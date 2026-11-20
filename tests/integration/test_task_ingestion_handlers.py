"""Integration tests for voice and text task ingestion bot handlers and confirmation callbacks."""

from datetime import date, datetime, timezone
import io
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram import Bot
from aiogram.enums import ChatAction
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    Chat,
    InlineKeyboardMarkup,
    Message,
    Update,
    User as TgUser,
    Voice,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.bot.dispatcher import create_dispatcher
from src.bot.handlers.callbacks import task_confirm_callback
from src.bot.handlers.voice_text import (
    EMPTY_TASKS_NOTIFICATION,
    format_extracted_tasks_message,
    handle_text_message,
    handle_voice_message,
)
from src.bot.keyboards.tasks import TaskConfirmCallback, get_task_confirmation_keyboard
from src.bot.states.tasks import TaskIngestionState
from src.models.task import Task, TaskPriority, TaskStatus
from src.models.user import User
from src.schemas.task import ExtractedTask


def create_fsm_context(user_id: int, chat_id: int, bot_id: int = 1) -> tuple[FSMContext, MemoryStorage]:
    """Helper to create an isolated in-memory FSMContext."""
    storage = MemoryStorage()
    key = StorageKey(bot_id=bot_id, chat_id=chat_id, user_id=user_id)
    return FSMContext(storage=storage, key=key), storage


# ==============================================================================
# Helper & Keyboard Unit Tests
# ==============================================================================


def test_get_task_confirmation_keyboard_structure() -> None:
    """Verifies REQ-AI-03: get_task_confirmation_keyboard returns 2 buttons in a single row."""
    user_id = 12345
    kb = get_task_confirmation_keyboard(user_id=user_id)

    assert isinstance(kb, InlineKeyboardMarkup)
    assert len(kb.inline_keyboard) == 1
    row = kb.inline_keyboard[0]
    assert len(row) <= 2  # Design system: max 2 buttons per row
    assert len(row) == 2

    # Save button
    save_btn = row[0]
    assert save_btn.text == "✅ Зберегти"
    save_data = TaskConfirmCallback.unpack(save_btn.callback_data)
    assert save_data.action == "save"
    assert save_data.user_id == user_id

    # Edit button
    edit_btn = row[1]
    assert edit_btn.text == "✏️ Виправити"
    edit_data = TaskConfirmCallback.unpack(edit_btn.callback_data)
    assert edit_data.action == "edit"
    assert edit_data.user_id == user_id


def test_format_extracted_tasks_message_formatting() -> None:
    """Verifies REQ-AI-02, REQ-AI-03: format_extracted_tasks_message includes header and semantic emojis."""
    tasks = [
        ExtractedTask(
            title="Терміновий звіт",
            target_date=date(2026, 11, 20),
            deadline_at=datetime(2026, 11, 20, 15, 30, tzinfo=timezone.utc),
            priority=TaskPriority.high,
            tag="робота",
        ),
        ExtractedTask(
            title="Прибирання",
            target_date=date(2026, 11, 21),
            deadline_at=None,
            priority=TaskPriority.low,
            tag=None,
        ),
        ExtractedTask(
            title="Купити каву",
            target_date=date(2026, 11, 20),
            deadline_at=None,
            priority=TaskPriority.medium,
            tag="#покупки",
        ),
    ]

    formatted = format_extracted_tasks_message(tasks)

    # Header check
    assert "<b>📋 Розпізнані завдання:</b>" in formatted

    # High priority task
    assert "• Терміновий звіт — " in formatted
    assert "⚠️ Високий" in formatted
    assert "🏷️ #робота" in formatted
    assert "📅 2026-11-20" in formatted
    assert "🕒 до 15:30" in formatted

    # Low priority task
    assert "• Прибирання — " in formatted
    assert "💤 Низький" in formatted
    assert "📅 2026-11-21" in formatted

    # Medium priority task
    assert "• Купити каву — " in formatted
    assert "⚡ Середній" in formatted
    assert "🏷️ #покупки" in formatted


