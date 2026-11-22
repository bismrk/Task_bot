"""Integration tests for voice and text task ingestion bot handlers and confirmation callbacks."""

from datetime import date, datetime, timedelta, timezone
import io
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram import Bot
from aiogram.enums import ChatAction
from aiogram.methods import EditMessageText, SendMessage
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
from src.bot.handlers.callbacks import plan_tomorrow_callback, task_confirm_callback
from src.bot.handlers.voice_text import (
    EMPTY_TASKS_NOTIFICATION,
    format_extracted_tasks_message,
    handle_text_message,
    handle_voice_message,
)
from src.bot.keyboards import (
    PlanTomorrowCallback as ExportedPlanTomorrowCallback,
    get_evening_summary_keyboard as exported_get_evening_summary_keyboard,
    get_plan_tomorrow_cancel_keyboard as exported_get_plan_tomorrow_cancel_keyboard,
)
from src.bot.keyboards.tasks import (
    PlanTomorrowCallback,
    TaskConfirmCallback,
    get_evening_summary_keyboard,
    get_plan_tomorrow_cancel_keyboard,
    get_task_confirmation_keyboard,
)
from src.bot.states.tasks import TaskIngestionState
from src.models.task import Task, TaskPriority, TaskStatus
from src.models.user import User
from src.schemas.task import ExtractedTask
from src.services.user_service import get_user_local_time


def create_fsm_context(user_id: int, chat_id: int, bot_id: int = 1) -> tuple[FSMContext, MemoryStorage]:
    """Helper to create an isolated in-memory FSMContext."""
    storage = MemoryStorage()
    key = StorageKey(bot_id=bot_id, chat_id=chat_id, user_id=user_id)
    return FSMContext(storage=storage, key=key), storage


# ==============================================================================
# Helper & Keyboard Unit Tests
# ==============================================================================


def test_get_task_confirmation_keyboard_structure() -> None:
    """Verifies REQ-AI-03: get_task_confirmation_keyboard returns 3 buttons across 2 rows with max 2 buttons per row."""
    user_id = 12345
    kb = get_task_confirmation_keyboard(user_id=user_id)

    assert isinstance(kb, InlineKeyboardMarkup)
    assert len(kb.inline_keyboard) == 2
    for r in kb.inline_keyboard:
        assert len(r) <= 2  # Design system: max 2 buttons per row

    row0 = kb.inline_keyboard[0]
    assert len(row0) == 2

    # Save button
    save_btn = row0[0]
    assert save_btn.text == "✅ Зберегти"
    save_data = TaskConfirmCallback.unpack(save_btn.callback_data)
    assert save_data.action == "save"
    assert save_data.user_id == user_id

    # Edit button
    edit_btn = row0[1]
    assert edit_btn.text == "✏️ Виправити"
    edit_data = TaskConfirmCallback.unpack(edit_btn.callback_data)
    assert edit_data.action == "edit"
    assert edit_data.user_id == user_id

    row1 = kb.inline_keyboard[1]
    assert len(row1) == 1

    # Delete button
    delete_btn = row1[0]
    assert delete_btn.text == "🗑️ Видалити"
    delete_data = TaskConfirmCallback.unpack(delete_btn.callback_data)
    assert delete_data.action == "delete"
    assert delete_data.user_id == user_id


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


