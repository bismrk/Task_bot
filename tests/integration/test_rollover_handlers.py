"""Integration tests for midnight rollover dialogue and callback handlers."""

from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
from aiogram import Bot
from aiogram.types import CallbackQuery, Chat, InlineKeyboardMarkup, Message, Update, User as TgUser
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.bot.dispatcher import create_dispatcher
from src.bot.handlers.rollover import (
    ALL_PROCESSED_TEXT,
    FOLLOW_UP_PROMPT_TEXT,
    TASK_ALREADY_PROCESSED_ALERT,
    TENANT_SECURITY_ALERT,
    format_overdue_task_item,
    handle_rollover_callback,
    send_midnight_rollover_dialogue,
)
from src.bot.keyboards.rollover import (
    RolloverCallback,
    get_batch_rollover_keyboard,
    get_task_rollover_keyboard,
)
from src.models.task import Task, TaskPriority, TaskStatus
from src.services.task_service import create_task, get_task
from src.services.user_service import get_or_create_user, get_user_local_time
from src.schemas.task import TaskCreate


def create_mock_message() -> AsyncMock:
    """Create an AsyncMock for Message with async edit methods."""
    msg = AsyncMock(spec=Message)
    msg.edit_text = AsyncMock()
    msg.edit_reply_markup = AsyncMock()
    return msg


# ==============================================================================
# Keyboard & Formatter Tests
# ==============================================================================


def test_get_task_rollover_keyboard_structure() -> None:
    """Verifies REQ-SCH-01: get_task_rollover_keyboard returns max 2 buttons per row with correct callbacks."""
    task_id = 42
    user_id = 12345
    kb = get_task_rollover_keyboard(task_id=task_id, user_id=user_id)

    assert isinstance(kb, InlineKeyboardMarkup)
    assert len(kb.inline_keyboard) == 1
    row = kb.inline_keyboard[0]
    assert len(row) <= 2
    assert len(row) == 2

    btn_postpone = row[0]
    assert btn_postpone.text == "⏩ Перенести на сьогодні"
    data_postpone = RolloverCallback.unpack(btn_postpone.callback_data)
    assert data_postpone.action == "postpone"
    assert data_postpone.task_id == task_id
    assert data_postpone.user_id == user_id

    btn_close = row[1]
    assert btn_close.text == "❌ Закрити"
    data_close = RolloverCallback.unpack(btn_close.callback_data)
    assert data_close.action == "close"
    assert data_close.task_id == task_id
    assert data_close.user_id == user_id


def test_get_batch_rollover_keyboard_structure() -> None:
    """Verifies REQ-SCH-01: get_batch_rollover_keyboard returns max 2 buttons per row with correct callbacks."""
    user_id = 12345
    kb = get_batch_rollover_keyboard(user_id=user_id)

    assert isinstance(kb, InlineKeyboardMarkup)
    assert len(kb.inline_keyboard) == 1
    row = kb.inline_keyboard[0]
    assert len(row) <= 2
    assert len(row) == 2

    btn_postpone_all = row[0]
    assert btn_postpone_all.text == "⏩ Перенести всі"
    data_postpone_all = RolloverCallback.unpack(btn_postpone_all.callback_data)
    assert data_postpone_all.action == "postpone_all"
    assert data_postpone_all.task_id is None
    assert data_postpone_all.user_id == user_id

    btn_close_all = row[1]
    assert btn_close_all.text == "❌ Закрити всі"
    data_close_all = RolloverCallback.unpack(btn_close_all.callback_data)
    assert data_close_all.action == "close_all"
    assert data_close_all.task_id is None
    assert data_close_all.user_id == user_id


