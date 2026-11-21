"""Automated integration tests for deadline notification reminders (-1h and -10m).

Verifies:
- REQ-SCH-03: Automated background deadline monitoring at -1h and -10m thresholds.
- REQ-NFR-02: Strict tenant isolation and per-task exception isolation.
- REQ-NFR-03: Restart-resilient database idempotency tracking via reminder flags.
- REQ-TSK-02: Interactive task completion and snooze callback actions.
"""

from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message, User as TgUser
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.bot.handlers.deadline import deadline_callback_handler
from src.bot.keyboards.deadline import DeadlineCallback, get_deadline_keyboard
from src.models.task import Task, TaskPriority, TaskStatus
from src.models.user import User
from src.scheduler.jobs import run_deadline_checks
from src.scheduler.manager import setup_scheduler


@pytest.fixture
def mock_bot() -> AsyncMock:
    """Provide a mock aiogram Bot instance with async send_message."""
    bot = AsyncMock(spec=Bot)
    bot.send_message = AsyncMock(return_value=AsyncMock(message_id=100))
    return bot


@pytest.fixture
def session_factory(db_session: AsyncSession) -> async_sessionmaker[AsyncSession]:
    """Provide an async_sessionmaker bound to the test database engine."""
    engine = db_session.bind
    return async_sessionmaker(
        bind=engine,
        expire_on_commit=False,
        class_=AsyncSession,
    )


def create_mock_message() -> AsyncMock:
    """Create an AsyncMock for Telegram Message with async edit methods."""
    msg = AsyncMock(spec=Message)
    msg.edit_text = AsyncMock()
    msg.edit_reply_markup = AsyncMock()
    return msg


# ==============================================================================
# Keyboard & Callback Schema Unit Tests (REQ-SCH-03)
# ==============================================================================


def test_get_deadline_keyboard_structure() -> None:
    """Verifies REQ-SCH-03: get_deadline_keyboard returns max 2 buttons per row with valid callbacks."""
    task_id = 42
    user_id = 999
    kb = get_deadline_keyboard(task_id=task_id, user_id=user_id, snooze_minutes=15)

    assert isinstance(kb, InlineKeyboardMarkup)
    assert len(kb.inline_keyboard) == 1
    row = kb.inline_keyboard[0]
    assert len(row) <= 2
    assert len(row) == 2

    done_btn = row[0]
    assert done_btn.text == "✅ Виконано"
    done_data = DeadlineCallback.unpack(done_btn.callback_data)
    assert done_data.action == "done"
    assert done_data.task_id == task_id
    assert done_data.user_id == user_id

    snooze_btn = row[1]
    assert snooze_btn.text == "⏰ +15 хв"
    snooze_data = DeadlineCallback.unpack(snooze_btn.callback_data)
    assert snooze_data.action == "snooze"
    assert snooze_data.task_id == task_id
    assert snooze_data.user_id == user_id
    assert snooze_data.minutes == 15


# ==============================================================================
# Proximity Trigger Tests (REQ-SCH-03, REQ-NFR-03)
# ==============================================================================


@pytest.mark.asyncio
async def test_1h_proximity_trigger(
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    mock_bot: AsyncMock,
) -> None:
    """Verifies REQ-SCH-03: Task nearing deadline within 1 hour triggers 1h reminder."""
    user = User(telegram_id=101, timezone="Europe/Kyiv")
    db_session.add(user)
    await db_session.commit()

    now_utc = datetime(2026, 11, 21, 14, 0, 0, tzinfo=timezone.utc)
    # Deadline in 50 minutes (delta = 3000 sec, within 600 < delta <= 3600)
    deadline_utc = now_utc + timedelta(minutes=50)

    task = Task(
        user_id=user.telegram_id,
        title="Здати квартальний звіт",
        target_date=now_utc.date(),
        deadline_at=deadline_utc,
        priority=TaskPriority.high,
        tag="робота",
        status=TaskStatus.todo,
        reminder_sent_1h=False,
        reminder_sent_10m=False,
    )
    db_session.add(task)
    await db_session.commit()

    stats = await run_deadline_checks(
        bot=mock_bot,
        sessionmaker=session_factory,
        now_dt=now_utc,
    )

    assert stats["reminders_1h_sent"] == 1
    assert stats["reminders_10m_sent"] == 0
    assert stats["errors"] == 0

    mock_bot.send_message.assert_called_once()
    call_kwargs = mock_bot.send_message.call_args.kwargs
    assert call_kwargs["chat_id"] == user.telegram_id
    assert "⏳ <b>Нагадування про дедлайн!</b>" in call_kwargs["text"]
    assert "Здати квартальний звіт" in call_kwargs["text"]
    assert "⚠️ Високий" in call_kwargs["text"]
    assert "🏷️ #робота" in call_kwargs["text"]
    # In Europe/Kyiv (UTC+2 in winter), 14:50 UTC is 16:50
    assert "🕒 до 16:50" in call_kwargs["text"]
    assert isinstance(call_kwargs["reply_markup"], InlineKeyboardMarkup)

    await db_session.refresh(task)
    assert task.reminder_sent_1h is True
    assert task.reminder_sent_10m is False