def test_format_extracted_tasks_message_local_timezones_and_html() -> None:
    """Verifies REQ-AI-02, REQ-AI-03, REQ-USR-01: Local timezone conversion, HTML bold deadlines, naive UTC, fallback, and untimed omission."""
    tasks = [
        ExtractedTask(
            title="Вечірній звіт",
            target_date=date(2026, 11, 20),
            deadline_at=datetime(2026, 11, 20, 18, 0, tzinfo=timezone.utc),
            priority=TaskPriority.high,
            tag="робота",
        ),
        ExtractedTask(
            title="Ранковий рейс",
            target_date=date(2026, 11, 20),
            deadline_at=datetime(2026, 11, 20, 3, 0, tzinfo=timezone.utc),
            priority=TaskPriority.medium,
            tag=None,
        ),
        ExtractedTask(
            title="Завдання без часу",
            target_date=date(2026, 11, 20),
            deadline_at=None,
            priority=TaskPriority.low,
            tag="дім",
        ),
    ]

    # 1. Backward compatibility when user_timezone=None (no shift, HTML bold)
    formatted_default = format_extracted_tasks_message(tasks)
    assert "<b>🕒 до 18:00</b>" in formatted_default
    assert "<b>🕒 до 03:00</b>" in formatted_default
    untimed_line_default = next(
        line for line in formatted_default.splitlines() if "Завдання без часу" in line
    )
    assert "🕒" not in untimed_line_default

    # 2. Europe/Kyiv winter (UTC+2): 18:00 UTC -> 20:00, 03:00 UTC -> 05:00
    formatted_kyiv = format_extracted_tasks_message(tasks, user_timezone="Europe/Kyiv")
    assert "<b>🕒 до 20:00</b>" in formatted_kyiv
    assert "<b>🕒 до 05:00</b>" in formatted_kyiv
    untimed_line_kyiv = next(
        line for line in formatted_kyiv.splitlines() if "Завдання без часу" in line
    )
    assert "🕒" not in untimed_line_kyiv

    # 3. Non-Kyiv timezone America/New_York winter (EST, UTC-5): 18:00 UTC -> 13:00, 03:00 UTC -> 22:00
    formatted_ny = format_extracted_tasks_message(tasks, user_timezone="America/New_York")
    assert "<b>🕒 до 13:00</b>" in formatted_ny
    assert "<b>🕒 до 22:00</b>" in formatted_ny

    # 4. Invalid / blank timezone strings safely fall back to Europe/Kyiv
    for bad_tz in ("Invalid/Zone", "Mars/Olympus", "   ", ""):
        formatted_fallback = format_extracted_tasks_message(tasks, user_timezone=bad_tz)
        assert "<b>🕒 до 20:00</b>" in formatted_fallback
        assert "<b>🕒 до 05:00</b>" in formatted_fallback

    # 5. Naive datetime treated as UTC before converting to local timezone
    naive_tasks = [
        ExtractedTask.model_construct(
            title="Наївний дедлайн",
            target_date=date(2026, 11, 20),
            deadline_at=datetime(2026, 11, 20, 18, 0),
            priority=TaskPriority.medium,
            tag=None,
            recurrence=None,
        )
    ]
    formatted_naive_kyiv = format_extracted_tasks_message(
        naive_tasks, user_timezone="Europe/Kyiv"
    )
    assert "<b>🕒 до 20:00</b>" in formatted_naive_kyiv
    formatted_naive_ny = format_extracted_tasks_message(
        naive_tasks, user_timezone="America/New_York"
    )
    assert "<b>🕒 до 13:00</b>" in formatted_naive_ny


@pytest.mark.asyncio
async def test_handle_voice_and_text_render_local_deadline_times(
    db_session: AsyncSession,
) -> None:
    """Verifies REQ-AI-01, REQ-AI-02, REQ-USR-01: Voice and text handlers format deadlines in user's local timezone."""
    # Pre-create two users in different timezones
    kyiv_user_id = 80101
    ny_user_id = 80102
    db_session.add_all(
        [
            User(telegram_id=kyiv_user_id, timezone="Europe/Kyiv"),
            User(telegram_id=ny_user_id, timezone="America/New_York"),
        ]
    )
    await db_session.commit()

    extracted = [
        ExtractedTask(
            title="Ранковий дзвінок",
            target_date=date(2026, 11, 20),
            deadline_at=datetime(2026, 11, 20, 3, 0, tzinfo=timezone.utc),
            priority=TaskPriority.high,
            tag="робота",
        ),
        ExtractedTask(
            title="Купити хліб",
            target_date=date(2026, 11, 20),
            deadline_at=None,
            priority=TaskPriority.low,
        ),
    ]

    # Voice message for Europe/Kyiv user (03:00 UTC -> 05:00 local)
    bot_voice = AsyncMock(spec=Bot)
    bot_voice.id = 1
    bot_voice.send_chat_action = AsyncMock()

    async def fake_download(file_id: str, destination: io.BytesIO) -> None:
        destination.write(b"voice_bytes")

    bot_voice.download = AsyncMock(side_effect=fake_download)
    voice_state, _ = create_fsm_context(user_id=kyiv_user_id, chat_id=kyiv_user_id)
    voice_msg = AsyncMock(spec=Message)
    voice_msg.from_user = TgUser(id=kyiv_user_id, is_bot=False, first_name="KyivVoice")
    voice_msg.chat = Chat(id=kyiv_user_id, type="private")
    voice_msg.voice = Voice(file_id="vf_tz", file_unique_id="vu_tz", duration=3)
    voice_msg.answer = AsyncMock()

    with patch(
        "src.bot.handlers.voice_text.parse_tasks_from_audio",
        new_callable=AsyncMock,
        return_value=extracted,
    ):
        await handle_voice_message(
            message=voice_msg,
            bot=bot_voice,
            session=db_session,
            state=voice_state,
        )

    voice_reply_text = voice_msg.answer.call_args.kwargs["text"]
    assert "<b>🕒 до 05:00</b>" in voice_reply_text
    assert "🕒" not in next(
        line for line in voice_reply_text.splitlines() if "Купити хліб" in line
    )

    # Text message for America/New_York user (18:00 UTC -> 13:00 local)
    extracted_ny = [
        ExtractedTask(
            title="Надіслати рахунок",
            target_date=date(2026, 11, 20),
            deadline_at=datetime(2026, 11, 20, 18, 0, tzinfo=timezone.utc),
            priority=TaskPriority.high,
            tag="фінанси",
        )
    ]
    bot_text = AsyncMock(spec=Bot)
    bot_text.id = 1
    bot_text.send_chat_action = AsyncMock()
    text_state, _ = create_fsm_context(user_id=ny_user_id, chat_id=ny_user_id)
    text_msg = AsyncMock(spec=Message)
    text_msg.from_user = TgUser(id=ny_user_id, is_bot=False, first_name="NyText")
    text_msg.chat = Chat(id=ny_user_id, type="private")
    text_msg.text = "Надіслати рахунок до 13:00"
    text_msg.answer = AsyncMock()

    with patch(
        "src.bot.handlers.voice_text.parse_tasks_from_text",
        new_callable=AsyncMock,
        return_value=extracted_ny,
    ):
        await handle_text_message(
            message=text_msg,
            bot=bot_text,
            session=db_session,
            state=text_state,
        )

    text_reply_text = text_msg.answer.call_args.kwargs["text"]
    assert "<b>🕒 до 13:00</b>" in text_reply_text


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
        assert keyboard.inline_keyboard[1][0].text == "🗑️ Видалити"


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


