"""Start command handler for Telegram bot."""

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.keyboards.start import get_start_keyboard
from src.services.user_service import get_or_create_user

router = Router(name="start")
start_router = router

NEW_USER_MESSAGE = (
    "<b>Вітаю у Task Tracker Bot!</b> 🚀\n\n"
    "Я допоможу тримати всі ваші задачі під контролем.\n\n"
    "✨ <b>Що я вмію:</b>\n"
    "• 🎙 <b>Голосові нотатки:</b> Надиктуйте задачі голосом — AI розпізнає та структурує їх.\n"
    "• 📋 <b>Швидке планування:</b> Додавайте завдання звичайним текстом.\n"
    "• 🕒 <b>Нагадування та дедлайни:</b> Сповіщення про дедлайни, щоб нічого не пропустити.\n"
    "• 🌙 <b>Нічний перегляд (00:00):</b> Автоматичне перенесення невиконаних задач («хвостів»).\n"
    "• ☀️ <b>Ранковий дайджест (09:00):</b> Щоденний план для фокусу на головному.\n\n"
    "💡 Натисніть кнопку нижче, щоб відкрити свій персональний план!"
)

RETURNING_USER_MESSAGE = (
    "<b>З поверненням!</b> 🚀\n\n"
    "Радий бачити вас знову. Ваші задачі вже чекають на вас.\n\n"
    "💡 Натисніть кнопку нижче, щоб відкрити план, або надішліть нове завдання текстом чи голосом."
)


@router.message(CommandStart())
async def start_command(
    message: Message,
    session: AsyncSession,
    webapp_url: str | None = None,
) -> Message | None:
    """Handle /start command for new and returning users.

    Verifies REQ-USR-01:
    - Registers new user with default timezone 'Europe/Kyiv' and sends onboarding text.
    - Greets returning user without modifying their existing timezone or data.
    - Safely returns None if message.from_user is None.
    """
    if message.from_user is None:
        return None

    _, created = await get_or_create_user(
        session=session,
        telegram_id=message.from_user.id,
        timezone="Europe/Kyiv",
    )

    keyboard = get_start_keyboard(webapp_url=webapp_url)

    if created:
        return await message.answer(text=NEW_USER_MESSAGE, reply_markup=keyboard)
    return await message.answer(text=RETURNING_USER_MESSAGE, reply_markup=keyboard)