def test_format_extracted_tasks_message_empty() -> None:
    """Verifies REQ-AI-02: format_extracted_tasks_message returns empty string for empty input."""
    assert format_extracted_tasks_message([]) == ""


# ==============================================================================
# Voice Message Handler Tests (REQ-AI-01, REQ-AI-02)
# ==============================================================================


@pytest.mark.asyncio
async def test_handle_voice_message_success(db_session: AsyncSession) -> None:
    """Verifies REQ-AI-01, REQ-AI-02, REQ-AI-03: handle_voice_message downloads in-memory, parses, and sets FSM."""
    user_id = 10001
    chat_id = 10001

    bot = AsyncMock(spec=Bot)
    bot.id = 1
    bot.send_chat_action = AsyncMock()

    # In-memory download simulation (zero disk files)
    fake_audio_bytes = b"fake_opus_bytes_data_stream"

    async def fake_download(file_id: str, destination: io.BytesIO) -> None:
        destination.write(fake_audio_bytes)

    bot.download = AsyncMock(side_effect=fake_download)

    state, _ = create_fsm_context(user_id=user_id, chat_id=chat_id)

    tg_user = TgUser(id=user_id, is_bot=False, first_name="VoiceTester")
    tg_chat = Chat(id=chat_id, type="private")
    voice = Voice(file_id="voice_file_123", file_unique_id="v_uniq_123", duration=5)

    message = AsyncMock(spec=Message)
    message.from_user = tg_user
    message.chat = tg_chat
    message.voice = voice
    message.answer = AsyncMock()

    extracted_tasks = [
        ExtractedTask(
            title="Купити продукти",
            target_date=date(2026, 11, 20),
            priority=TaskPriority.medium,
            tag="покупки",
        )
    ]

    with patch(
        "src.bot.handlers.voice_text.parse_tasks_from_audio",
        new_callable=AsyncMock,
        return_value=extracted_tasks,
    ) as mock_parse:
        result = await handle_voice_message(
            message=message,
            bot=bot,
            session=db_session,
            state=state,
        )

        # 1. Assert user registered with Europe/Kyiv default
        stmt = select(User).where(User.telegram_id == user_id)
        user = (await db_session.execute(stmt)).scalar_one_or_none()
        assert user is not None
        assert user.timezone == "Europe/Kyiv"

        # 2. Assert chat action UPLOAD_VOICE sent
        bot.send_chat_action.assert_called_once_with(
            chat_id=chat_id,
            action=ChatAction.UPLOAD_VOICE,
        )

        # 3. Assert bot.download was called into in-memory buffer
        bot.download.assert_called_once()
        assert bot.download.call_args[0][0] == "voice_file_123"

        # 4. Assert parse_tasks_from_audio received correct audio bytes & user timezone
        mock_parse.assert_called_once_with(
            audio_bytes=fake_audio_bytes,
            user_timezone="Europe/Kyiv",
        )

        # 5. Assert FSM state & data updated
        current_state = await state.get_state()
        assert current_state == TaskIngestionState.waiting_confirmation.state

        state_data = await state.get_data()
        assert "pending_tasks" in state_data
        assert len(state_data["pending_tasks"]) == 1
        assert state_data["pending_tasks"][0]["title"] == "Купити продукти"

        # 6. Assert bot replied with message and keyboard
        message.answer.assert_called_once()
        call_kwargs = message.answer.call_args[1]
        assert "<b>📋 Розпізнані завдання:</b>" in call_kwargs["text"]
        assert "Купити продукти" in call_kwargs["text"]

        keyboard = call_kwargs["reply_markup"]
        assert isinstance(keyboard, InlineKeyboardMarkup)
        assert keyboard.inline_keyboard[0][0].text == "✅ Зберегти"
        assert keyboard.inline_keyboard[0][1].text == "✏️ Виправити"