@pytest.mark.asyncio
async def test_callback_delete_cancels_tasks_and_clears_fsm(db_session: AsyncSession) -> None:
    """Verifies REQ-AI-03, REQ-TSK-01, REQ-NFR-02: [🗑️ Видалити] callback clears FSM, edits message, and saves nothing to DB."""
    user_id = 50002
    chat_id = 50002

    state, _ = create_fsm_context(user_id=user_id, chat_id=chat_id)
    pending_tasks = [
        ExtractedTask(
            title="Непотрібне завдання",
            target_date=date(2026, 11, 20),
            priority=TaskPriority.medium,
        ).model_dump(mode="json")
    ]
    await state.set_state(TaskIngestionState.waiting_confirmation)
    await state.update_data(pending_tasks=pending_tasks)

    mock_message = AsyncMock(spec=Message)
    mock_message.edit_text = AsyncMock()

    tg_user = TgUser(id=user_id, is_bot=False, first_name="DeleteUser")
    callback_query = AsyncMock(spec=CallbackQuery)
    callback_query.from_user = tg_user
    callback_query.message = mock_message
    callback_query.answer = AsyncMock()

    callback_data = TaskConfirmCallback(action="delete", user_id=user_id)

    await task_confirm_callback(
        callback_query=callback_query,
        callback_data=callback_data,
        session=db_session,
        state=state,
    )

    # 1. Assert FSM state cleared
    assert await state.get_state() is None
    assert (await state.get_data()) == {}

    # 2. Assert message edited to cancellation text and keyboard removed
    mock_message.edit_text.assert_called_once_with(
        text="🗑️ <b>Завдання скасовано та видалено.</b>",
        reply_markup=None,
    )

    # 3. Assert callback answered
    callback_query.answer.assert_called_once_with("Скасовано!")

    # 4. Assert zero tasks in DB
    stmt = select(Task).where(Task.user_id == user_id)
    assert len((await db_session.execute(stmt)).scalars().all()) == 0


@pytest.mark.asyncio
async def test_callback_delete_tenant_security_rejection(db_session: AsyncSession) -> None:
    """Verifies REQ-AI-03, REQ-NFR-02: [🗑️ Видалити] callback from unauthorized user is rejected with alert."""
    owner_id = 50003
    attacker_id = 99998
    chat_id = 50003

    state, _ = create_fsm_context(user_id=owner_id, chat_id=chat_id)
    initial_tasks = [
        ExtractedTask(
            title="Особисте завдання",
            target_date=date(2026, 11, 20),
            priority=TaskPriority.high,
        ).model_dump(mode="json")
    ]
    await state.set_state(TaskIngestionState.waiting_confirmation)
    await state.update_data(pending_tasks=initial_tasks)

    mock_message = AsyncMock(spec=Message)
    mock_message.edit_text = AsyncMock()

    attacker_user = TgUser(id=attacker_id, is_bot=False, first_name="Attacker")
    callback_query = AsyncMock(spec=CallbackQuery)
    callback_query.from_user = attacker_user
    callback_query.message = mock_message
    callback_query.answer = AsyncMock()

    callback_data = TaskConfirmCallback(action="delete", user_id=owner_id)

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
async def test_callback_delete_with_already_cleared_fsm(db_session: AsyncSession) -> None:
    """Verifies REQ-AI-03: [🗑️ Видалити] callback when FSM state is already empty/None executes safely."""
    user_id = 50004
    chat_id = 50004

    state, _ = create_fsm_context(user_id=user_id, chat_id=chat_id)

    mock_message = AsyncMock(spec=Message)
    mock_message.edit_text = AsyncMock()

    tg_user = TgUser(id=user_id, is_bot=False, first_name="ClearedUser")
    callback_query = AsyncMock(spec=CallbackQuery)
    callback_query.from_user = tg_user
    callback_query.message = mock_message
    callback_query.answer = AsyncMock()

    callback_data = TaskConfirmCallback(action="delete", user_id=user_id)

    await task_confirm_callback(
        callback_query=callback_query,
        callback_data=callback_data,
        session=db_session,
        state=state,
    )

    # 1. Assert message edited to cancellation text and keyboard removed
    mock_message.edit_text.assert_called_once_with(
        text="🗑️ <b>Завдання скасовано та видалено.</b>",
        reply_markup=None,
    )

    # 2. Assert callback answered
    callback_query.answer.assert_called_once_with("Скасовано!")

    # 3. Assert state is still cleared
    assert await state.get_state() is None
    assert (await state.get_data()) == {}