@pytest.mark.asyncio
async def test_10m_proximity_trigger(
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    mock_bot: AsyncMock,
) -> None:
    """Verifies REQ-SCH-03: Task nearing deadline within 10 minutes triggers 10m reminder and sets both flags."""
    user = User(telegram_id=102, timezone="Europe/Kyiv")
    db_session.add(user)
    await db_session.commit()

    now_utc = datetime(2026, 11, 21, 14, 0, 0, tzinfo=timezone.utc)
    # Deadline in 8 minutes (delta = 480 sec, within 0 < delta <= 600)
    deadline_utc = now_utc + timedelta(minutes=8)

    task = Task(
        user_id=user.telegram_id,
        title="Оплатити рахунок",
        target_date=now_utc.date(),
        deadline_at=deadline_utc,
        priority=TaskPriority.medium,
        tag=None,
        status=TaskStatus.todo,
        reminder_sent_1h=False,
        reminder_sent_10m=False,
    )
    db_session.add(task)
    await db_session.commit()

    stats = await run_deadline_checks(
        bot=mock_bot,
        sessionmaker=session_factory,
        now_dt=now_utc,
    )

    assert stats["reminders_1h_sent"] == 0
    assert stats["reminders_10m_sent"] == 1
    assert stats["errors"] == 0

    mock_bot.send_message.assert_called_once()
    call_kwargs = mock_bot.send_message.call_args.kwargs
    assert call_kwargs["chat_id"] == user.telegram_id
    assert "🚨 <b>Увага! Дедлайн через 10 хвилин!</b>" in call_kwargs["text"]
    assert "Оплатити рахунок" in call_kwargs["text"]
    assert "⚡ Середній" in call_kwargs["text"]
    # In Europe/Kyiv (UTC+2 in winter), 14:08 UTC is 16:08
    assert "🕒 до 16:08" in call_kwargs["text"]

    await db_session.refresh(task)
    assert task.reminder_sent_10m is True
    assert task.reminder_sent_1h is True


@pytest.mark.asyncio
async def test_deadline_more_than_1h_away_ignored(
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    mock_bot: AsyncMock,
) -> None:
    """Verifies REQ-SCH-03: Task with deadline > 1 hour away does not dispatch notification."""
    user = User(telegram_id=103, timezone="Europe/Kyiv")
    db_session.add(user)
    await db_session.commit()

    now_utc = datetime(2026, 11, 21, 14, 0, 0, tzinfo=timezone.utc)
    deadline_utc = now_utc + timedelta(minutes=75)

    task = Task(
        user_id=user.telegram_id,
        title="Завдання на вечір",
        target_date=now_utc.date(),
        deadline_at=deadline_utc,
        status=TaskStatus.todo,
        reminder_sent_1h=False,
        reminder_sent_10m=False,
    )
    db_session.add(task)
    await db_session.commit()

    stats = await run_deadline_checks(
        bot=mock_bot,
        sessionmaker=session_factory,
        now_dt=now_utc,
    )

    assert stats["reminders_1h_sent"] == 0
    assert stats["reminders_10m_sent"] == 0
    assert stats["errors"] == 0
    mock_bot.send_message.assert_not_called()

    await db_session.refresh(task)
    assert task.reminder_sent_1h is False
    assert task.reminder_sent_10m is False