def test_format_overdue_task_item_formatting() -> None:
    """Verifies REQ-SCH-01: format_overdue_task_item formats task with title, priority, tag, and target date."""
    task_high = Task(
        id=1,
        user_id=100,
        title="Звіт для директора",
        priority=TaskPriority.high,
        tag="робота",
        target_date=date(2026, 11, 19),
        status=TaskStatus.todo,
    )
    formatted_high = format_overdue_task_item(task_high)
    assert "Звіт для директора" in formatted_high
    assert "⚠️ Високий" in formatted_high
    assert "🏷️ #робота" in formatted_high
    assert "📅 2026-11-19" in formatted_high

    task_medium = Task(
        id=2,
        user_id=100,
        title="Купити молоко",
        priority=TaskPriority.medium,
        tag="#покупки",
        target_date=date(2026, 11, 18),
        status=TaskStatus.todo,
    )
    formatted_medium = format_overdue_task_item(task_medium)
    assert "Купити молоко" in formatted_medium
    assert "⚡ Середній" in formatted_medium
    assert "🏷️ #покупки" in formatted_medium
    assert "📅 2026-11-18" in formatted_medium

    task_low = Task(
        id=3,
        user_id=100,
        title="Прочитати статтю",
        priority=TaskPriority.low,
        tag=None,
        target_date=date(2026, 11, 17),
        status=TaskStatus.todo,
    )
    formatted_low = format_overdue_task_item(task_low)
    assert "Прочитати статтю" in formatted_low
    assert "💤 Низький" in formatted_low
    assert "🏷️" not in formatted_low
    assert "📅 2026-11-17" in formatted_low


# ==============================================================================
# send_midnight_rollover_dialogue Tests (REQ-SCH-01, REQ-NFR-02)
# ==============================================================================


@pytest.mark.asyncio
async def test_send_midnight_rollover_dialogue_zero_overdue_tasks(db_session: AsyncSession) -> None:
    """Verifies REQ-SCH-01: Zero overdue tasks sends single congratulatory message with no keyboard."""
    user, _ = await get_or_create_user(db_session, telegram_id=1001, timezone="Europe/Kyiv")

    bot = AsyncMock(spec=Bot)
    mock_sent_msg = create_mock_message()
    bot.send_message.return_value = mock_sent_msg

    messages = await send_midnight_rollover_dialogue(
        bot=bot,
        session=db_session,
        user=user,
        reference_date=date(2026, 11, 20),
    )

    assert len(messages) == 1
    assert messages[0] == mock_sent_msg
    bot.send_message.assert_called_once()
    kwargs = bot.send_message.call_args[1]
    assert kwargs["chat_id"] == 1001
    assert "Всі вчорашні завдання виконано!" in kwargs["text"]
    assert "reply_markup" not in kwargs or kwargs["reply_markup"] is None


@pytest.mark.asyncio
async def test_send_midnight_rollover_dialogue_multiple_overdue_tasks(db_session: AsyncSession) -> None:
    """Verifies REQ-SCH-01: Multiple overdue tasks sends overview batch message and per-task messages."""
    user, _ = await get_or_create_user(db_session, telegram_id=1002, timezone="Europe/Kyiv")

    # Create overdue tasks (target_date < 2026-11-20)
    await create_task(
        db_session,
        user_id=user.telegram_id,
        data=TaskCreate(title="Overdue Task 1", target_date=date(2026, 11, 18), priority=TaskPriority.high),
    )
    await create_task(
        db_session,
        user_id=user.telegram_id,
        data=TaskCreate(title="Overdue Task 2", target_date=date(2026, 11, 19), priority=TaskPriority.medium),
    )
    # Today task (not overdue)
    await create_task(
        db_session,
        user_id=user.telegram_id,
        data=TaskCreate(title="Today Task", target_date=date(2026, 11, 20), priority=TaskPriority.low),
    )

    bot = AsyncMock(spec=Bot)
    mock_overview_msg = create_mock_message()
    mock_task1_msg = create_mock_message()
    mock_task2_msg = create_mock_message()
    bot.send_message.side_effect = [mock_overview_msg, mock_task1_msg, mock_task2_msg]

    messages = await send_midnight_rollover_dialogue(
        bot=bot,
        session=db_session,
        user=user,
        reference_date=date(2026, 11, 20),
    )

    assert len(messages) == 3
    assert messages == [mock_overview_msg, mock_task1_msg, mock_task2_msg]
    assert bot.send_message.call_count == 3

    # Check overview message call
    call1_kwargs = bot.send_message.call_args_list[0][1]
    assert call1_kwargs["chat_id"] == 1002
    assert "Невиконані завдання за вчора" in call1_kwargs["text"]
    assert "2 невиконаних завдань" in call1_kwargs["text"]
    assert isinstance(call1_kwargs["reply_markup"], InlineKeyboardMarkup)
    assert call1_kwargs["reply_markup"].inline_keyboard[0][0].text == "⏩ Перенести всі"

    # Check task 1 call
    call2_kwargs = bot.send_message.call_args_list[1][1]
    assert call2_kwargs["chat_id"] == 1002
    assert "Overdue Task 1" in call2_kwargs["text"]
    assert isinstance(call2_kwargs["reply_markup"], InlineKeyboardMarkup)
    assert call2_kwargs["reply_markup"].inline_keyboard[0][0].text == "⏩ Перенести на сьогодні"

    # Check task 2 call
    call3_kwargs = bot.send_message.call_args_list[2][1]
    assert call3_kwargs["chat_id"] == 1002
    assert "Overdue Task 2" in call3_kwargs["text"]