@pytest.mark.asyncio
async def test_callback_delete_message_none_safety(db_session: AsyncSession) -> None:
    """Verifies REQ-AI-03: [🗑️ Видалити] callback when callback_query.message is None executes safely."""
    user_id = 50005
    chat_id = 50005

    state, _ = create_fsm_context(user_id=user_id, chat_id=chat_id)
    await state.set_state(TaskIngestionState.waiting_confirmation)
    await state.update_data(pending_tasks=[{"title": "test"}])

    tg_user = TgUser(id=user_id, is_bot=False, first_name="NoMsgUser")
    callback_query = AsyncMock(spec=CallbackQuery)
    callback_query.from_user = tg_user
    callback_query.message = None
    callback_query.answer = AsyncMock()

    callback_data = TaskConfirmCallback(action="delete", user_id=user_id)

    await task_confirm_callback(
        callback_query=callback_query,
        callback_data=callback_data,
        session=db_session,
        state=state,
    )

    # 1. Assert state cleared
    assert await state.get_state() is None
    assert (await state.get_data()) == {}

    # 2. Assert callback answered
    callback_query.answer.assert_called_once_with("Скасовано!")


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


@pytest.mark.asyncio
async def test_dispatcher_feed_text_message_to_delete_callback_pipeline(db_session: AsyncSession) -> None:
    """Verifies REQ-AI-02, REQ-AI-03, REQ-TSK-01: Full pipeline: text message -> FSM waiting_confirmation -> delete callback -> FSM cleared & zero DB tasks."""
    bind = db_session.bind
    session_factory = async_sessionmaker(bind=bind, expire_on_commit=False, class_=AsyncSession)

    dp = create_dispatcher(sessionmaker=session_factory)

    telegram_id = 70002
    tg_user = TgUser(id=telegram_id, is_bot=False, first_name="PipelineDeleteTester")
    chat = Chat(id=telegram_id, type="private")

    mock_bot = AsyncMock(spec=Bot)
    mock_bot.id = 1
    mock_bot.send_chat_action = AsyncMock()

    extracted = [
        ExtractedTask(
            title="Скасоване завдання",
            target_date=date(2026, 11, 22),
            priority=TaskPriority.medium,
            tag="тест",
        )
    ]

    with patch("src.bot.handlers.voice_text.parse_tasks_from_text", new_callable=AsyncMock, return_value=extracted):
        msg = Message(
            message_id=301,
            date=datetime.now(timezone.utc),
            chat=chat,
            from_user=tg_user,
            text="Скасоване завдання на післязавтра",
        )
        await dp.feed_update(bot=mock_bot, update=Update(update_id=301, message=msg))

        # Check bot sent chat action and reply
        mock_bot.send_chat_action.assert_called_with(chat_id=telegram_id, action=ChatAction.TYPING)

        # Check FSM state in dispatcher storage
        key = StorageKey(bot_id=1, chat_id=telegram_id, user_id=telegram_id)
        current_state = await dp.storage.get_state(key=key)
        assert current_state == TaskIngestionState.waiting_confirmation.state

        state_data = await dp.storage.get_data(key=key)
        assert len(state_data["pending_tasks"]) == 1

        # Now simulate user pressing [🗑️ Видалити]
        cb_data = TaskConfirmCallback(action="delete", user_id=telegram_id).pack()
        cb_msg = Message(
            message_id=302,
            date=datetime.now(timezone.utc),
            chat=chat,
            from_user=tg_user,
            text="Розпізнані завдання",
        )

        cb_query = CallbackQuery(
            id="cb_q_2",
            from_user=tg_user,
            chat_instance="ci_2",
            message=cb_msg,
            data=cb_data,
        )

        await dp.feed_update(bot=mock_bot, update=Update(update_id=302, callback_query=cb_query))

        # Check zero tasks persisted to DB
        stmt = select(Task).where(Task.user_id == telegram_id)
        saved = list((await db_session.execute(stmt)).scalars().all())
        assert len(saved) == 0

        # Check bot edited message text to cancellation text
        edit_calls = [
            call.args[0]
            for call in mock_bot.call_args_list
            if call.args and isinstance(call.args[0], EditMessageText)
        ]
        assert len(edit_calls) == 1
        assert edit_calls[0].text == "🗑️ <b>Завдання скасовано та видалено.</b>"
        assert edit_calls[0].reply_markup is None

        # Check FSM cleared
        cleared_state = await dp.storage.get_state(key=key)
        assert cleared_state is None