@pytest.mark.asyncio
async def test_past_deadline_ignored(
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    mock_bot: AsyncMock,
) -> None:
    """Verifies REQ-SCH-03: Task with past deadline (delta_sec <= 0) does not dispatch notification."""
    user = User(telegram_id=104, timezone="Europe/Kyiv")
    db_session.add(user)
    await db_session.commit()

    now_utc = datetime(2026, 11, 21, 14, 0, 0, tzinfo=timezone.utc)
    deadline_utc = now_utc - timedelta(minutes=5)

    task = Task(
        user_id=user.telegram_id,
        title="Протерміноване завдання",
        target_date=now_utc.date(),
        deadline_at=deadline_utc,
        status=TaskStatus.todo,
        reminder_sent_1h=False,
        reminder_sent_10m=False,
    )
    db_session.add(task)
    await db_session.commit()

    stats = await run_deadline_checks(
        bot=mock_bot,
        sessionmaker=session_factory,
        now_dt=now_utc,
    )

    assert stats["reminders_1h_sent"] == 0
    assert stats["reminders_10m_sent"] == 0
    assert stats["errors"] == 0
    mock_bot.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_completed_and_canceled_tasks_ignored(
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    mock_bot: AsyncMock,
) -> None:
    """Verifies REQ-SCH-03: Completed and canceled tasks are excluded from reminder processing."""
    user = User(telegram_id=105, timezone="Europe/Kyiv")
    db_session.add(user)
    await db_session.commit()

    now_utc = datetime(2026, 11, 21, 14, 0, 0, tzinfo=timezone.utc)
    deadline_utc = now_utc + timedelta(minutes=5)

    done_task = Task(
        user_id=user.telegram_id,
        title="Виконане завдання",
        target_date=now_utc.date(),
        deadline_at=deadline_utc,
        status=TaskStatus.done,
    )
    canceled_task = Task(
        user_id=user.telegram_id,
        title="Скасоване завдання",
        target_date=now_utc.date(),
        deadline_at=deadline_utc,
        status=TaskStatus.canceled,
    )
    db_session.add_all([done_task, canceled_task])
    await db_session.commit()

    stats = await run_deadline_checks(
        bot=mock_bot,
        sessionmaker=session_factory,
        now_dt=now_utc,
    )

    assert stats["reminders_1h_sent"] == 0
    assert stats["reminders_10m_sent"] == 0
    mock_bot.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_task_without_deadline_ignored(
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    mock_bot: AsyncMock,
) -> None:
    """Verifies REQ-SCH-03: Tasks without deadline (deadline_at is None) are ignored."""
    user = User(telegram_id=106, timezone="Europe/Kyiv")
    db_session.add(user)
    await db_session.commit()

    now_utc = datetime(2026, 11, 21, 14, 0, 0, tzinfo=timezone.utc)
    task = Task(
        user_id=user.telegram_id,
        title="Завдання без дедлайну",
        target_date=now_utc.date(),
        deadline_at=None,
        status=TaskStatus.todo,
    )
    db_session.add(task)
    await db_session.commit()

    stats = await run_deadline_checks(
        bot=mock_bot,
        sessionmaker=session_factory,
        now_dt=now_utc,
    )

    assert stats["reminders_1h_sent"] == 0
    assert stats["reminders_10m_sent"] == 0
    mock_bot.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_idempotency_no_duplicate_notifications(
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    mock_bot: AsyncMock,
) -> None:
    """Verifies REQ-SCH-03, REQ-NFR-03: Successive calls do not dispatch duplicate reminders once flags are True."""
    user = User(telegram_id=107, timezone="Europe/Kyiv")
    db_session.add(user)
    await db_session.commit()

    now_utc = datetime(2026, 11, 21, 14, 0, 0, tzinfo=timezone.utc)

    # Task 1 already has 1h reminder sent
    task_1h = Task(
        user_id=user.telegram_id,
        title="Вже нагадано за годину",
        target_date=now_utc.date(),
        deadline_at=now_utc + timedelta(minutes=40),
        status=TaskStatus.todo,
        reminder_sent_1h=True,
        reminder_sent_10m=False,
    )
    # Task 2 already has 10m reminder sent
    task_10m = Task(
        user_id=user.telegram_id,
        title="Вже нагадано за 10 хв",
        target_date=now_utc.date(),
        deadline_at=now_utc + timedelta(minutes=5),
        status=TaskStatus.todo,
        reminder_sent_1h=True,
        reminder_sent_10m=True,
    )
    db_session.add_all([task_1h, task_10m])
    await db_session.commit()

    stats = await run_deadline_checks(
        bot=mock_bot,
        sessionmaker=session_factory,
        now_dt=now_utc,
    )

    assert stats["reminders_1h_sent"] == 0
    assert stats["reminders_10m_sent"] == 0
    mock_bot.send_message.assert_not_called()


