"""Unit tests for bot initialization, dispatcher configuration, and keyboards."""

from unittest.mock import patch

import pytest
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardButton, WebAppInfo

from src.bot import create_bot, create_dispatcher
from src.bot.handlers import start_router
from src.bot.keyboards import get_start_keyboard
from src.bot.middlewares import DbSessionMiddleware
from src.core import Settings


def test_create_bot_with_explicit_token() -> None:
    """Verifies REQ-USR-01: create_bot initializes Bot with explicit token and HTML parse mode."""
    token = "123456789:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
    bot = create_bot(token=token)
    assert isinstance(bot, Bot)
    assert bot.token == token
    assert bot.default.parse_mode == ParseMode.HTML


def test_create_bot_with_settings_token() -> None:
    """Verifies REQ-USR-01: create_bot falls back to Settings.BOT_TOKEN when no token passed."""
    fake_token = "987654321:XYZ-DEF1234ghIkl-zyx57W2v1u123ew11"
    fake_settings = Settings(BOT_TOKEN=fake_token, _env_file=None)
    with patch("src.bot.dispatcher.get_settings", return_value=fake_settings):
        bot = create_bot()
        assert isinstance(bot, Bot)
        assert bot.token == fake_token
        assert bot.default.parse_mode == ParseMode.HTML


def test_create_bot_raises_error_when_token_empty() -> None:
    """Verifies REQ-USR-01: create_bot raises ValueError when token is empty or whitespace."""
    fake_settings = Settings(BOT_TOKEN="", _env_file=None)
    with patch("src.bot.dispatcher.get_settings", return_value=fake_settings):
        with pytest.raises(ValueError, match="BOT_TOKEN is not set"):
            create_bot()

    with pytest.raises(ValueError, match="BOT_TOKEN is not set"):
        create_bot(token="   ")


def test_create_dispatcher_attaches_middleware_and_router() -> None:
    """Verifies REQ-USR-01: create_dispatcher attaches DbSessionMiddleware and registers start_router."""
    webapp_url = "https://app.example.com"
    dp = create_dispatcher(webapp_url=webapp_url)

    assert isinstance(dp, Dispatcher)
    assert dp.workflow_data["webapp_url"] == webapp_url

    # Check middlewares on message and callback_query
    message_middlewares = [m for m in dp.message.middleware]
    assert any(isinstance(m, DbSessionMiddleware) for m in message_middlewares)

    callback_middlewares = [m for m in dp.callback_query.middleware]
    assert any(isinstance(m, DbSessionMiddleware) for m in callback_middlewares)

    # Check that start_router is included in sub-routers
    sub_routers = dp.sub_routers
    assert start_router in sub_routers


def test_get_start_keyboard_with_webapp_url() -> None:
    """Verifies REQ-USR-01: get_start_keyboard creates WebAppInfo button when webapp_url is provided."""
    url = "https://miniapp.example.com"
    kb = get_start_keyboard(webapp_url=url)

    assert len(kb.inline_keyboard) == 1
    row = kb.inline_keyboard[0]
    assert len(row) <= 2  # Design system: max 2 buttons per row
    button = row[0]
    assert isinstance(button, InlineKeyboardButton)
    assert button.text == "🚀 Відкрити план"
    assert isinstance(button.web_app, WebAppInfo)
    assert button.web_app.url == url
    assert button.callback_data is None


def test_get_start_keyboard_fallback_when_webapp_url_none_or_empty() -> None:
    """Verifies REQ-USR-01: get_start_keyboard creates fallback callback button when webapp_url is None or empty."""
    for empty_val in [None, "", "   "]:
        kb = get_start_keyboard(webapp_url=empty_val)
        assert len(kb.inline_keyboard) == 1
        row = kb.inline_keyboard[0]
        assert len(row) <= 2
        button = row[0]
        assert button.text == "🚀 Відкрити план"
        assert button.callback_data == "open_plan"
        assert button.web_app is None