# ==============================================================================
# Tomorrow Planning Mode Tests (Issue #26)
# ==============================================================================


def test_evening_summary_and_plan_tomorrow_keyboards_and_exports() -> None:
    """Verifies Issue #26: PlanTomorrowCallback, evening summary & cancel keyboards, and __init__ exports."""
    assert ExportedPlanTomorrowCallback is PlanTomorrowCallback
    assert exported_get_evening_summary_keyboard is get_evening_summary_keyboard
    assert exported_get_plan_tomorrow_cancel_keyboard is get_plan_tomorrow_cancel_keyboard

    kb_webapp = get_evening_summary_keyboard(user_id=9001, webapp_url="https://tma.example.com")
    assert len(kb_webapp.inline_keyboard) == 1
    assert len(kb_webapp.inline_keyboard[0]) == 2
    assert kb_webapp.inline_keyboard[0][0].text == "📝 План на завтра"
    start_cb = PlanTomorrowCallback.unpack(kb_webapp.inline_keyboard[0][0].callback_data)
    assert start_cb.action == "start"
    assert start_cb.user_id == 9001
    assert kb_webapp.inline_keyboard[0][1].text == "🚀 Відкрити план"
    assert kb_webapp.inline_keyboard[0][1].web_app.url == "https://tma.example.com"

    kb_fallback = get_evening_summary_keyboard(user_id=9001, webapp_url=None)
    assert kb_fallback.inline_keyboard[0][1].callback_data == "open_plan"

    kb_cancel = get_plan_tomorrow_cancel_keyboard(user_id=9001)
    assert len(kb_cancel.inline_keyboard) == 1
    assert len(kb_cancel.inline_keyboard[0]) == 1
    assert kb_cancel.inline_keyboard[0][0].text == "❌ Скасувати"
    cancel_cb = PlanTomorrowCallback.unpack(kb_cancel.inline_keyboard[0][0].callback_data)
    assert cancel_cb.action == "cancel"
    assert cancel_cb.user_id == 9001


@pytest.mark.asyncio
async def test_plan_tomorrow_start_cancel_and_tenant_isolation(
    db_session: AsyncSession,
) -> None:
    """Verifies Issue #26: start sets planning_tomorrow preserving analytics msg, cancel clears FSM, tenant mismatches rejected."""
    owner_id = 91001
    attacker_id = 99991
    db_user = User(telegram_id=owner_id, timezone="Europe/Kyiv")
    db_session.add(db_user)
    await db_session.commit()

    state, _ = create_fsm_context(user_id=owner_id, chat_id=owner_id)
    summary_msg = AsyncMock(spec=Message)
    summary_msg.answer = AsyncMock()
    summary_msg.edit_text = AsyncMock()

    # 1. Tenant mismatch on start is rejected with alert and leaves state untouched
    attacker_cb = AsyncMock(spec=CallbackQuery)
    attacker_cb.from_user = TgUser(id=attacker_id, is_bot=False, first_name="Attacker")
    attacker_cb.message = summary_msg
    attacker_cb.answer = AsyncMock()
    await plan_tomorrow_callback(
        callback_query=attacker_cb,
        callback_data=PlanTomorrowCallback(action="start", user_id=owner_id),
        session=db_session,
        state=state,
    )
    attacker_cb.answer.assert_called_once()
    assert attacker_cb.answer.call_args.kwargs.get("show_alert") is True
    assert await state.get_state() is None
    summary_msg.answer.assert_not_called()

    # 2. Owner taps [📝 План на завтра]
    owner_cb = AsyncMock(spec=CallbackQuery)
    owner_cb.from_user = TgUser(id=owner_id, is_bot=False, first_name="Owner")
    owner_cb.message = summary_msg
    owner_cb.answer = AsyncMock()
    await plan_tomorrow_callback(
        callback_query=owner_cb,
        callback_data=PlanTomorrowCallback(action="start", user_id=owner_id),
        session=db_session,
        state=state,
    )

    assert await state.get_state() == TaskIngestionState.planning_tomorrow.state
    owner_cb.answer.assert_called_once_with()
    # Original analytics summary message must NOT be edited
    summary_msg.edit_text.assert_not_called()
    summary_msg.answer.assert_called_once()
    expected_tomorrow = (get_user_local_time(db_user).date() + timedelta(days=1)).strftime("%d.%m.%Y")
    prompt_text = summary_msg.answer.call_args.kwargs["text"]
    assert f"🎙️ <b>Планування на завтра ({expected_tomorrow})</b>" in prompt_text
    prompt_kb = summary_msg.answer.call_args.kwargs["reply_markup"]
    assert prompt_kb.inline_keyboard[0][0].text == "❌ Скасувати"

    # 3. Tenant mismatch on cancel is rejected with alert and preserves planning_tomorrow state
    attacker_cancel_cb = AsyncMock(spec=CallbackQuery)
    attacker_cancel_cb.from_user = TgUser(id=attacker_id, is_bot=False, first_name="Attacker")
    attacker_cancel_cb.message = summary_msg
    attacker_cancel_cb.answer = AsyncMock()
    await plan_tomorrow_callback(
        callback_query=attacker_cancel_cb,
        callback_data=PlanTomorrowCallback(action="cancel", user_id=owner_id),
        session=db_session,
        state=state,
    )
    assert attacker_cancel_cb.answer.call_args.kwargs.get("show_alert") is True
    assert await state.get_state() == TaskIngestionState.planning_tomorrow.state

    # 4. Owner taps [❌ Скасувати]
    prompt_msg = AsyncMock(spec=Message)
    prompt_msg.edit_text = AsyncMock()
    owner_cancel_cb = AsyncMock(spec=CallbackQuery)
    owner_cancel_cb.from_user = TgUser(id=owner_id, is_bot=False, first_name="Owner")
    owner_cancel_cb.message = prompt_msg
    owner_cancel_cb.answer = AsyncMock()
    await plan_tomorrow_callback(
        callback_query=owner_cancel_cb,
        callback_data=PlanTomorrowCallback(action="cancel", user_id=owner_id),
        session=db_session,
        state=state,
    )
    assert await state.get_state() is None
    prompt_msg.edit_text.assert_called_once()
    assert prompt_msg.edit_text.call_args.kwargs["reply_markup"] is None
    owner_cancel_cb.answer.assert_called_once_with("Скасовано!")