# ==============================================================================
# Callback Query Handlers Tests (REQ-TSK-02, REQ-SCH-03, REQ-NFR-02)
# ==============================================================================


@pytest.mark.asyncio
async def test_done_callback_success(db_session: AsyncSession) -> None:
    """Verifies REQ-TSK-02: Done callback marks task as done, updates message with strikethrough, and removes keyboard."""
    user = User(telegram_id=201, timezone="Europe/Kyiv")
    db_session.add(user)
    await db_session.commit()

    task = Task(
        user_id=user.telegram_id,
        title="Підготувати презентацію",
        target_date=date(2026, 11, 21),
        status=TaskStatus.todo,
    )
    db_session.add(task)
    await db_session.commit()

    mock_msg = create_mock_message()
    query = AsyncMock(spec=CallbackQuery)
    query.from_user = TgUser(id=user.telegram_id, is_bot=False, first_name="Nazarii")
    query.message = mock_msg
    query.answer = AsyncMock()

    callback_data = DeadlineCallback(action="done", task_id=task.id, user_id=user.telegram_id)

    await deadline_callback_handler(
        callback_query=query,
        callback_data=callback_data,
        session=db_session,
    )

    # Verify task updated in database
    await db_session.refresh(task)
    assert task.status == TaskStatus.done

    # Verify message edit
    mock_msg.edit_text.assert_called_once()
    call_kwargs = mock_msg.edit_text.call_args.kwargs
    assert "<s>Підготувати презентацію</s>" in call_kwargs["text"]
    assert "✅ <b>Завдання виконано!</b>" in call_kwargs["text"]
    assert call_kwargs["reply_markup"] is None

    # Verify callback query answered
    query.answer.assert_called_once_with("✅ Виконано!")


@pytest.mark.asyncio
async def test_done_callback_already_done(db_session: AsyncSession) -> None:
    """Verifies REQ-TSK-02: Done callback on already-completed task alerts user and removes keyboard."""
    user = User(telegram_id=202, timezone="Europe/Kyiv")
    db_session.add(user)
    await db_session.commit()

    task = Task(
        user_id=user.telegram_id,
        title="Вже виконане",
        target_date=date(2026, 11, 21),
        status=TaskStatus.done,
    )
    db_session.add(task)
    await db_session.commit()

    mock_msg = create_mock_message()
    query = AsyncMock(spec=CallbackQuery)
    query.from_user = TgUser(id=user.telegram_id, is_bot=False, first_name="Nazarii")
    query.message = mock_msg
    query.answer = AsyncMock()

    callback_data = DeadlineCallback(action="done", task_id=task.id, user_id=user.telegram_id)

    await deadline_callback_handler(
        callback_query=query,
        callback_data=callback_data,
        session=db_session,
    )

    query.answer.assert_called_once_with("⚠️ Завдання вже виконано.", show_alert=True)
    mock_msg.edit_reply_markup.assert_called_once_with(reply_markup=None)


