"""Integration tests for Telegram bot settings command, keyboards, and callback handlers."""

from unittest.mock import AsyncMock

import pytest
from aiogram.types import (
    CallbackQuery,
    Chat,
    InlineKeyboardMarkup,
    Message,
    User as TgUser,
    WebAppInfo,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.handlers.settings import (
    format_settings_text,
    handle_fallback_settings_app,
    handle_timezone_callback,
    settings_command,
)
from src.bot.keyboards.settings import (
    TIMEZONE_PRESETS,
    TimezoneCallback,
    get_settings_keyboard,
)
from src.models.user import User
from src.services.user_service import get_or_create_user, get_user_local_time


def create_mock_message() -> AsyncMock:
    """Create an AsyncMock for Message with async answer and edit methods."""
    msg = AsyncMock(spec=Message)
    msg.answer = AsyncMock()
    msg.edit_text = AsyncMock()
    msg.edit_reply_markup = AsyncMock()
    return msg


# ==============================================================================
# Keyboard & Formatter Tests
# ==============================================================================


def test_get_settings_keyboard_structure_and_presets() -> None:
    """Verifies REQ-USR-02: get_settings_keyboard creates max 2 buttons per row, checkmark on current, and Mini App launcher."""
    current_tz = "Europe/Kyiv"
    webapp_url = "https://app.example.com"
    kb = get_settings_keyboard(current_tz=current_tz, webapp_url=webapp_url)

    assert isinstance(kb, InlineKeyboardMarkup)
    # Check max 2 buttons per preset row
    for row in kb.inline_keyboard[:-1]:
        assert len(row) <= 2

    # Checkmark on currently active timezone
    found_checked = False
    all_buttons = [btn for row in kb.inline_keyboard for btn in row]
    for btn in all_buttons:
        cb_data = btn.callback_data or ""
        if "Europe/Kyiv" in cb_data:
            assert "✓" in btn.text
            found_checked = True
        elif cb_data.startswith("tz:"):
            assert "✓" not in btn.text

    assert found_checked

    # Mini App launcher button in bottom row
    last_row = kb.inline_keyboard[-1]
    assert len(last_row) == 1
    mini_app_btn = last_row[0]
    assert mini_app_btn.text == "⚙️ Відкрити в Mini App"
    assert isinstance(mini_app_btn.web_app, WebAppInfo)
    assert mini_app_btn.web_app.url == webapp_url


def test_get_settings_keyboard_fallback_when_no_webapp_url() -> None:
    """Verifies REQ-USR-02: get_settings_keyboard produces fallback callback when webapp_url is None or empty."""
    kb_none = get_settings_keyboard(current_tz="Europe/Warsaw", webapp_url=None)
    last_btn = kb_none.inline_keyboard[-1][0]
    assert last_btn.web_app is None
    assert last_btn.callback_data == "open_settings_app"

    kb_empty = get_settings_keyboard(current_tz="Europe/Warsaw", webapp_url="  ")
    last_btn_empty = kb_empty.inline_keyboard[-1][0]
    assert last_btn_empty.web_app is None
    assert last_btn_empty.callback_data == "open_settings_app"


# ==============================================================================
# /settings Command Handler Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_settings_command_existing_user(db_session: AsyncSession) -> None:
    """Verifies REQ-USR-02: /settings returns formatted HTML message with timezone, local time, and keyboard."""
    telegram_id = 30001
    user, _ = await get_or_create_user(db_session, telegram_id=telegram_id, timezone="Europe/Warsaw")

    tg_user = TgUser(id=telegram_id, is_bot=False, first_name="ExistingUser")
    mock_msg = create_mock_message()
    mock_msg.from_user = tg_user

    await settings_command(
        message=mock_msg,
        session=db_session,
        webapp_url="https://app.example.com",
    )

    mock_msg.answer.assert_called_once()
    call_args, call_kwargs = mock_msg.answer.call_args
    sent_text = call_kwargs.get("text", call_args[0] if call_args else "")
    reply_markup = call_kwargs.get("reply_markup")

    # Verify formatted text contents
    assert "⚙️ <b>Налаштування</b>" in sent_text
    assert "🌍 Часовий пояс: <code>Europe/Warsaw</code>" in sent_text
    assert "🕒 Поточний локальний час:" in sent_text

    # Verify keyboard attached
    assert isinstance(reply_markup, InlineKeyboardMarkup)
    assert any("Варшава ✓" in btn.text for row in reply_markup.inline_keyboard for btn in row)


@pytest.mark.asyncio
async def test_settings_command_unregistered_user_auto_registered(db_session: AsyncSession) -> None:
    """Verifies REQ-USR-01, REQ-USR-02: /settings automatically registers new user with default Europe/Kyiv."""
    telegram_id = 30002
    tg_user = TgUser(id=telegram_id, is_bot=False, first_name="NewUser")
    mock_msg = create_mock_message()
    mock_msg.from_user = tg_user

    await settings_command(
        message=mock_msg,
        session=db_session,
        webapp_url=None,
    )

    # Verify user was created in database
    stmt = select(User).where(User.telegram_id == telegram_id)
    saved_user = (await db_session.execute(stmt)).scalar_one_or_none()
    assert saved_user is not None
    assert saved_user.timezone == "Europe/Kyiv"

    mock_msg.answer.assert_called_once()
    call_args, call_kwargs = mock_msg.answer.call_args
    sent_text = call_kwargs.get("text", call_args[0] if call_args else "")
    assert "Europe/Kyiv" in sent_text


@pytest.mark.asyncio
async def test_settings_command_from_user_none(db_session: AsyncSession) -> None:
    """Verifies REQ-USR-02: /settings handles message with from_user is None safely returning None."""
    mock_msg = create_mock_message()
    mock_msg.from_user = None

    result = await settings_command(
        message=mock_msg,
        session=db_session,
        webapp_url=None,
    )

    assert result is None
    mock_msg.answer.assert_not_called()


# ==============================================================================
# Timezone Callback Handler Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_timezone_callback_updates_timezone_and_edits_message(db_session: AsyncSession) -> None:
    """Verifies REQ-USR-02: Timezone callback updates DB, updates message text and markup, and answers query."""
    telegram_id = 40001
    user, _ = await get_or_create_user(db_session, telegram_id=telegram_id, timezone="Europe/Kyiv")

    mock_msg = create_mock_message()
    query = AsyncMock(spec=CallbackQuery)
    query.from_user = TgUser(id=telegram_id, is_bot=False, first_name="TzUser")
    query.message = mock_msg
    query.answer = AsyncMock()

    callback_data = TimezoneCallback(timezone="America/New_York")

    await handle_timezone_callback(
        callback_query=query,
        callback_data=callback_data,
        session=db_session,
        webapp_url="https://app.example.com",
    )

    # Verify database updated
    stmt = select(User).where(User.telegram_id == telegram_id)
    updated_user = (await db_session.execute(stmt)).scalar_one()
    assert updated_user.timezone == "America/New_York"

    # Verify message edited
    mock_msg.edit_text.assert_called_once()
    edit_args, edit_kwargs = mock_msg.edit_text.call_args
    edited_text = edit_kwargs.get("text", edit_args[0] if edit_args else "")
    edited_markup = edit_kwargs.get("reply_markup")

    assert "✅ Часовий пояс оновлено!" in edited_text
    assert "America/New_York" in edited_text
    assert any("Нью-Йорк ✓" in btn.text for row in edited_markup.inline_keyboard for btn in row)

    # Verify callback acknowledged
    query.answer.assert_called_once_with("Часовий пояс змінено!")


@pytest.mark.asyncio
async def test_timezone_callback_already_set_no_db_write(db_session: AsyncSession) -> None:
    """Verifies REQ-USR-02: Selecting already active timezone performs no DB write and notifies user."""
    telegram_id = 40002
    user, _ = await get_or_create_user(db_session, telegram_id=telegram_id, timezone="Europe/Kyiv")

    mock_msg = create_mock_message()
    query = AsyncMock(spec=CallbackQuery)
    query.from_user = TgUser(id=telegram_id, is_bot=False, first_name="TzUser2")
    query.message = mock_msg
    query.answer = AsyncMock()

    callback_data = TimezoneCallback(timezone="Europe/Kyiv")

    await handle_timezone_callback(
        callback_query=query,
        callback_data=callback_data,
        session=db_session,
        webapp_url=None,
    )

    # Verify query answered with notice
    query.answer.assert_called_once_with("Цей часовий пояс уже встановлено.")

    # Verify message was NOT edited
    mock_msg.edit_text.assert_not_called()


@pytest.mark.asyncio
async def test_fallback_settings_app_callback() -> None:
    """Verifies REQ-USR-02: Clicking fallback Mini App button displays alert notification."""
    query = AsyncMock(spec=CallbackQuery)
    query.answer = AsyncMock()

    await handle_fallback_settings_app(query)
    query.answer.assert_called_once_with("Mini App недоступний у тестовому режимі", show_alert=True)


def test_dispatcher_includes_settings_router() -> None:
    """Verifies REQ-USR-02: create_dispatcher includes settings_router in sub-routers."""
    from src.bot.dispatcher import create_dispatcher
    from src.bot.handlers.settings import settings_router

    dp = create_dispatcher()
    assert settings_router in dp.sub_routers