@pytest.mark.asyncio
async def test_voice_and_text_in_planning_tomorrow_mode_pass_tomorrow_date(
    db_session: AsyncSession,
) -> None:
    """Verifies Issue #26: voice & text handlers pass default_target_date=tomorrow when in planning_tomorrow."""
    user_id = 91002
    db_user = User(telegram_id=user_id, timezone="America/New_York")
    db_session.add(db_user)
    await db_session.commit()

    expected_tomorrow = get_user_local_time(db_user).date() + timedelta(days=1)
    extracted = [
        ExtractedTask(
            title="Підготувати звіт",
            target_date=expected_tomorrow,
            priority=TaskPriority.high,
        )
    ]

    # Voice in planning_tomorrow mode
    voice_state, _ = create_fsm_context(user_id=user_id, chat_id=user_id)
    await voice_state.set_state(TaskIngestionState.planning_tomorrow)
    bot_voice = AsyncMock(spec=Bot)
    bot_voice.send_chat_action = AsyncMock()

    async def fake_download(file_id: str, destination: io.BytesIO) -> None:
        destination.write(b"tomorrow_voice_bytes")

    bot_voice.download = AsyncMock(side_effect=fake_download)
    voice_msg = AsyncMock(spec=Message)
    voice_msg.from_user = TgUser(id=user_id, is_bot=False, first_name="VoiceTomorrow")
    voice_msg.chat = Chat(id=user_id, type="private")
    voice_msg.voice = Voice(file_id="vf_tmr", file_unique_id="vu_tmr", duration=4)
    voice_msg.answer = AsyncMock()

    with patch(
        "src.bot.handlers.voice_text.parse_tasks_from_audio",
        new_callable=AsyncMock,
        return_value=extracted,
    ) as mock_audio_parse:
        await handle_voice_message(voice_msg, bot_voice, db_session, voice_state)
        mock_audio_parse.assert_called_once_with(
            audio_bytes=b"tomorrow_voice_bytes",
            user_timezone="America/New_York",
            default_target_date=expected_tomorrow,
        )
    assert await voice_state.get_state() == TaskIngestionState.waiting_confirmation.state
    assert (await voice_state.get_data())["from_tomorrow_plan"] is True

    # Text in planning_tomorrow mode
    text_state, _ = create_fsm_context(user_id=user_id, chat_id=user_id)
    await text_state.set_state(TaskIngestionState.planning_tomorrow)
    bot_text = AsyncMock(spec=Bot)
    bot_text.send_chat_action = AsyncMock()
    text_msg = AsyncMock(spec=Message)
    text_msg.from_user = TgUser(id=user_id, is_bot=False, first_name="TextTomorrow")
    text_msg.chat = Chat(id=user_id, type="private")
    text_msg.text = "Підготувати звіт"
    text_msg.answer = AsyncMock()

    with patch(
        "src.bot.handlers.voice_text.parse_tasks_from_text",
        new_callable=AsyncMock,
        return_value=extracted,
    ) as mock_text_parse:
        await handle_text_message(text_msg, bot_text, db_session, text_state)
        mock_text_parse.assert_called_once_with(
            text="Підготувати звіт",
            user_timezone="America/New_York",
            default_target_date=expected_tomorrow,
        )
    assert await text_state.get_state() == TaskIngestionState.waiting_confirmation.state
    assert (await text_state.get_data())["from_tomorrow_plan"] is True