@pytest.mark.asyncio
async def test_snooze_callback_success(db_session: AsyncSession) -> None:
    """Verifies REQ-SCH-03: Snooze callback extends deadline by specified minutes and resets 10m flag."""
    user = User(telegram_id=203, timezone="Europe/Kyiv")
    db_session.add(user)
    await db_session.commit()

    initial_deadline = datetime(2026, 11, 21, 15, 0, 0, tzinfo=timezone.utc)
    task = Task(
        user_id=user.telegram_id,
        title="Перевірити пошту",
        target_date=date(2026, 11, 21),
        deadline_at=initial_deadline,
        status=TaskStatus.todo,
        reminder_sent_1h=True,
        reminder_sent_10m=True,
    )
    db_session.add(task)
    await db_session.commit()

    mock_msg = create_mock_message()
    query = AsyncMock(spec=CallbackQuery)
    query.from_user = TgUser(id=user.telegram_id, is_bot=False, first_name="Nazarii")
    query.message = mock_msg
    query.answer = AsyncMock()

    callback_data = DeadlineCallback(action="snooze", task_id=task.id, user_id=user.telegram_id, minutes=15)

    await deadline_callback_handler(
        callback_query=query,
        callback_data=callback_data,
        session=db_session,
    )

    await db_session.refresh(task)
    expected_deadline = initial_deadline + timedelta(minutes=15)
    assert task.deadline_at == expected_deadline or task.deadline_at.replace(tzinfo=timezone.utc) == expected_deadline
    assert task.reminder_sent_10m is False

    mock_msg.edit_text.assert_called_once()
    call_kwargs = mock_msg.edit_text.call_args.kwargs
    assert "⏰ <b>Дедлайн відкладено на +15 хв!</b>" in call_kwargs["text"]
    assert "Перевірити пошту" in call_kwargs["text"]
    # 15:15 UTC in Europe/Kyiv is 17:15
    assert "🕒 17:15" in call_kwargs["text"]
    assert isinstance(call_kwargs["reply_markup"], InlineKeyboardMarkup)

    query.answer.assert_called_once_with("⏰ Відкладено на 15 хв")


@pytest.mark.asyncio
async def test_snooze_callback_resets_1h_flag_when_extended_beyond_60m(db_session: AsyncSession) -> None:
    """Verifies REQ-SCH-03: Snooze callback resets reminder_sent_1h if new deadline is > 60m away."""
    user = User(telegram_id=204, timezone="Europe/Kyiv")
    db_session.add(user)
    await db_session.commit()

    # Current time: now_utc; initial deadline: now + 5 min
    now_utc = datetime.now(timezone.utc)
    task = Task(
        user_id=user.telegram_id,
        title="Довгий дедлайн",
        target_date=now_utc.date(),
        deadline_at=now_utc + timedelta(minutes=5),
        status=TaskStatus.todo,
        reminder_sent_1h=True,
        reminder_sent_10m=True,
    )
    db_session.add(task)
    await db_session.commit()

    mock_msg = create_mock_message()
    query = AsyncMock(spec=CallbackQuery)
    query.from_user = TgUser(id=user.telegram_id, is_bot=False, first_name="Nazarii")
    query.message = mock_msg
    query.answer = AsyncMock()

    # Snooze by 90 minutes
    callback_data = DeadlineCallback(action="snooze", task_id=task.id, user_id=user.telegram_id, minutes=90)

    await deadline_callback_handler(
        callback_query=query,
        callback_data=callback_data,
        session=db_session,
    )

    await db_session.refresh(task)
    assert task.reminder_sent_10m is False
    assert task.reminder_sent_1h is False


@pytest.mark.asyncio
async def test_snooze_callback_updates_target_date_across_midnight(db_session: AsyncSession) -> None:
    """Verifies REQ-SCH-03: Snooze callback advances target_date if extended deadline reaches next day."""
    user = User(telegram_id=205, timezone="Europe/Kyiv")
    db_session.add(user)
    await db_session.commit()

    # In Kyiv (UTC+2), 2026-11-21 21:50:00 UTC is 23:50 local time on Nov 21
    deadline_utc = datetime(2026, 11, 21, 21, 50, 0, tzinfo=timezone.utc)
    task = Task(
        user_id=user.telegram_id,
        title="Нічне завдання",
        target_date=date(2026, 11, 21),
        deadline_at=deadline_utc,
        status=TaskStatus.todo,
    )
    db_session.add(task)
    await db_session.commit()

    mock_msg = create_mock_message()
    query = AsyncMock(spec=CallbackQuery)
    query.from_user = TgUser(id=user.telegram_id, is_bot=False, first_name="Nazarii")
    query.message = mock_msg
    query.answer = AsyncMock()

    # Snooze by 20 minutes -> Kyiv time 00:10 on Nov 22
    callback_data = DeadlineCallback(action="snooze", task_id=task.id, user_id=user.telegram_id, minutes=20)

    await deadline_callback_handler(
        callback_query=query,
        callback_data=callback_data,
        session=db_session,
    )

    await db_session.refresh(task)
    assert task.target_date == date(2026, 11, 22)