@pytest.mark.asyncio
async def test_send_midnight_rollover_dialogue_respects_reference_date(db_session: AsyncSession) -> None:
    """Verifies REQ-SCH-01: send_midnight_rollover_dialogue respects reference_date for deterministic tests."""
    user, _ = await get_or_create_user(db_session, telegram_id=1003, timezone="Europe/Kyiv")

    # Task for 2026-11-15
    await create_task(
        db_session,
        user_id=user.telegram_id,
        data=TaskCreate(title="Task Nov 15", target_date=date(2026, 11, 15)),
    )

    bot = AsyncMock(spec=Bot)
    mock_msg = create_mock_message()
    bot.send_message.return_value = mock_msg

    # If reference_date is Nov 10, task is NOT overdue
    messages_early = await send_midnight_rollover_dialogue(
        bot=bot,
        session=db_session,
        user=user,
        reference_date=date(2026, 11, 10),
    )
    assert len(messages_early) == 1
    assert "Всі вчорашні завдання виконано!" in bot.send_message.call_args[1]["text"]

    bot.send_message.reset_mock()
    # If reference_date is Nov 16, task IS overdue
    messages_late = await send_midnight_rollover_dialogue(
        bot=bot,
        session=db_session,
        user=user,
        reference_date=date(2026, 11, 16),
    )
    assert len(messages_late) == 2
    assert "Невиконані завдання за вчора" in bot.send_message.call_args_list[0][1]["text"]


# ==============================================================================
# Callback Query Handlers Tests (REQ-SCH-01, REQ-TSK-01, REQ-TSK-02, REQ-NFR-02)
# ==============================================================================


@pytest.mark.asyncio
async def test_handle_rollover_callback_none_safety(db_session: AsyncSession) -> None:
    """Verifies REQ-SCH-01: handle_rollover_callback safely returns if from_user is None or message is not Message."""
    bot = AsyncMock(spec=Bot)
    callback_data = RolloverCallback(action="postpone", task_id=1, user_id=100)

    # None from_user
    q1 = AsyncMock(spec=CallbackQuery)
    q1.from_user = None
    q1.message = create_mock_message()
    await handle_rollover_callback(q1, callback_data, bot, db_session)
    q1.answer.assert_not_called()

    # message is not Message (e.g. InaccessibleMessage)
    q2 = AsyncMock(spec=CallbackQuery)
    q2.from_user = TgUser(id=100, is_bot=False, first_name="User")
    q2.message = "not a message object"
    await handle_rollover_callback(q2, callback_data, bot, db_session)
    q2.answer.assert_not_called()


@pytest.mark.asyncio
async def test_handle_rollover_callback_tenant_security(db_session: AsyncSession) -> None:
    """Verifies REQ-NFR-02: Callback query from unauthorized user triggers alert and leaves DB unchanged."""
    owner_id = 2001
    attacker_id = 9999

    user, _ = await get_or_create_user(db_session, telegram_id=owner_id, timezone="Europe/Kyiv")
    local_today = get_user_local_time(user).date()
    yesterday = local_today - timedelta(days=1)

    task = await create_task(
        db_session,
        user_id=owner_id,
        data=TaskCreate(title="Secret Task", target_date=yesterday),
    )

    mock_msg = create_mock_message()
    query = AsyncMock(spec=CallbackQuery)
    query.from_user = TgUser(id=attacker_id, is_bot=False, first_name="Attacker")
    query.message = mock_msg
    query.answer = AsyncMock()

    bot = AsyncMock(spec=Bot)
    callback_data = RolloverCallback(action="postpone", task_id=task.id, user_id=owner_id)

    await handle_rollover_callback(query, callback_data, bot, db_session)

    # Alert shown
    query.answer.assert_called_once_with(TENANT_SECURITY_ALERT, show_alert=True)
    # Message untouched
    mock_msg.edit_text.assert_not_called()
    mock_msg.edit_reply_markup.assert_not_called()
    bot.send_message.assert_not_called()

    # DB untouched
    db_task = await get_task(db_session, task.id, owner_id)
    assert db_task.target_date == yesterday