@pytest.mark.asyncio
async def test_planning_tomorrow_empty_extraction_keeps_planning_state(
    db_session: AsyncSession,
) -> None:
    """Verifies Issue #26: empty voice/text extraction while in planning_tomorrow replies EMPTY_TASKS_NOTIFICATION and retains planning_tomorrow."""
    user_id = 91003
    db_session.add(User(telegram_id=user_id, timezone="Europe/Kyiv"))
    await db_session.commit()

    state, _ = create_fsm_context(user_id=user_id, chat_id=user_id)
    await state.set_state(TaskIngestionState.planning_tomorrow)

    bot = AsyncMock(spec=Bot)
    bot.send_chat_action = AsyncMock()
    bot.download = AsyncMock()

    # Empty text extraction
    text_msg = AsyncMock(spec=Message)
    text_msg.from_user = TgUser(id=user_id, is_bot=False, first_name="EmptyTomorrow")
    text_msg.chat = Chat(id=user_id, type="private")
    text_msg.text = "ммм ну не знаю"
    text_msg.answer = AsyncMock()

    with patch(
        "src.bot.handlers.voice_text.parse_tasks_from_text",
        new_callable=AsyncMock,
        return_value=[],
    ):
        await handle_text_message(text_msg, bot, db_session, state)
    text_msg.answer.assert_called_once_with(text=EMPTY_TASKS_NOTIFICATION)
    assert await state.get_state() == TaskIngestionState.planning_tomorrow.state

    # Empty voice extraction
    voice_msg = AsyncMock(spec=Message)
    voice_msg.from_user = TgUser(id=user_id, is_bot=False, first_name="EmptyTomorrow")
    voice_msg.chat = Chat(id=user_id, type="private")
    voice_msg.voice = Voice(file_id="vf_empty", file_unique_id="vu_empty", duration=2)
    voice_msg.answer = AsyncMock()

    with patch(
        "src.bot.handlers.voice_text.parse_tasks_from_audio",
        new_callable=AsyncMock,
        return_value=[],
    ):
        await handle_voice_message(voice_msg, bot, db_session, state)
    voice_msg.answer.assert_called_once_with(text=EMPTY_TASKS_NOTIFICATION)
    assert await state.get_state() == TaskIngestionState.planning_tomorrow.state


