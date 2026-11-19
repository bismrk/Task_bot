import asyncio
import enum
import io
import logging
import os
from datetime import date, datetime, timedelta
from typing import Literal, Optional
from zoneinfo import ZoneInfo

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from sqlalchemy import BigInteger, Date, DateTime, Enum, ForeignKey, String, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# ==========================================
# 1. КОНФІГУРАЦІЯ
# ==========================================
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///tasks.db")

if not BOT_TOKEN or not GEMINI_API_KEY:
    raise ValueError("Заповни BOT_TOKEN та GEMINI_API_KEY у файлі .env")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Ініціалізація Gemini клієнта
genai_client = genai.Client(api_key=GEMINI_API_KEY)


# ==========================================
# 2. БАЗА ДАНИХ (SQLAlchemy 2.0 Async)
# ==========================================
class Base(DeclarativeBase):
    pass


class TaskStatus(str, enum.Enum):
    TODO = "todo"
    DONE = "done"
    CANCELED = "canceled"


class TaskPriority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class User(Base):
    __tablename__ = "users"

    telegram_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    timezone: Mapped[str] = mapped_column(String(50), default="Europe/Berlin")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    tasks: Mapped[list["Task"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.telegram_id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(255))
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus), default=TaskStatus.TODO
    )
    priority: Mapped[TaskPriority] = mapped_column(
        Enum(TaskPriority), default=TaskPriority.MEDIUM
    )
    tag: Mapped[Optional[str]] = mapped_column(String(50), index=True)
    target_date: Mapped[date] = mapped_column(Date, index=True)
    deadline_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="tasks")


engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_or_create_user(session: AsyncSession, telegram_id: int) -> User:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if not user:
        user = User(telegram_id=telegram_id)
        session.add(user)
        await session.commit()
    return user


# ==========================================
# 3. AI-ПАРСЕР (Gemini 2.5 Flash -> JSON)
# ==========================================
class ParsedTask(BaseModel):
    title: str = Field(
        description="Коротка, чітка назва задачі у форматі дії (напр. 'Полити квіти')"
    )
    target_date: str = Field(description="Дата виконання у форматі YYYY-MM-DD")
    deadline_time: Optional[str] = Field(
        default=None,
        description="Час дедлайну у форматі HH:MM (24h), якщо згадано, інакше null",
    )
    priority: Literal["low", "medium", "high"] = Field(
        default="medium",
        description="high для термінових/важливих задач, low для другорядних, інакше medium",
    )
    tag: Optional[str] = Field(
        default=None,
        description="Одна коротка категорія українською (Робота, Дім, Спорт, Навчання, Особисте тощо)",
    )


class ParsedTasksResponse(BaseModel):
    tasks: list[ParsedTask]


def build_system_prompt(user_tz: str) -> str:
    now = datetime.now(ZoneInfo(user_tz))
    # Якщо юзер планує ввечері (21:00–23:59), дефолтна дата — завтра; інакше — сьогодні
    default_date = (now + timedelta(days=1)).date() if now.hour >= 21 else now.date()

    return (
        "Ти — асистент для планування задач. Проаналізуй аудіо або текст користувача "
        "та витягни всі згадані задачі.\n\n"
        f"Контекст користувача:\n"
        f"- Поточна дата і час: {now.strftime('%Y-%m-%d %H:%M')} ({user_tz})\n"
        f"- Дефолтна дата для задач (якщо не вказано інше): {default_date.isoformat()}\n\n"
        "Правила:\n"
        "1. Формулюй `title` лаконічно українською мовою, прибираючи слова-паразити.\n"
        "2. Якщо названо конкретний час ('до 15:00', 'о шостій вечора'), запиши його в `deadline_time` (HH:MM).\n"
        "3. Визначай `priority`: 'high' для термінових, 'low' для другорядних, 'medium' за замовчуванням.\n"
        "4. Підбери один найбільш доречний `tag` українською.\n"
        "5. Поверни результат строго у форматі заданої JSON-схеми."
    )


async def parse_tasks_with_gemini(
    user_tz: str,
    text: Optional[str] = None,
    audio_bytes: Optional[bytes] = None,
) -> list[ParsedTask]:
    prompt = build_system_prompt(user_tz)
    contents: list = [prompt]

    if audio_bytes:
        contents.append(
            types.Part.from_bytes(data=audio_bytes, mime_type="audio/ogg")
        )
    if text:
        contents.append(text)

    # Виклик Gemini у фоновому потоці, щоб не блокувати event loop aiogram
    response = await asyncio.to_thread(
        genai_client.models.generate_content,
        model="gemini-2.5-flash",
        contents=contents,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ParsedTasksResponse,
            temperature=0.2,
        ),
    )

    parsed = ParsedTasksResponse.model_validate_json(response.text)
    return parsed.tasks


