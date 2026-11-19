"""Integration tests for database session middleware and /start bot handler."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram import Bot
from aiogram.types import Chat, Message, Update, User as TgUser
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.bot.dispatcher import create_dispatcher
from src.bot.handlers.start import start_command
from src.bot.middlewares.db import DbSessionMiddleware
from src.models.user import User


@pytest.mark.asyncio
async def test_db_session_middleware_commit_on_success(db_session: AsyncSession) -> None:
    """Verifies REQ-USR-01: DbSessionMiddleware injects session and commits transaction on success."""
    # Create a custom sessionmaker backed by the same engine / session setup
    bind = db_session.bind
    session_factory = async_sessionmaker(bind=bind, expire_on_commit=False, class_=AsyncSession)

    middleware = DbSessionMiddleware(sessionmaker=session_factory)
    data: dict[str, object] = {}
    mock_event = MagicMock()

    async def sample_handler(event, handler_data):
        session: AsyncSession = handler_data["session"]
        assert isinstance(session, AsyncSession)
        user = User(telegram_id=111222, timezone="Europe/Kyiv")
        session.add(user)
        return "success"

    result = await middleware(sample_handler, mock_event, data)
    assert result == "success"

    # Verify committed in database
    stmt = select(User).where(User.telegram_id == 111222)
    saved_user = (await db_session.execute(stmt)).scalar_one_or_none()
    assert saved_user is not None
    assert saved_user.telegram_id == 111222


@pytest.mark.asyncio
async def test_db_session_middleware_rollback_on_exception(db_session: AsyncSession) -> None:
    """Verifies REQ-USR-01: DbSessionMiddleware rolls back transaction and re-raises on exception."""
    bind = db_session.bind
    session_factory = async_sessionmaker(bind=bind, expire_on_commit=False, class_=AsyncSession)

    middleware = DbSessionMiddleware(sessionmaker=session_factory)
    data: dict[str, object] = {}
    mock_event = MagicMock()

    async def failing_handler(event, handler_data):
        session: AsyncSession = handler_data["session"]
        user = User(telegram_id=333444, timezone="Europe/Kyiv")
        session.add(user)
        raise RuntimeError("Something failed in handler")

    with pytest.raises(RuntimeError, match="Something failed in handler"):
        await middleware(failing_handler, mock_event, data)

    # Verify record was rolled back
    stmt = select(User).where(User.telegram_id == 333444)
    saved_user = (await db_session.execute(stmt)).scalar_one_or_none()
    assert saved_user is None


@pytest.mark.asyncio
async def test_start_command_new_user_onboarding(db_session: AsyncSession) -> None:
    """Verifies REQ-USR-01: /start registers a new user with Europe/Kyiv and sends onboarding message."""
    telegram_id = 777001
    tg_user = TgUser(id=telegram_id, is_bot=False, first_name="Nazarii", username="nazarii_test")
    chat = Chat(id=telegram_id, type="private")

    mock_message = AsyncMock(spec=Message)
    mock_message.from_user = tg_user
    mock_message.chat = chat
    mock_message.answer = AsyncMock()

    result = await start_command(
        message=mock_message,
        session=db_session,
        webapp_url="https://miniapp.example.com",
    )

    # Verify user persisted in database
    stmt = select(User).where(User.telegram_id == telegram_id)
    user = (await db_session.execute(stmt)).scalar_one_or_none()
    assert user is not None
    assert user.telegram_id == telegram_id
    assert user.timezone == "Europe/Kyiv"

    # Verify mock message.answer call
    mock_message.answer.assert_called_once()
    call_args, call_kwargs = mock_message.answer.call_args
    sent_text = call_kwargs.get("text", call_args[0] if call_args else "")
    reply_markup = call_kwargs.get("reply_markup")

    # Check onboarding text content and semantic emojis
    for emoji in ["🚀", "📋", "✨", "💡", "🕒"]:
        assert emoji in sent_text

    assert "Голосові нотатки" in sent_text
    assert "00:00" in sent_text
    assert "09:00" in sent_text

    # Check attached keyboard
    assert reply_markup is not None
    assert reply_markup.inline_keyboard[0][0].text == "🚀 Відкрити план"
    assert reply_markup.inline_keyboard[0][0].web_app.url == "https://miniapp.example.com"


@pytest.mark.asyncio
async def test_start_command_returning_user_greeting(db_session: AsyncSession) -> None:
    """Verifies REQ-USR-01: /start greets returning user without modifying timezone or creating duplicates."""
    telegram_id = 777002
    existing_user = User(telegram_id=telegram_id, timezone="America/New_York")
    db_session.add(existing_user)
    await db_session.commit()

    tg_user = TgUser(id=telegram_id, is_bot=False, first_name="ExistingUser")
    chat = Chat(id=telegram_id, type="private")

    mock_message = AsyncMock(spec=Message)
    mock_message.from_user = tg_user
    mock_message.chat = chat
    mock_message.answer = AsyncMock()

    await start_command(
        message=mock_message,
        session=db_session,
        webapp_url=None,
    )

    # Verify only 1 user record exists and timezone is preserved
    stmt = select(User).where(User.telegram_id == telegram_id)
    users = (await db_session.execute(stmt)).scalars().all()
    assert len(users) == 1
    assert users[0].timezone == "America/New_York"

    # Verify returning user greeting sent
    mock_message.answer.assert_called_once()
    call_args, call_kwargs = mock_message.answer.call_args
    sent_text = call_kwargs.get("text", call_args[0] if call_args else "")
    reply_markup = call_kwargs.get("reply_markup")

    assert "З поверненням" in sent_text
    assert "🚀" in sent_text
    assert "💡" in sent_text

    # Check fallback callback_data button when webapp_url is None
    assert reply_markup is not None
    assert reply_markup.inline_keyboard[0][0].callback_data == "open_plan"


@pytest.mark.asyncio
async def test_start_command_from_user_none_handled_safely(db_session: AsyncSession) -> None:
    """Verifies REQ-USR-01: /start handles message with from_user is None safely without errors or DB changes."""
    mock_message = AsyncMock(spec=Message)
    mock_message.from_user = None
    mock_message.chat = Chat(id=1000, type="channel")
    mock_message.answer = AsyncMock()

    result = await start_command(
        message=mock_message,
        session=db_session,
        webapp_url="https://miniapp.example.com",
    )

    assert result is None
    mock_message.answer.assert_not_called()

    # Verify no users were created
    stmt = select(User)
    users = (await db_session.execute(stmt)).scalars().all()
    assert len(users) == 0


@pytest.mark.asyncio
async def test_dispatcher_feed_start_command_integration(db_session: AsyncSession) -> None:
    """Verifies REQ-USR-01: Full dispatcher pipeline processes /start command via DbSessionMiddleware."""
    bind = db_session.bind
    session_factory = async_sessionmaker(bind=bind, expire_on_commit=False, class_=AsyncSession)

    dp = create_dispatcher(
        sessionmaker=session_factory,
        webapp_url="https://miniapp.example.com",
    )

    mock_bot = AsyncMock(spec=Bot)
    mock_bot.return_value = MagicMock()

    telegram_id = 888123
    tg_user = TgUser(id=telegram_id, is_bot=False, first_name="PipelineUser")
    chat = Chat(id=telegram_id, type="private")

    msg = Message(
        message_id=1,
        date=datetime.now(timezone.utc),
        chat=chat,
        from_user=tg_user,
        text="/start",
    )
    update = Update(update_id=1, message=msg)

    # Feed message through dispatcher
    await dp.feed_update(bot=mock_bot, update=update)

    # Check that bot call was made to send the reply
    assert mock_bot.call_count == 1
    call_args = mock_bot.call_args[0]
    send_message_req = call_args[0]
    assert send_message_req.chat_id == telegram_id
    assert "Вітаю" in send_message_req.text

    # Check user record was committed in database
    stmt = select(User).where(User.telegram_id == telegram_id)
    user = (await db_session.execute(stmt)).scalar_one_or_none()
    assert user is not None
    assert user.timezone == "Europe/Kyiv"
