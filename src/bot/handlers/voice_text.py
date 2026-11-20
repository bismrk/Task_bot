"""Voice and text task ingestion bot handlers."""

import io
import logging

from aiogram import Bot, F, Router
from aiogram.enums import ChatAction
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.keyboards.tasks import get_task_confirmation_keyboard
from src.bot.states.tasks import TaskIngestionState
from src.models.task import TaskPriority
from src.schemas.task import ExtractedTask
from src.services.ai_parser import parse_tasks_from_audio, parse_tasks_from_text
from src.services.user_service import get_or_create_user

logger = logging.getLogger(__name__)

router = Router(name="voice_text")
voice_text_router = router

EMPTY_TASKS_NOTIFICATION = (
    "💡 Не вдалося розпізнати завдання. Спробуйте надиктувати або написати чіткіше."
)


def format_extracted_tasks_message(tasks: list[ExtractedTask]) -> str:
    """Format extracted tasks into an HTML-formatted message with semantic emojis.

    Adheres to _docs/design-system.md:
    Header: <b>📋 Розпізнані завдання:</b>
    Items: • [Назва задачі] — ⚠️ Високий | 🏷️ #робота | 📅 {target_date} | 🕒 до {time}
    """
    if not tasks:
        return ""

    lines = ["<b>📋 Розпізнані завдання:</b>\n"]
    for task in tasks:
        meta_parts: list[str] = []

        # Priority badge
        if task.priority == TaskPriority.high:
            meta_parts.append("⚠️ Високий")
        elif task.priority == TaskPriority.low:
            meta_parts.append("💤 Низький")
        else:
            meta_parts.append("⚡ Середній")

        # Category tag
        if task.tag:
            clean_tag = task.tag.lstrip("#")
            meta_parts.append(f"🏷️ #{clean_tag}")

        # Target date
        if task.target_date:
            meta_parts.append(f"📅 {task.target_date}")

        # Formatted deadline
        if task.deadline_at:
            meta_parts.append(f"🕒 до {task.deadline_at.strftime('%H:%M')}")

        meta_str = " | ".join(meta_parts)
        lines.append(f"• {task.title} — {meta_str}")

    return "\n".join(lines)


@router.message(F.voice)
async def handle_voice_message(
    message: Message,
    bot: Bot,
    session: AsyncSession,
    state: FSMContext,
) -> Message | None:
    """Handle incoming voice message for task extraction.

    Verifies REQ-AI-01, REQ-AI-02, REQ-AI-03, REQ-USR-01:
    - Safely returns None if message.from_user or message.voice is missing.
    - Resolves user timezone from database via get_or_create_user.
    - Dispatches chat action UPLOAD_VOICE.
    - Downloads audio in-memory into io.BytesIO without writing to disk.
    - Invokes Gemini AI parser with audio bytes and user timezone.
    - If no tasks extracted, replies with polite notification without keyboard or FSM update.
    - If tasks extracted, saves pending tasks to FSM, sets waiting_confirmation state,
      and replies with formatted tasks list and confirmation keyboard.
    """
    if message.from_user is None or message.voice is None:
        return None

    user, _ = await get_or_create_user(session, telegram_id=message.from_user.id)

    await bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.UPLOAD_VOICE)

    audio_buffer = io.BytesIO()
    await bot.download(message.voice.file_id, destination=audio_buffer)
    audio_bytes = audio_buffer.getvalue()

    tasks = await parse_tasks_from_audio(
        audio_bytes=audio_bytes,
        user_timezone=user.timezone,
    )

    if not tasks:
        return await message.answer(text=EMPTY_TASKS_NOTIFICATION)

    await state.update_data(pending_tasks=[t.model_dump(mode="json") for t in tasks])
    await state.set_state(TaskIngestionState.waiting_confirmation)

    formatted_text = format_extracted_tasks_message(tasks)
    keyboard = get_task_confirmation_keyboard(user_id=message.from_user.id)
    return await message.answer(text=formatted_text, reply_markup=keyboard)


@router.message(F.text & ~F.text.startswith("/"))
async def handle_text_message(
    message: Message,
    bot: Bot,
    session: AsyncSession,
    state: FSMContext,
) -> Message | None:
    """Handle incoming non-command text message for task extraction.

    Verifies REQ-AI-02, REQ-AI-03, REQ-USR-01:
    - Safely returns None if message.from_user or message.text is empty/whitespace.
    - Resolves user timezone from database via get_or_create_user.
    - Dispatches chat action TYPING.
    - Invokes Gemini AI parser with text and user timezone.
    - If no tasks extracted, replies with polite notification without keyboard or FSM update.
    - If tasks extracted, saves pending tasks to FSM, sets waiting_confirmation state,
      and replies with formatted tasks list and confirmation keyboard.
    """
    if message.from_user is None or message.text is None or not message.text.strip():
        return None

    user, _ = await get_or_create_user(session, telegram_id=message.from_user.id)

    await bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)

    tasks = await parse_tasks_from_text(
        text=message.text,
        user_timezone=user.timezone,
    )

    if not tasks:
        return await message.answer(text=EMPTY_TASKS_NOTIFICATION)

    await state.update_data(pending_tasks=[t.model_dump(mode="json") for t in tasks])
    await state.set_state(TaskIngestionState.waiting_confirmation)

    formatted_text = format_extracted_tasks_message(tasks)
    keyboard = get_task_confirmation_keyboard(user_id=message.from_user.id)
    return await message.answer(text=formatted_text, reply_markup=keyboard)