@pytest.mark.asyncio
async def test_handle_voice_message_empty_tasks(db_session: AsyncSession) -> None:
    """Verifies REQ-AI-02: handle_voice_message replies politely when no tasks extracted, no FSM entered."""
    user_id = 10002
    chat_id = 10002

    bot = AsyncMock(spec=Bot)
    bot.id = 1
    bot.send_chat_action = AsyncMock()
    bot.download = AsyncMock()

    state, _ = create_fsm_context(user_id=user_id, chat_id=chat_id)

    tg_user = TgUser(id=user_id, is_bot=False, first_name="NoiseTester")
    tg_chat = Chat(id=chat_id, type="private")
    voice = Voice(file_id="noise_voice_456", file_unique_id="v_uniq_456", duration=2)

    message = AsyncMock(spec=Message)
    message.from_user = tg_user
    message.chat = tg_chat
    message.voice = voice
    message.answer = AsyncMock()

    with patch(
        "src.bot.handlers.voice_text.parse_tasks_from_audio",
        new_callable=AsyncMock,
        return_value=[],
    ):
        await handle_voice_message(
            message=message,
            bot=bot,
            session=db_session,
            state=state,
        )

        # Notification message sent without keyboard
        message.answer.assert_called_once_with(text=EMPTY_TASKS_NOTIFICATION)

        # FSM state remains empty
        current_state = await state.get_state()
        assert current_state is None
        state_data = await state.get_data()
        assert "pending_tasks" not in state_data


@pytest.mark.asyncio
async def test_handle_voice_message_none_safety(db_session: AsyncSession) -> None:
    """Verifies REQ-AI-01: handle_voice_message returns None safely when from_user or voice is None."""
    bot = AsyncMock(spec=Bot)
    state, _ = create_fsm_context(user_id=1, chat_id=1)

    # Message without from_user
    msg_no_user = AsyncMock(spec=Message)
    msg_no_user.from_user = None
    msg_no_user.voice = Voice(file_id="f1", file_unique_id="u1", duration=1)
    res1 = await handle_voice_message(msg_no_user, bot, db_session, state)
    assert res1 is None

    # Message without voice
    msg_no_voice = AsyncMock(spec=Message)
    msg_no_voice.from_user = TgUser(id=1, is_bot=False, first_name="NoVoice")
    msg_no_voice.voice = None
    res2 = await handle_voice_message(msg_no_voice, bot, db_session, state)
    assert res2 is None


# ==============================================================================
# Text Message Handler Tests (REQ-AI-02)
# ==============================================================================


@pytest.mark.asyncio
async def test_handle_text_message_success(db_session: AsyncSession) -> None:
    """Verifies REQ-AI-02, REQ-AI-03: handle_text_message dispatches TYPING, parses text, and sets FSM."""
    user_id = 20001
    chat_id = 20001

    bot = AsyncMock(spec=Bot)
    bot.id = 1
    bot.send_chat_action = AsyncMock()

    state, _ = create_fsm_context(user_id=user_id, chat_id=chat_id)

    tg_user = TgUser(id=user_id, is_bot=False, first_name="TextTester")
    tg_chat = Chat(id=chat_id, type="private")

    message = AsyncMock(spec=Message)
    message.from_user = tg_user
    message.chat = tg_chat
    message.text = "Зробити звіт до завтра 18:00"
    message.answer = AsyncMock()

    extracted_tasks = [
        ExtractedTask(
            title="Зробити звіт",
            target_date=date(2026, 11, 21),
            deadline_at=datetime(2026, 11, 21, 18, 0, tzinfo=timezone.utc),
            priority=TaskPriority.high,
            tag="робота",
        )
    ]

    with patch(
        "src.bot.handlers.voice_text.parse_tasks_from_text",
        new_callable=AsyncMock,
        return_value=extracted_tasks,
    ) as mock_parse:
        await handle_text_message(
            message=message,
            bot=bot,
            session=db_session,
            state=state,
        )

        # 1. Assert TYPING action sent
        bot.send_chat_action.assert_called_once_with(
            chat_id=chat_id,
            action=ChatAction.TYPING,
        )

        # 2. Assert parser invoked with message text & user timezone
        mock_parse.assert_called_once_with(
            text="Зробити звіт до завтра 18:00",
            user_timezone="Europe/Kyiv",
        )

        # 3. Assert FSM state & data updated
        current_state = await state.get_state()
        assert current_state == TaskIngestionState.waiting_confirmation.state

        state_data = await state.get_data()
        assert len(state_data["pending_tasks"]) == 1
        assert state_data["pending_tasks"][0]["title"] == "Зробити звіт"

        # 4. Assert reply with keyboard sent
        message.answer.assert_called_once()
        call_kwargs = message.answer.call_args[1]
        assert "<b>📋 Розпізнані завдання:</b>" in call_kwargs["text"]
        assert "Зробити звіт" in call_kwargs["text"]
        assert isinstance(call_kwargs["reply_markup"], InlineKeyboardMarkup)