@pytest.mark.asyncio
async def test_single_task_postpone_with_remaining_tasks(db_session: AsyncSession) -> None:
    """Verifies REQ-SCH-01, REQ-TSK-01: Postpone single task updates target_date, edits message, but no follow-up if tasks remain."""
    user_id = 3001
    user, _ = await get_or_create_user(db_session, telegram_id=user_id, timezone="Europe/Kyiv")
    local_today = get_user_local_time(user).date()
    yesterday = local_today - timedelta(days=1)

    task1 = await create_task(db_session, user_id, TaskCreate(title="Task 1", target_date=yesterday))
    await create_task(db_session, user_id, TaskCreate(title="Task 2", target_date=yesterday))

    mock_msg = create_mock_message()
    query = AsyncMock(spec=CallbackQuery)
    query.from_user = TgUser(id=user_id, is_bot=False, first_name="User")
    query.message = mock_msg
    query.answer = AsyncMock()

    bot = AsyncMock(spec=Bot)
    callback_data = RolloverCallback(action="postpone", task_id=task1.id, user_id=user_id)

    await handle_rollover_callback(query, callback_data, bot, db_session)

    # 1. DB updated
    db_task1 = await get_task(db_session, task1.id, user_id)
    assert db_task1.target_date == local_today

    # 2. Message edited & keyboard removed
    mock_msg.edit_text.assert_called_once_with(
        text=f"⏩ Завдання «{task1.title}» перенесено на сьогодні!",
        reply_markup=None,
    )

    # 3. Callback answered
    query.answer.assert_called_once_with("Перенесено на сьогодні!")

    # 4. Remaining overdue tasks exist (task2), so follow-up prompt NOT sent
    bot.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_single_task_postpone_last_task_sends_follow_up(db_session: AsyncSession) -> None:
    """Verifies REQ-SCH-01, REQ-TSK-01: Postpone last overdue task sends follow-up prompt to plan today."""
    user_id = 3002
    user, _ = await get_or_create_user(db_session, telegram_id=user_id, timezone="Europe/Kyiv")
    local_today = get_user_local_time(user).date()
    yesterday = local_today - timedelta(days=1)

    task = await create_task(db_session, user_id, TaskCreate(title="Sole Overdue Task", target_date=yesterday))

    mock_msg = create_mock_message()
    query = AsyncMock(spec=CallbackQuery)
    query.from_user = TgUser(id=user_id, is_bot=False, first_name="User")
    query.message = mock_msg
    query.answer = AsyncMock()

    bot = AsyncMock(spec=Bot)
    callback_data = RolloverCallback(action="postpone", task_id=task.id, user_id=user_id)

    await handle_rollover_callback(query, callback_data, bot, db_session)

    # DB updated
    db_task = await get_task(db_session, task.id, user_id)
    assert db_task.target_date == local_today

    # Message edited
    mock_msg.edit_text.assert_called_once_with(
        text=f"⏩ Завдання «{task.title}» перенесено на сьогодні!",
        reply_markup=None,
    )

    # Follow-up prompt sent because remaining overdue tasks == 0
    bot.send_message.assert_called_once_with(
        chat_id=user_id,
        text=FOLLOW_UP_PROMPT_TEXT,
    )


