"""Telegram bot handlers for user settings and timezone configuration."""

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.keyboards.settings import TimezoneCallback, get_settings_keyboard
from src.services.user_service import (
    get_or_create_user,
    get_user,
    get_user_local_time,
    update_user_timezone,
)

router = Router(name="settings")
settings_router = router


def format_settings_text(
    timezone: str,
    local_time_str: str,
    updated: bool = False,
) -> str:
    """Format settings menu text adhering to design-system.md standards."""
    status_header = "✅ Часовий пояс оновлено!\n" if updated else ""
    return (
        f"⚙️ <b>Налаштування</b>\n\n"
        f"{status_header}"
        f"🌍 Часовий пояс: <code>{timezone}</code>\n"
        f"🕒 Поточний локальний час: <code>{local_time_str}</code>\n\n"
        "Оберіть часовий пояс зі швидкого списку нижче або відкрийте Mini App для повного налаштування."
    )


@router.message(Command("settings"))
async def settings_command(
    message: Message,
    session: AsyncSession,
    webapp_url: str | None = None,
) -> Message | None:
    """Handle /settings command to display and manage user preferences.

    Verifies REQ-USR-02:
    - Automatically gets or registers user.
    - Computes user local time and formats HTML response.
    - Attaches quick timezone selection keyboard and Mini App launcher.
    - Safely returns None if message.from_user is None.
    """
    if message.from_user is None:
        return None

    user, _ = await get_or_create_user(
        session=session,
        telegram_id=message.from_user.id,
    )
    local_time = get_user_local_time(user)
    local_time_str = local_time.strftime("%H:%M, %d.%m.%Y")

    text = format_settings_text(
        timezone=user.timezone,
        local_time_str=local_time_str,
        updated=False,
    )
    keyboard = get_settings_keyboard(current_tz=user.timezone, webapp_url=webapp_url)

    return await message.answer(text=text, reply_markup=keyboard)


@router.callback_query(TimezoneCallback.filter())
async def handle_timezone_callback(
    callback_query: CallbackQuery,
    callback_data: TimezoneCallback,
    session: AsyncSession,
    webapp_url: str | None = None,
) -> None:
    """Handle interactive quick timezone selection callback.

    Verifies REQ-USR-02:
    - Confirms callback sender identity.
    - If selected timezone is already active, answers without modifying database.
    - If selected timezone differs, updates user timezone in database, edits message
      text and reply markup with updated checkmark, and answers callback query.
    """
    if callback_query.from_user is None:
        return

    telegram_id = callback_query.from_user.id
    user = await get_user(session, telegram_id)
    if user is None:
        user, _ = await get_or_create_user(session, telegram_id)

    if callback_data.timezone == user.timezone:
        await callback_query.answer("Цей часовий пояс уже встановлено.")
        return

    updated_user = await update_user_timezone(
        session=session,
        telegram_id=telegram_id,
        timezone=callback_data.timezone,
    )
    new_local_time = get_user_local_time(updated_user)
    new_local_time_str = new_local_time.strftime("%H:%M, %d.%m.%Y")

    new_text = format_settings_text(
        timezone=updated_user.timezone,
        local_time_str=new_local_time_str,
        updated=True,
    )
    new_keyboard = get_settings_keyboard(
        current_tz=updated_user.timezone,
        webapp_url=webapp_url,
    )

    if callback_query.message:
        await callback_query.message.edit_text(
            text=new_text,
            reply_markup=new_keyboard,
        )

    await callback_query.answer("Часовий пояс змінено!")


@router.callback_query(F.data == "open_settings_app")
async def handle_fallback_settings_app(callback_query: CallbackQuery) -> None:
    """Handle click on Mini App launcher button when webapp_url is not configured."""
    await callback_query.answer("Mini App недоступний у тестовому режимі", show_alert=True)


__all__ = [
    "format_settings_text",
    "handle_fallback_settings_app",
    "handle_timezone_callback",
    "router",
    "settings_command",
    "settings_router",
]