# ==========================================
# 4. TELEGRAM BOT (aiogram 3)
# ==========================================
router = Router()


class TaskDraftState(StatesGroup):
    confirming = State()


PRIORITY_ICONS = {"high": "🔥", "medium": "🔹", "low": "▫️"}


def format_tasks_preview(tasks: list[dict]) -> str:
    lines = ["<b>Ось що я розпізнав:</b>\n"]
    for i, t in enumerate(tasks, 1):
        icon = PRIORITY_ICONS.get(t["priority"], "🔹")
        tag = f" <code>#{t['tag']}</code>" if t.get("tag") else ""
        deadline = f" ⏰ {t['deadline_time']}" if t.get("deadline_time") else ""
        lines.append(f"{i}. {icon} {t['title']}{deadline}{tag} ({t['target_date']})")
    lines.append("\nЗберегти цей список чи виправити?")
    return "\n".join(lines)


def get_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Зберегти", callback_data="draft:save"),
                InlineKeyboardButton(text="✏️ Виправити", callback_data="draft:edit"),
            ],
            [InlineKeyboardButton(text="❌ Скасувати", callback_data="draft:cancel")],
        ]
    )


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    async with async_session() as session:
        await get_or_create_user(session, message.from_user.id)

    await message.answer(
        "Привіт! 👋 Я твій трекер задач.\n\n"
        "Просто <b>надиктуй голосове</b> або <b>напиши текстом</b> свої плани — "
        "я витягну задачі, дедлайни, пріоритети й теги."
    )


@router.message(F.voice | F.text)
async def handle_voice_or_text(message: Message, state: FSMContext, bot: Bot) -> None:
    status_msg = await message.answer("⏳ Розпізнаю задачі...")

    async with async_session() as session:
        user = await get_or_create_user(session, message.from_user.id)
        user_tz = user.timezone

    try:
        audio_bytes = None
        text_input = message.text

        if message.voice:
            file = await bot.get_file(message.voice.file_id)
            buf = io.BytesIO()
            await bot.download_file(file.file_path, destination=buf)
            audio_bytes = buf.getvalue()

        parsed_tasks = await parse_tasks_with_gemini(
            user_tz=user_tz, text=text_input, audio_bytes=audio_bytes
        )

        if not parsed_tasks:
            await status_msg.edit_text("Не знайшов жодної задачі. Спробуй ще раз!")
            return

        tasks_dicts = [t.model_dump() for t in parsed_tasks]
        await state.set_state(TaskDraftState.confirming)
        await state.update_data(draft_tasks=tasks_dicts, user_tz=user_tz)

        await status_msg.edit_text(
            format_tasks_preview(tasks_dicts),
            reply_markup=get_confirm_keyboard(),
            parse_mode="HTML",
        )

    except Exception as e:
        logger.exception("Помилка при парсингу задач")
        await status_msg.edit_text(f"⚠️ Помилка обробки: {e}")


@router.callback_query(F.data == "draft:save", TaskDraftState.confirming)
async def cb_save_draft(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    draft_tasks = data.get("draft_tasks", [])
    user_tz = ZoneInfo(data.get("user_tz", "Europe/Berlin"))

    async with async_session() as session:
        for item in draft_tasks:
            target_d = date.fromisoformat(item["target_date"])
            deadline_dt = None

            if item.get("deadline_time"):
                h, m = map(int, item["deadline_time"].split(":"))
                local_dt = datetime(
                    target_d.year, target_d.month, target_d.day, h, m, tzinfo=user_tz
                )
                deadline_dt = local_dt.astimezone(ZoneInfo("UTC"))

            task = Task(
                user_id=callback.from_user.id,
                title=item["title"],
                priority=TaskPriority(item["priority"]),
                tag=item.get("tag"),
                target_date=target_d,
                deadline_at=deadline_dt,
            )
            session.add(task)
        await session.commit()

    await state.clear()
    await callback.message.edit_text(
        f"✅ Збережено задач: <b>{len(draft_tasks)}</b>!", parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "draft:edit", TaskDraftState.confirming)
async def cb_edit_draft(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text(
        "✏️ Окей, надиктуй нове голосове або напиши виправлений список текстом."
    )
    await callback.answer()


@router.callback_query(F.data == "draft:cancel", TaskDraftState.confirming)
async def cb_cancel_draft(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("❌ Чернетку скасовано.")
    await callback.answer()


# ==========================================
# 5. ЗАПУСК
# ==========================================
async def main() -> None:
    await init_db()
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)

    logger.info("Бот запущено!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())