@pytest.mark.asyncio
async def test_single_task_close_with_remaining_tasks(db_session: AsyncSession) -> None:
    """Verifies REQ-SCH-01, REQ-TSK-02: Close single task cancels status, edits message, no follow-up if tasks remain."""
    user_id = 4001
    user, _ = await get_or_create_user(db_session, telegram_id=user_id, timezone="Europe/Kyiv")
    local_today = get_user_local_time(user).date()
    yesterday = local_today - timedelta(days=1)

    task1 = await create_task(db_session, user_id, TaskCreate(title="Close Task 1", target_date=yesterday))
    await create_task(db_session, user_id, TaskCreate(title="Keep Task 2", target_date=yesterday))

    mock_msg = create_mock_message()
    query = AsyncMock(spec=CallbackQuery)
    query.from_user = TgUser(id=user_id, is_bot=False, first_name="User")
    query.message = mock_msg
    query.answer = AsyncMock()

    bot = AsyncMock(spec=Bot)
    callback_data = RolloverCallback(action="close", task_id=task1.id, user_id=user_id)

    await handle_rollover_callback(query, callback_data, bot, db_session)

    # 1. DB updated to canceled
    db_task1 = await get_task(db_session, task1.id, user_id)
    assert db_task1.status == TaskStatus.canceled

    # 2. Message edited
    mock_msg.edit_text.assert_called_once_with(
        text=f"❌ Завдання «{task1.title}» закрито.",
        reply_markup=None,
    )
    query.answer.assert_called_once_with("Завдання закрито!")

    # 3. Task 2 still overdue, no follow up
    bot.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_single_task_close_last_task_sends_follow_up(db_session: AsyncSession) -> None:
    """Verifies REQ-SCH-01, REQ-TSK-02: Close last overdue task sends follow-up prompt to plan today."""
    user_id = 4002
    user, _ = await get_or_create_user(db_session, telegram_id=user_id, timezone="Europe/Kyiv")
    local_today = get_user_local_time(user).date()
    yesterday = local_today - timedelta(days=1)

    task = await create_task(db_session, user_id, TaskCreate(title="Last Task to Close", target_date=yesterday))

    mock_msg = create_mock_message()
    query = AsyncMock(spec=CallbackQuery)
    query.from_user = TgUser(id=user_id, is_bot=False, first_name="User")
    query.message = mock_msg
    query.answer = AsyncMock()

    bot = AsyncMock(spec=Bot)
    callback_data = RolloverCallback(action="close", task_id=task.id, user_id=user_id)

    await handle_rollover_callback(query, callback_data, bot, db_session)

    # DB updated
    db_task = await get_task(db_session, task.id, user_id)
    assert db_task.status == TaskStatus.canceled

    # Follow-up prompt sent
    bot.send_message.assert_called_once_with(
        chat_id=user_id,
        text=FOLLOW_UP_PROMPT_TEXT,
    )


@pytest.mark.asyncio
async def test_batch_postpone_all_success(db_session: AsyncSession) -> None:
    """Verifies REQ-SCH-01: Batch postpone rolls over all overdue tasks to today and sends follow-up prompt."""
    user_id = 5001
    user, _ = await get_or_create_user(db_session, telegram_id=user_id, timezone="Europe/Kyiv")
    local_today = get_user_local_time(user).date()
    yesterday = local_today - timedelta(days=1)

    task1 = await create_task(db_session, user_id, TaskCreate(title="Batch 1", target_date=yesterday))
    task2 = await create_task(db_session, user_id, TaskCreate(title="Batch 2", target_date=yesterday))

    mock_msg = create_mock_message()
    query = AsyncMock(spec=CallbackQuery)
    query.from_user = TgUser(id=user_id, is_bot=False, first_name="User")
    query.message = mock_msg
    query.answer = AsyncMock()

    bot = AsyncMock(spec=Bot)
    callback_data = RolloverCallback(action="postpone_all", task_id=None, user_id=user_id)

    await handle_rollover_callback(query, callback_data, bot, db_session)

    # 1. DB updated
    t1 = await get_task(db_session, task1.id, user_id)
    t2 = await get_task(db_session, task2.id, user_id)
    assert t1.target_date == local_today
    assert t2.target_date == local_today

    # 2. Overview message edited
    mock_msg.edit_text.assert_called_once_with(
        text="⏩ Всі завдання (2) перенесено на сьогодні!",
        reply_markup=None,
    )
    query.answer.assert_called_once_with("Всі завдання перенесено!")

    # 3. Follow-up prompt sent
    bot.send_message.assert_called_once_with(
        chat_id=user_id,
        text=FOLLOW_UP_PROMPT_TEXT,
    )