@pytest.mark.asyncio
async def test_dispatcher_planning_tomorrow_edit_restores_state_then_saves(
    db_session: AsyncSession,
) -> None:
    """Verifies Issue #26: full dispatcher flow: start -> text -> [✏️ Виправити] restores planning_tomorrow -> revised text -> [✅ Зберегти] saves & clears FSM."""
    bind = db_session.bind
    session_factory = async_sessionmaker(bind=bind, expire_on_commit=False, class_=AsyncSession)
    dp = create_dispatcher(sessionmaker=session_factory)

    telegram_id = 91004
    db_user = User(telegram_id=telegram_id, timezone="Europe/Kyiv")
    db_session.add(db_user)
    await db_session.commit()

    expected_tomorrow = get_user_local_time(db_user).date() + timedelta(days=1)
    tg_user = TgUser(id=telegram_id, is_bot=False, first_name="TomorrowFlow")
    chat = Chat(id=telegram_id, type="private")
    key = StorageKey(bot_id=1, chat_id=telegram_id, user_id=telegram_id)

    mock_bot = AsyncMock(spec=Bot)
    mock_bot.id = 1
    mock_bot.send_chat_action = AsyncMock()

    # 1. Tap [📝 План на завтра]
    start_cb = CallbackQuery(
        id="cb_start_tmr",
        from_user=tg_user,
        chat_instance="ci_tmr",
        message=Message(
            message_id=401,
            date=datetime.now(timezone.utc),
            chat=chat,
            from_user=tg_user,
            text="🌙 Підсумки дня",
        ),
        data=PlanTomorrowCallback(action="start", user_id=telegram_id).pack(),
    )
    await dp.feed_update(bot=mock_bot, update=Update(update_id=401, callback_query=start_cb))
    assert await dp.storage.get_state(key=key) == TaskIngestionState.planning_tomorrow.state

    # 2. Send initial text draft
    draft1 = [ExtractedTask(title="Перший варіант", target_date=expected_tomorrow)]
    with patch(
        "src.bot.handlers.voice_text.parse_tasks_from_text",
        new_callable=AsyncMock,
        return_value=draft1,
    ) as mock_parse1:
        msg1 = Message(
            message_id=402,
            date=datetime.now(timezone.utc),
            chat=chat,
            from_user=tg_user,
            text="Перший варіант",
        )
        await dp.feed_update(bot=mock_bot, update=Update(update_id=402, message=msg1))
        mock_parse1.assert_called_once_with(
            text="Перший варіант",
            user_timezone="Europe/Kyiv",
            default_target_date=expected_tomorrow,
        )
    assert await dp.storage.get_state(key=key) == TaskIngestionState.waiting_confirmation.state

    # 3. Tap [✏️ Виправити] -> must clear pending_tasks AND restore planning_tomorrow
    edit_cb = CallbackQuery(
        id="cb_edit_tmr",
        from_user=tg_user,
        chat_instance="ci_tmr",
        message=Message(
            message_id=403,
            date=datetime.now(timezone.utc),
            chat=chat,
            from_user=tg_user,
            text="Розпізнані завдання",
        ),
        data=TaskConfirmCallback(action="edit", user_id=telegram_id).pack(),
    )
    await dp.feed_update(bot=mock_bot, update=Update(update_id=403, callback_query=edit_cb))
    assert await dp.storage.get_state(key=key) == TaskIngestionState.planning_tomorrow.state
    assert "pending_tasks" not in (await dp.storage.get_data(key=key))

    # 4. Send revised text -> must STILL receive default_target_date=expected_tomorrow
    draft2 = [ExtractedTask(title="Фінальна задача на завтра", target_date=expected_tomorrow)]
    with patch(
        "src.bot.handlers.voice_text.parse_tasks_from_text",
        new_callable=AsyncMock,
        return_value=draft2,
    ) as mock_parse2:
        msg2 = Message(
            message_id=404,
            date=datetime.now(timezone.utc),
            chat=chat,
            from_user=tg_user,
            text="Фінальна задача на завтра",
        )
        await dp.feed_update(bot=mock_bot, update=Update(update_id=404, message=msg2))
        mock_parse2.assert_called_once_with(
            text="Фінальна задача на завтра",
            user_timezone="Europe/Kyiv",
            default_target_date=expected_tomorrow,
        )

    # 5. Tap [✅ Зберегти] -> saves task for tomorrow and clears FSM state
    save_cb = CallbackQuery(
        id="cb_save_tmr",
        from_user=tg_user,
        chat_instance="ci_tmr",
        message=Message(
            message_id=405,
            date=datetime.now(timezone.utc),
            chat=chat,
            from_user=tg_user,
            text="Розпізнані завдання",
        ),
        data=TaskConfirmCallback(action="save", user_id=telegram_id).pack(),
    )
    await dp.feed_update(bot=mock_bot, update=Update(update_id=405, callback_query=save_cb))

    assert await dp.storage.get_state(key=key) is None
    saved_tasks = list(
        (await db_session.execute(select(Task).where(Task.user_id == telegram_id))).scalars().all()
    )
    assert len(saved_tasks) == 1
    assert saved_tasks[0].title == "Фінальна задача на завтра"
    assert saved_tasks[0].target_date == expected_tomorrow
    assert saved_tasks[0].status == TaskStatus.todo

    # Verify SendMessage was emitted for the planning prompt
    send_calls = [
        call.args[0]
        for call in mock_bot.call_args_list
        if call.args and isinstance(call.args[0], SendMessage)
    ]
    assert any("Планування на завтра" in c.text for c in send_calls)


@pytest.mark.asyncio
async def test_planning_tomorrow_delete_discards_and_clears_fsm(
    db_session: AsyncSession,
) -> None:
    """Verifies Issue #26: [🗑️ Видалити] on a tomorrow-planning draft discards tasks and clears FSM state completely."""
    user_id = 91005
    state, _ = create_fsm_context(user_id=user_id, chat_id=user_id)
    await state.set_state(TaskIngestionState.waiting_confirmation)
    await state.update_data(
        pending_tasks=[{"title": "Скасувати завтра", "target_date": "2026-11-22"}],
        from_tomorrow_plan=True,
    )

    msg = AsyncMock(spec=Message)
    msg.edit_text = AsyncMock()
    cb = AsyncMock(spec=CallbackQuery)
    cb.from_user = TgUser(id=user_id, is_bot=False, first_name="DeleteTomorrow")
    cb.message = msg
    cb.answer = AsyncMock()

    await task_confirm_callback(
        callback_query=cb,
        callback_data=TaskConfirmCallback(action="delete", user_id=user_id),
        session=db_session,
        state=state,
    )

    assert await state.get_state() is None
    assert (await state.get_data()) == {}
    msg.edit_text.assert_called_once_with(
        text="🗑️ <b>Завдання скасовано та видалено.</b>",
        reply_markup=None,
    )
    cb.answer.assert_called_once_with("Скасовано!")
    saved = list((await db_session.execute(select(Task).where(Task.user_id == user_id))).scalars().all())
    assert len(saved) == 0