@pytest.mark.asyncio
async def test_handle_text_message_empty_tasks(db_session: AsyncSession) -> None:
    """Verifies REQ-AI-02: handle_text_message replies politely when text has no tasks, no FSM entered."""
    user_id = 20002
    chat_id = 20002

    bot = AsyncMock(spec=Bot)
    bot.id = 1
    bot.send_chat_action = AsyncMock()

    state, _ = create_fsm_context(user_id=user_id, chat_id=chat_id)

    tg_user = TgUser(id=user_id, is_bot=False, first_name="ChitchatTester")
    tg_chat = Chat(id=chat_id, type="private")

    message = AsyncMock(spec=Message)
    message.from_user = tg_user
    message.chat = tg_chat
    message.text = "Привіт, як справи? Гарна погода."
    message.answer = AsyncMock()

    with patch(
        "src.bot.handlers.voice_text.parse_tasks_from_text",
        new_callable=AsyncMock,
        return_value=[],
    ):
        await handle_text_message(
            message=message,
            bot=bot,
            session=db_session,
            state=state,
        )

        message.answer.assert_called_once_with(text=EMPTY_TASKS_NOTIFICATION)
        current_state = await state.get_state()
        assert current_state is None


@pytest.mark.asyncio
async def test_handle_text_message_none_or_empty_safety(db_session: AsyncSession) -> None:
    """Verifies REQ-AI-02: handle_text_message returns None for None from_user or empty/whitespace text."""
    bot = AsyncMock(spec=Bot)
    state, _ = create_fsm_context(user_id=1, chat_id=1)

    # None user
    m1 = AsyncMock(spec=Message)
    m1.from_user = None
    m1.text = "Купити молоко"
    assert await handle_text_message(m1, bot, db_session, state) is None

    # Empty text
    m2 = AsyncMock(spec=Message)
    m2.from_user = TgUser(id=1, is_bot=False, first_name="Empty")
    m2.text = ""
    assert await handle_text_message(m2, bot, db_session, state) is None

    # Whitespace text
    m3 = AsyncMock(spec=Message)
    m3.from_user = TgUser(id=1, is_bot=False, first_name="Whitespace")
    m3.text = "   \n\t  "
    assert await handle_text_message(m3, bot, db_session, state) is None


# ==============================================================================
# Confirmation Callback Tests (REQ-AI-03, REQ-TSK-01, REQ-NFR-02)
# ==============================================================================