@pytest.mark.asyncio
async def test_batch_postpone_all_when_no_tasks_remain(db_session: AsyncSession) -> None:
    """Verifies REQ-SCH-01: Batch postpone when no overdue tasks remain edits message and removes keyboard."""
    user_id = 5002
    await get_or_create_user(db_session, telegram_id=user_id, timezone="Europe/Kyiv")

    mock_msg = create_mock_message()
    query = AsyncMock(spec=CallbackQuery)
    query.from_user = TgUser(id=user_id, is_bot=False, first_name="User")
    query.message = mock_msg
    query.answer = AsyncMock()

    bot = AsyncMock(spec=Bot)
    callback_data = RolloverCallback(action="postpone_all", task_id=None, user_id=user_id)

    await handle_rollover_callback(query, callback_data, bot, db_session)

    mock_msg.edit_text.assert_called_once_with(
        text=ALL_PROCESSED_TEXT,
        reply_markup=None,
    )
    query.answer.assert_called_once_with()
    bot.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_batch_close_all_success(db_session: AsyncSession) -> None:
    """Verifies REQ-SCH-01, REQ-TSK-02: Batch close cancels all overdue tasks and sends follow-up prompt."""
    user_id = 6001
    user, _ = await get_or_create_user(db_session, telegram_id=user_id, timezone="Europe/Kyiv")
    local_today = get_user_local_time(user).date()
    yesterday = local_today - timedelta(days=1)

    task1 = await create_task(db_session, user_id, TaskCreate(title="Cancel 1", target_date=yesterday))
    task2 = await create_task(db_session, user_id, TaskCreate(title="Cancel 2", target_date=yesterday))

    mock_msg = create_mock_message()
    query = AsyncMock(spec=CallbackQuery)
    query.from_user = TgUser(id=user_id, is_bot=False, first_name="User")
    query.message = mock_msg
    query.answer = AsyncMock()

    bot = AsyncMock(spec=Bot)
    callback_data = RolloverCallback(action="close_all", task_id=None, user_id=user_id)

    await handle_rollover_callback(query, callback_data, bot, db_session)

    # 1. DB updated
    t1 = await get_task(db_session, task1.id, user_id)
    t2 = await get_task(db_session, task2.id, user_id)
    assert t1.status == TaskStatus.canceled
    assert t2.status == TaskStatus.canceled

    # 2. Overview message edited
    mock_msg.edit_text.assert_called_once_with(
        text="❌ Всі завдання (2) закрито.",
        reply_markup=None,
    )
    query.answer.assert_called_once_with("Всі завдання закрито!")

    # 3. Follow-up prompt sent
    bot.send_message.assert_called_once_with(
        chat_id=user_id,
        text=FOLLOW_UP_PROMPT_TEXT,
    )