@pytest.mark.asyncio
async def test_tenant_security_rejection(db_session: AsyncSession) -> None:
    """Verifies REQ-NFR-02: Callback from unauthorized user is rejected with alert and leaves task state untouched."""
    owner_id = 301
    attacker_id = 999

    user = User(telegram_id=owner_id, timezone="Europe/Kyiv")
    db_session.add(user)
    await db_session.commit()

    deadline_utc = datetime(2026, 11, 21, 15, 0, 0, tzinfo=timezone.utc)
    task = Task(
        user_id=owner_id,
        title="Конфіденційне завдання",
        target_date=date(2026, 11, 21),
        deadline_at=deadline_utc,
        status=TaskStatus.todo,
    )
    db_session.add(task)
    await db_session.commit()

    mock_msg = create_mock_message()
    query = AsyncMock(spec=CallbackQuery)
    query.from_user = TgUser(id=attacker_id, is_bot=False, first_name="Attacker")
    query.message = mock_msg
    query.answer = AsyncMock()

    callback_data = DeadlineCallback(action="done", task_id=task.id, user_id=owner_id)

    await deadline_callback_handler(
        callback_query=query,
        callback_data=callback_data,
        session=db_session,
    )

    query.answer.assert_called_once_with(
        "⚠️ Ви не можете керувати завданнями іншого користувача.",
        show_alert=True,
    )
    mock_msg.edit_text.assert_not_called()
    mock_msg.edit_reply_markup.assert_not_called()

    # Database untouched
    await db_session.refresh(task)
    assert task.status == TaskStatus.todo
    assert task.deadline_at == deadline_utc or task.deadline_at.replace(tzinfo=timezone.utc) == deadline_utc


@pytest.mark.asyncio
async def test_task_not_found_callback(db_session: AsyncSession) -> None:
    """Verifies REQ-NFR-02: Callback for non-existent or deleted task alerts user and clears keyboard."""
    user_id = 302
    user = User(telegram_id=user_id, timezone="Europe/Kyiv")
    db_session.add(user)
    await db_session.commit()

    mock_msg = create_mock_message()
    query = AsyncMock(spec=CallbackQuery)
    query.from_user = TgUser(id=user_id, is_bot=False, first_name="Nazarii")
    query.message = mock_msg
    query.answer = AsyncMock()

    callback_data = DeadlineCallback(action="done", task_id=999999, user_id=user_id)

    await deadline_callback_handler(
        callback_query=query,
        callback_data=callback_data,
        session=db_session,
    )

    query.answer.assert_called_once_with(
        "⚠️ Завдання не знайдено або вже видалено.",
        show_alert=True,
    )
    mock_msg.edit_reply_markup.assert_called_once_with(reply_markup=None)


# ==============================================================================
# Error Isolation & Telegram Exception Tests (REQ-NFR-02, REQ-SCH-03)
# ==============================================================================


@pytest.mark.asyncio
async def test_error_isolation_and_blocked_bot(
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    mock_bot: AsyncMock,
) -> None:
    """Verifies REQ-NFR-02, REQ-SCH-03: TelegramForbiddenError marks flags to avoid retry storms and isolates errors."""
    user1 = User(telegram_id=401, timezone="Europe/Kyiv")
    user2 = User(telegram_id=402, timezone="Europe/Kyiv")
    db_session.add_all([user1, user2])
    await db_session.commit()

    now_utc = datetime(2026, 11, 21, 14, 0, 0, tzinfo=timezone.utc)
    task1 = Task(
        user_id=user1.telegram_id,
        title="Завдання заблокованого",
        target_date=now_utc.date(),
        deadline_at=now_utc + timedelta(minutes=5),
        status=TaskStatus.todo,
    )
    task2 = Task(
        user_id=user2.telegram_id,
        title="Завдання активного",
        target_date=now_utc.date(),
        deadline_at=now_utc + timedelta(minutes=5),
        status=TaskStatus.todo,
    )
    db_session.add_all([task1, task2])
    await db_session.commit()

    # User 1 raises TelegramForbiddenError, User 2 succeeds
    async def fake_send_message(chat_id, **kwargs):
        if chat_id == user1.telegram_id:
            raise TelegramForbiddenError(method="sendMessage", message="Forbidden: bot was blocked by the user")
        return AsyncMock(message_id=200)

    mock_bot.send_message.side_effect = fake_send_message

    stats = await run_deadline_checks(
        bot=mock_bot,
        sessionmaker=session_factory,
        now_dt=now_utc,
    )

    # User 1 was skipped cleanly with flags set; User 2 triggered reminder
    assert stats["reminders_10m_sent"] == 1
    assert stats["errors"] == 0

    await db_session.refresh(task1)
    assert task1.reminder_sent_1h is True
    assert task1.reminder_sent_10m is True

    await db_session.refresh(task2)
    assert task2.reminder_sent_1h is True
    assert task2.reminder_sent_10m is True