@pytest.mark.asyncio
async def test_callback_save_persists_tasks_and_clears_fsm(db_session: AsyncSession) -> None:
    """Verifies REQ-AI-03, REQ-TSK-01: [✅ Зберегти] callback persists tasks in DB with status todo and clears FSM."""
    user_id = 30001
    chat_id = 30001

    # Ensure user exists in DB
    db_user = User(telegram_id=user_id, timezone="Europe/Kyiv")
    db_session.add(db_user)
    await db_session.commit()

    state, _ = create_fsm_context(user_id=user_id, chat_id=chat_id)
    pending_tasks = [
        ExtractedTask(
            title="Зателефонувати клієнту",
            target_date=date(2026, 11, 20),
            priority=TaskPriority.high,
            tag="робота",
        ).model_dump(mode="json"),
        ExtractedTask(
            title="Купити чай",
            target_date=date(2026, 11, 20),
            priority=TaskPriority.low,
            tag="дім",
        ).model_dump(mode="json"),
    ]
    await state.set_state(TaskIngestionState.waiting_confirmation)
    await state.update_data(pending_tasks=pending_tasks)

    # Mock CallbackQuery and Message
    mock_message = AsyncMock(spec=Message)
    mock_message.edit_text = AsyncMock()

    tg_user = TgUser(id=user_id, is_bot=False, first_name="CallbackUser")
    callback_query = AsyncMock(spec=CallbackQuery)
    callback_query.from_user = tg_user
    callback_query.message = mock_message
    callback_query.answer = AsyncMock()

    callback_data = TaskConfirmCallback(action="save", user_id=user_id)

    await task_confirm_callback(
        callback_query=callback_query,
        callback_data=callback_data,
        session=db_session,
        state=state,
    )

    # 1. Assert tasks persisted in DB
    stmt = select(Task).where(Task.user_id == user_id).order_by(Task.id.asc())
    saved_tasks = list((await db_session.execute(stmt)).scalars().all())
    assert len(saved_tasks) == 2

    assert saved_tasks[0].title == "Зателефонувати клієнту"
    assert saved_tasks[0].status == TaskStatus.todo
    assert saved_tasks[0].priority == TaskPriority.high
    assert saved_tasks[0].tag == "робота"

    assert saved_tasks[1].title == "Купити чай"
    assert saved_tasks[1].status == TaskStatus.todo
    assert saved_tasks[1].priority == TaskPriority.low

    # 2. Assert original message edited with confirmation text & no keyboard
    mock_message.edit_text.assert_called_once_with(
        text="✅ <b>Завдання успішно збережено!</b>",
        reply_markup=None,
    )

    # 3. Assert FSM state cleared
    assert await state.get_state() is None
    assert (await state.get_data()) == {}

    # 4. Assert callback answered
    callback_query.answer.assert_called_once_with("Збережено!")


@pytest.mark.asyncio
async def test_callback_edit_prompts_reentry_and_clears_fsm(db_session: AsyncSession) -> None:
    """Verifies REQ-AI-03: [✏️ Виправити] callback prompts user to re-enter tasks and clears FSM."""
    user_id = 30002
    chat_id = 30002

    state, _ = create_fsm_context(user_id=user_id, chat_id=chat_id)
    await state.set_state(TaskIngestionState.waiting_confirmation)
    await state.update_data(pending_tasks=[{"title": "Помилкова задача", "target_date": "2026-11-20"}])

    mock_message = AsyncMock(spec=Message)
    mock_message.edit_text = AsyncMock()

    tg_user = TgUser(id=user_id, is_bot=False, first_name="EditUser")
    callback_query = AsyncMock(spec=CallbackQuery)
    callback_query.from_user = tg_user
    callback_query.message = mock_message
    callback_query.answer = AsyncMock()

    callback_data = TaskConfirmCallback(action="edit", user_id=user_id)

    await task_confirm_callback(
        callback_query=callback_query,
        callback_data=callback_data,
        session=db_session,
        state=state,
    )

    # 1. Assert message edited to prompt re-entry and keyboard removed
    mock_message.edit_text.assert_called_once_with(
        text="✏️ Будь ласка, надиктуйте або надішліть текстом нове формулювання завдань.",
        reply_markup=None,
    )

    # 2. Assert FSM cleared
    assert await state.get_state() is None
    assert (await state.get_data()) == {}

    # 3. Assert callback answered
    callback_query.answer.assert_called_once_with()

    # 4. Assert no tasks created in DB
    stmt = select(Task).where(Task.user_id == user_id)
    assert len((await db_session.execute(stmt)).scalars().all()) == 0