@pytest.mark.asyncio
async def test_batch_close_all_when_no_tasks_remain(db_session: AsyncSession) -> None:
    """Verifies REQ-SCH-01, REQ-TSK-02: Batch close when no overdue tasks remain edits message and removes keyboard."""
    user_id = 6002
    await get_or_create_user(db_session, telegram_id=user_id, timezone="Europe/Kyiv")

    mock_msg = create_mock_message()
    query = AsyncMock(spec=CallbackQuery)
    query.from_user = TgUser(id=user_id, is_bot=False, first_name="User")
    query.message = mock_msg
    query.answer = AsyncMock()

    bot = AsyncMock(spec=Bot)
    callback_data = RolloverCallback(action="close_all", task_id=None, user_id=user_id)

    await handle_rollover_callback(query, callback_data, bot, db_session)

    mock_msg.edit_text.assert_called_once_with(
        text=ALL_PROCESSED_TEXT,
        reply_markup=None,
    )
    query.answer.assert_called_once_with()
    bot.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_handle_rollover_callback_missing_or_already_resolved(db_session: AsyncSession) -> None:
    """Verifies REQ-SCH-01: Non-existent or already resolved tasks display alert and remove keyboard safely."""
    user_id = 7001
    user, _ = await get_or_create_user(db_session, telegram_id=user_id, timezone="Europe/Kyiv")
    local_today = get_user_local_time(user).date()

    # 1. Non-existent task ID
    mock_msg1 = create_mock_message()
    q1 = AsyncMock(spec=CallbackQuery)
    q1.from_user = TgUser(id=user_id, is_bot=False, first_name="User")
    q1.message = mock_msg1
    q1.answer = AsyncMock()

    bot = AsyncMock(spec=Bot)
    await handle_rollover_callback(
        q1,
        RolloverCallback(action="postpone", task_id=999999, user_id=user_id),
        bot,
        db_session,
    )
    q1.answer.assert_called_once_with(TASK_ALREADY_PROCESSED_ALERT, show_alert=True)
    mock_msg1.edit_reply_markup.assert_called_once_with(reply_markup=None)

    # 2. Already completed task (status == done)
    done_task = await create_task(
        db_session,
        user_id,
        TaskCreate(title="Done Task", target_date=local_today - timedelta(days=1)),
    )
    done_task.status = TaskStatus.done
    await db_session.commit()

    mock_msg2 = create_mock_message()
    q2 = AsyncMock(spec=CallbackQuery)
    q2.from_user = TgUser(id=user_id, is_bot=False, first_name="User")
    q2.message = mock_msg2
    q2.answer = AsyncMock()

    await handle_rollover_callback(
        q2,
        RolloverCallback(action="close", task_id=done_task.id, user_id=user_id),
        bot,
        db_session,
    )
    q2.answer.assert_called_once_with(TASK_ALREADY_PROCESSED_ALERT, show_alert=True)
    mock_msg2.edit_reply_markup.assert_called_once_with(reply_markup=None)

    # 3. Missing task_id (task_id=None) for single postpone
    mock_msg3 = create_mock_message()
    q3 = AsyncMock(spec=CallbackQuery)
    q3.from_user = TgUser(id=user_id, is_bot=False, first_name="User")
    q3.message = mock_msg3
    q3.answer = AsyncMock()

    await handle_rollover_callback(
        q3,
        RolloverCallback(action="postpone", task_id=None, user_id=user_id),
        bot,
        db_session,
    )
    q3.answer.assert_called_once_with(TASK_ALREADY_PROCESSED_ALERT, show_alert=True)
    mock_msg3.edit_reply_markup.assert_called_once_with(reply_markup=None)


# ==============================================================================
# Full Dispatcher Pipeline Integration Test
# ==============================================================================


@pytest.mark.asyncio
async def test_dispatcher_feed_rollover_callback_pipeline(db_session: AsyncSession) -> None:
    """Verifies REQ-SCH-01, REQ-TSK-01, REQ-NFR-02: Full pipeline: feed_update with RolloverCallback through create_dispatcher."""
    bind = db_session.bind
    session_factory = async_sessionmaker(bind=bind, expire_on_commit=False, class_=AsyncSession)

    dp = create_dispatcher(sessionmaker=session_factory)
    mock_bot = AsyncMock(spec=Bot)
    mock_bot.id = 1
    mock_bot.send_message = AsyncMock()
    mock_bot.edit_message_text = AsyncMock()

    telegram_id = 8001
    user, _ = await get_or_create_user(db_session, telegram_id=telegram_id, timezone="Europe/Kyiv")
    local_today = get_user_local_time(user).date()
    yesterday = local_today - timedelta(days=1)

    task = await create_task(db_session, telegram_id, TaskCreate(title="Pipeline Task", target_date=yesterday))

    tg_user = TgUser(id=telegram_id, is_bot=False, first_name="PipelineUser")
    chat = Chat(id=telegram_id, type="private")

    mock_msg = Message(
        message_id=301,
        date=datetime.now(timezone.utc),
        chat=chat,
        from_user=tg_user,
        text="Overdue task message",
    )

    cb_data = RolloverCallback(action="postpone", task_id=task.id, user_id=telegram_id).pack()
    cb_query = CallbackQuery(
        id="cb_q_roll_1",
        from_user=tg_user,
        chat_instance="ci_roll_1",
        message=mock_msg,
        data=cb_data,
    )

    await dp.feed_update(bot=mock_bot, update=Update(update_id=301, callback_query=cb_query))

    # Task updated in DB
    await db_session.refresh(task)
    assert task.target_date == local_today

    # Follow-up sent (it was the only overdue task)
    mock_bot.send_message.assert_called_once_with(
        chat_id=telegram_id,
        text=FOLLOW_UP_PROMPT_TEXT,
    )