@pytest.mark.asyncio
async def test_unexpected_exception_isolation(
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    mock_bot: AsyncMock,
) -> None:
    """Verifies REQ-NFR-02: Unexpected exception on task 1 rolls back, increments errors, and does not stop task 2."""
    user1 = User(telegram_id=501, timezone="Europe/Kyiv")
    user2 = User(telegram_id=502, timezone="Europe/Kyiv")
    db_session.add_all([user1, user2])
    await db_session.commit()

    now_utc = datetime(2026, 11, 21, 14, 0, 0, tzinfo=timezone.utc)
    task1 = Task(
        user_id=user1.telegram_id,
        title="Завдання з помилкою",
        target_date=now_utc.date(),
        deadline_at=now_utc + timedelta(minutes=5),
        status=TaskStatus.todo,
    )
    task2 = Task(
        user_id=user2.telegram_id,
        title="Нормальне завдання",
        target_date=now_utc.date(),
        deadline_at=now_utc + timedelta(minutes=5),
        status=TaskStatus.todo,
    )
    db_session.add_all([task1, task2])
    await db_session.commit()

    # User 1 raises generic RuntimeError
    async def fake_send_message(chat_id, **kwargs):
        if chat_id == user1.telegram_id:
            raise RuntimeError("Database connection glitch or simulated failure")
        return AsyncMock(message_id=200)

    mock_bot.send_message.side_effect = fake_send_message

    stats = await run_deadline_checks(
        bot=mock_bot,
        sessionmaker=session_factory,
        now_dt=now_utc,
    )

    assert stats["reminders_10m_sent"] == 1
    assert stats["errors"] == 1

    await db_session.refresh(task1)
    # Task 1 was rolled back
    assert task1.reminder_sent_10m is False

    await db_session.refresh(task2)
    # Task 2 succeeded
    assert task2.reminder_sent_10m is True


# ==============================================================================
# Scheduler Registration Tests (REQ-SCH-03)
# ==============================================================================


def test_scheduler_registration_deadline_checks(
    session_factory: async_sessionmaker[AsyncSession],
    mock_bot: AsyncMock,
) -> None:
    """Verifies REQ-SCH-03: setup_scheduler registers deadline_checks job with CronTrigger(second=30)."""
    scheduler = AsyncIOScheduler(timezone="UTC")
    setup_scheduler(scheduler=scheduler, bot=mock_bot, sessionmaker=session_factory)

    job = scheduler.get_job("deadline_checks")
    assert job is not None
    assert job.name == "Deadline Proximity Checks"
    assert job.func == run_deadline_checks
    assert job.max_instances == 1
    assert job.coalesce is True

    # Verify CronTrigger second=30, UTC
    trigger = job.trigger
    assert isinstance(trigger, CronTrigger)
    second_field = next(f for f in trigger.fields if f.name == "second")
    assert str(second_field) == "30"
    assert trigger.timezone == timezone.utc


def test_create_dispatcher_includes_deadline_router() -> None:
    """Verifies REQ-SCH-03: create_dispatcher includes deadline_router in registered sub-routers."""
    from src.bot.dispatcher import create_dispatcher
    from src.bot.handlers.deadline import deadline_router

    dp = create_dispatcher()
    assert deadline_router in dp.sub_routers