@pytest.mark.asyncio
async def test_callback_tenant_security_rejection(db_session: AsyncSession) -> None:
    """Verifies REQ-AI-03, REQ-NFR-02: Callback from unauthorized user is rejected with alert and no state modification."""
    owner_id = 40001
    attacker_id = 99999
    chat_id = 40001

    state, _ = create_fsm_context(user_id=owner_id, chat_id=chat_id)
    initial_tasks = [
        ExtractedTask(
            title="Конфіденційне завдання",
            target_date=date(2026, 11, 20),
            priority=TaskPriority.high,
        ).model_dump(mode="json")
    ]
    await state.set_state(TaskIngestionState.waiting_confirmation)
    await state.update_data(pending_tasks=initial_tasks)

    # Attacker presses owner's button
    mock_message = AsyncMock(spec=Message)
    attacker_user = TgUser(id=attacker_id, is_bot=False, first_name="Attacker")
    callback_query = AsyncMock(spec=CallbackQuery)
    callback_query.from_user = attacker_user
    callback_query.message = mock_message
    callback_query.answer = AsyncMock()

    callback_data = TaskConfirmCallback(action="save", user_id=owner_id)

    await task_confirm_callback(
        callback_query=callback_query,
        callback_data=callback_data,
        session=db_session,
        state=state,
    )

    # 1. Assert alert was displayed to unauthorized user
    callback_query.answer.assert_called_once_with(
        "⚠️ Ви не можете керувати завданнями іншого користувача.",
        show_alert=True,
    )

    # 2. Assert message was NOT modified
    mock_message.edit_text.assert_not_called()

    # 3. Assert owner's state was NOT cleared
    assert await state.get_state() == TaskIngestionState.waiting_confirmation.state
    data = await state.get_data()
    assert data["pending_tasks"] == initial_tasks

    # 4. Assert no tasks were persisted
    stmt = select(Task)
    assert len((await db_session.execute(stmt)).scalars().all()) == 0


@pytest.mark.asyncio
async def test_callback_expired_state_handling(db_session: AsyncSession) -> None:
    """Verifies REQ-AI-03: Callback with expired or missing FSM state shows alert and removes keyboard safely."""
    user_id = 50001
    chat_id = 50001

    state, _ = create_fsm_context(user_id=user_id, chat_id=chat_id)
    # State has no pending_tasks

    mock_message = AsyncMock(spec=Message)
    mock_message.edit_reply_markup = AsyncMock()

    tg_user = TgUser(id=user_id, is_bot=False, first_name="ExpiredUser")
    callback_query = AsyncMock(spec=CallbackQuery)
    callback_query.from_user = tg_user
    callback_query.message = mock_message
    callback_query.answer = AsyncMock()

    callback_data = TaskConfirmCallback(action="save", user_id=user_id)

    await task_confirm_callback(
        callback_query=callback_query,
        callback_data=callback_data,
        session=db_session,
        state=state,
    )

    # 1. Assert alert was shown
    callback_query.answer.assert_called_once_with(
        "⚠️ Завдання вже збережено або сесія застаріла.",
        show_alert=True,
    )

    # 2. Assert keyboard was removed
    mock_message.edit_reply_markup.assert_called_once_with(reply_markup=None)

    # 3. Assert no tasks persisted
    stmt = select(Task)
    assert len((await db_session.execute(stmt)).scalars().all()) == 0


# ==============================================================================
# Full Dispatcher Pipeline Integration Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_dispatcher_ignores_commands_for_task_ingestion(db_session: AsyncSession) -> None:
    """Verifies REQ-AI-02: Commands such as /start and /settings are not parsed as tasks."""
    bind = db_session.bind
    session_factory = async_sessionmaker(bind=bind, expire_on_commit=False, class_=AsyncSession)

    dp = create_dispatcher(sessionmaker=session_factory)
    mock_bot = AsyncMock(spec=Bot)
    mock_bot.id = 1
    mock_bot.send_chat_action = AsyncMock()

    telegram_id = 60001
    tg_user = TgUser(id=telegram_id, is_bot=False, first_name="CommandUser")
    chat = Chat(id=telegram_id, type="private")

    with patch("src.bot.handlers.voice_text.parse_tasks_from_text", new_callable=AsyncMock) as mock_parse:
        # 1. Send /start command
        msg_start = Message(
            message_id=101,
            date=datetime.now(timezone.utc),
            chat=chat,
            from_user=tg_user,
            text="/start",
        )
        await dp.feed_update(bot=mock_bot, update=Update(update_id=1, message=msg_start))

        # 2. Send /settings command
        msg_settings = Message(
            message_id=102,
            date=datetime.now(timezone.utc),
            chat=chat,
            from_user=tg_user,
            text="/settings",
        )
        await dp.feed_update(bot=mock_bot, update=Update(update_id=2, message=msg_settings))

        # parse_tasks_from_text should NEVER be called for commands
        mock_parse.assert_not_called()


@pytest.mark.asyncio
async def test_dispatcher_feed_text_message_to_save_callback_pipeline(db_session: AsyncSession) -> None:
    """Verifies REQ-AI-02, REQ-AI-03, REQ-TSK-01: Full pipeline: text message -> FSM waiting_confirmation -> save callback -> DB."""
    bind = db_session.bind
    session_factory = async_sessionmaker(bind=bind, expire_on_commit=False, class_=AsyncSession)

    dp = create_dispatcher(sessionmaker=session_factory)

    telegram_id = 70001
    tg_user = TgUser(id=telegram_id, is_bot=False, first_name="PipelineTester")
    chat = Chat(id=telegram_id, type="private")

    mock_bot = AsyncMock(spec=Bot)
    mock_bot.id = 1
    mock_bot.send_chat_action = AsyncMock()

    extracted = [
        ExtractedTask(
            title="Підготувати презентацію",
            target_date=date(2026, 11, 22),
            priority=TaskPriority.high,
            tag="робота",
        )
    ]

    with patch("src.bot.handlers.voice_text.parse_tasks_from_text", new_callable=AsyncMock, return_value=extracted):
        msg = Message(
            message_id=201,
            date=datetime.now(timezone.utc),
            chat=chat,
            from_user=tg_user,
            text="Підготувати презентацію на післязавтра терміново",
        )
        await dp.feed_update(bot=mock_bot, update=Update(update_id=201, message=msg))

        # Check bot sent chat action and reply
        mock_bot.send_chat_action.assert_called_with(chat_id=telegram_id, action=ChatAction.TYPING)

        # Check FSM state in dispatcher storage
        key = StorageKey(bot_id=1, chat_id=telegram_id, user_id=telegram_id)
        current_state = await dp.storage.get_state(key=key)
        assert current_state == TaskIngestionState.waiting_confirmation.state

        state_data = await dp.storage.get_data(key=key)
        assert len(state_data["pending_tasks"]) == 1

        # Now simulate user pressing [✅ Зберегти]
        cb_data = TaskConfirmCallback(action="save", user_id=telegram_id).pack()
        cb_msg = Message(
            message_id=202,
            date=datetime.now(timezone.utc),
            chat=chat,
            from_user=tg_user,
            text="Розпізнані завдання",
        )
        cb_query = CallbackQuery(
            id="cb_q_1",
            from_user=tg_user,
            chat_instance="ci_1",
            message=cb_msg,
            data=cb_data,
        )

        await dp.feed_update(bot=mock_bot, update=Update(update_id=202, callback_query=cb_query))

        # Check tasks persisted to DB
        stmt = select(Task).where(Task.user_id == telegram_id)
        saved = list((await db_session.execute(stmt)).scalars().all())
        assert len(saved) == 1
        assert saved[0].title == "Підготувати презентацію"
        assert saved[0].status == TaskStatus.todo
        assert saved[0].priority == TaskPriority.high

        # Check FSM cleared
        cleared_state = await dp.storage.get_state(key=key)
        assert cleared_state is None
