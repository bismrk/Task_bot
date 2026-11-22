"""Automated integration tests for timezone-aware background scheduler.

Verifies:
- REQ-SCH-01: Timezone-aware midnight rollover reviews (00:00).
- REQ-SCH-02: Timezone-aware morning digest pushes (09:00).
- REQ-TMA-02: Pre-generation of recurring tasks before morning digest creation.
- REQ-NFR-02: Per-user exception isolation and tenant boundaries.
- REQ-NFR-03: Restart-resilient idempotency tracking via database dates.
"""

from datetime import date, datetime, time, timedelta, timezone
from unittest.mock import AsyncMock

from aiogram.exceptions import TelegramForbiddenError
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.models.task import Task, TaskPriority, TaskStatus
from src.models.user import User
from src.scheduler.jobs import (
    process_user_midnight_rollover,
    process_user_morning_push,
    process_user_periodic_reminder,
    run_deadline_checks,
    run_timezone_checks,
)
from src.scheduler.manager import (
    create_scheduler,
    setup_scheduler,
    start_scheduler,
    stop_scheduler,
)


@pytest.fixture
def mock_bot() -> AsyncMock:
    """Provide a mock aiogram Bot instance with async send_message."""
    bot = AsyncMock()
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


# ============================================================================
# Midnight Rollover Tests (REQ-SCH-01, REQ-NFR-03)
# ============================================================================


@pytest.mark.asyncio
async def test_midnight_rollover_with_overdue_tasks(
    db_session: AsyncSession,
    mock_bot: AsyncMock,
) -> None:
    """Verifies REQ-SCH-01: Midnight rollover dialogue with overdue tasks."""
    user = User(
        telegram_id=1001,
        timezone="Europe/Kyiv",
        last_midnight_review_date=None,
    )
    db_session.add(user)
    await db_session.commit()

    # Create an overdue task from yesterday
    overdue_task = Task(
        user_id=1001,
        title="Підготувати звіт",
        target_date=date(2026, 11, 20),
        status=TaskStatus.todo,
        priority=TaskPriority.high,
        tag="робота",
    )
    db_session.add(overdue_task)
    await db_session.commit()

    # Midnight in Kyiv on 2026-11-21: 2026-11-20 22:00:00 UTC (Kyiv is UTC+2)
    midnight_utc = datetime(2026, 11, 20, 22, 0, 0, tzinfo=timezone.utc)

    triggered = await process_user_midnight_rollover(
        bot=mock_bot,
        session=db_session,
        user=user,
        now_dt=midnight_utc,
    )

    assert triggered is True
    # Two messages: batch overview control message + individual task message
    assert mock_bot.send_message.call_count == 2
    assert user.last_midnight_review_date == date(2026, 11, 21)

    overview_call = mock_bot.send_message.call_args_list[0]
    assert overview_call.kwargs["chat_id"] == 1001
    assert "Невиконані завдання" in overview_call.kwargs["text"]
    assert overview_call.kwargs["reply_markup"] is not None

    task_call = mock_bot.send_message.call_args_list[1]
    assert task_call.kwargs["chat_id"] == 1001
    assert "Підготувати звіт" in task_call.kwargs["text"]


@pytest.mark.asyncio
async def test_midnight_rollover_with_zero_overdue_tasks(
    db_session: AsyncSession,
    mock_bot: AsyncMock,
) -> None:
    """Verifies REQ-SCH-01: Midnight rollover congratulatory message when 0 overdue tasks."""
    user = User(
        telegram_id=1002,
        timezone="Europe/Kyiv",
        last_midnight_review_date=None,
    )
    db_session.add(user)
    await db_session.commit()

    midnight_utc = datetime(2026, 11, 20, 22, 0, 0, tzinfo=timezone.utc)

    triggered = await process_user_midnight_rollover(
        bot=mock_bot,
        session=db_session,
        user=user,
        now_dt=midnight_utc,
    )

    assert triggered is True
    assert mock_bot.send_message.call_count == 1
    call = mock_bot.send_message.call_args
    assert call.kwargs["chat_id"] == 1002
    assert "Всі вчорашні завдання виконано" in call.kwargs["text"]
    assert call.kwargs.get("reply_markup") is None
    assert user.last_midnight_review_date == date(2026, 11, 21)


@pytest.mark.asyncio
async def test_midnight_rollover_off_window_ignored(
    db_session: AsyncSession,
    mock_bot: AsyncMock,
) -> None:
    """Verifies REQ-SCH-01: Off-window times (e.g. 23:59 or 00:01) do not trigger rollover."""
    user = User(
        telegram_id=1003,
        timezone="Europe/Kyiv",
        last_midnight_review_date=None,
    )
    db_session.add(user)
    await db_session.commit()

    # 23:59 Kyiv (21:59 UTC)
    t_2359 = datetime(2026, 11, 20, 21, 59, 0, tzinfo=timezone.utc)
    res_2359 = await process_user_midnight_rollover(mock_bot, db_session, user, now_dt=t_2359)
    assert res_2359 is False
    assert mock_bot.send_message.call_count == 0
    assert user.last_midnight_review_date is None

    # 00:01 Kyiv (22:01 UTC)
    t_0001 = datetime(2026, 11, 20, 22, 1, 0, tzinfo=timezone.utc)
    res_0001 = await process_user_midnight_rollover(mock_bot, db_session, user, now_dt=t_0001)
    assert res_0001 is False
    assert mock_bot.send_message.call_count == 0
    assert user.last_midnight_review_date is None


@pytest.mark.asyncio
async def test_midnight_rollover_idempotency_prevents_duplicate_runs(
    db_session: AsyncSession,
    mock_bot: AsyncMock,
) -> None:
    """Verifies REQ-SCH-01, REQ-NFR-03: Repeated runs on the same date return False."""
    user = User(
        telegram_id=1004,
        timezone="Europe/Kyiv",
        last_midnight_review_date=date(2026, 11, 21),
    )
    db_session.add(user)
    await db_session.commit()

    midnight_utc = datetime(2026, 11, 20, 22, 0, 0, tzinfo=timezone.utc)
    triggered = await process_user_midnight_rollover(mock_bot, db_session, user, now_dt=midnight_utc)

    assert triggered is False
    assert mock_bot.send_message.call_count == 0


# ============================================================================
# Morning Push Digest Tests (REQ-SCH-02, REQ-TMA-02, REQ-NFR-03)
# ============================================================================


@pytest.mark.asyncio
async def test_morning_push_with_pending_tasks_and_recurring_generation(
    db_session: AsyncSession,
    mock_bot: AsyncMock,
) -> None:
    """Verifies REQ-SCH-02, REQ-TMA-02: Morning push digest with pending and recurring tasks."""
    user = User(
        telegram_id=2001,
        timezone="Europe/Kyiv",
        last_morning_push_date=None,
    )
    db_session.add(user)
    await db_session.commit()

    today = date(2026, 11, 21)

    # 1. Normal task for today with high priority, tag, and deadline
    task1 = Task(
        user_id=2001,
        title="Зробити презентацію",
        target_date=today,
        priority=TaskPriority.high,
        tag="робота",
        deadline_at=datetime(2026, 11, 21, 16, 0, 0, tzinfo=timezone.utc),  # 18:00 Kyiv
        status=TaskStatus.todo,
    )
    db_session.add(task1)

    # 2. Daily recurring task from yesterday (REQ-TMA-02)
    past_recurring = Task(
        user_id=2001,
        title="Ранкова зарядка",
        target_date=date(2026, 11, 20),
        recurrence="daily",
        priority=TaskPriority.low,
        tag="здоров'я",
        status=TaskStatus.done,
    )
    db_session.add(past_recurring)
    await db_session.commit()

    # 09:00 Kyiv on 2026-11-21: 2026-11-21 07:00:00 UTC
    morning_utc = datetime(2026, 11, 21, 7, 0, 0, tzinfo=timezone.utc)

    triggered = await process_user_morning_push(
        bot=mock_bot,
        session=db_session,
        user=user,
        webapp_url="https://app.tasks.internal",
        now_dt=morning_utc,
    )

    assert triggered is True
    assert mock_bot.send_message.call_count == 1
    call = mock_bot.send_message.call_args
    assert call.kwargs["chat_id"] == 2001
    text = call.kwargs["text"]

    # Header and count
    assert "📋 <b>План на сьогодні (21.11.2026):</b>" in text
    assert "У вас 2 запланованих завдань на сьогодні:" in text

    # Bullet items formatting per _docs/design-system.md
    assert "• Зробити презентацію — ⚠️ Високий | 🏷️ #робота | 🕒 до 18:00" in text
    assert "• Ранкова зарядка — 💤 Низький | 🏷️ #здоров'я" in text

    # Keyboard button [🚀 Відкрити план]
    reply_markup = call.kwargs["reply_markup"]
    assert reply_markup is not None
    assert reply_markup.inline_keyboard[0][0].text == "🚀 Відкрити план"
    assert reply_markup.inline_keyboard[0][0].web_app.url == "https://app.tasks.internal"

    # Verify idempotency date updated
    assert user.last_morning_push_date == today


@pytest.mark.asyncio
async def test_morning_push_with_zero_pending_tasks(
    db_session: AsyncSession,
    mock_bot: AsyncMock,
) -> None:
    """Verifies REQ-SCH-02: Morning push friendly message when 0 pending tasks."""
    user = User(
        telegram_id=2002,
        timezone="Europe/Kyiv",
        last_morning_push_date=None,
    )
    db_session.add(user)
    await db_session.commit()

    morning_utc = datetime(2026, 11, 21, 7, 0, 0, tzinfo=timezone.utc)

    triggered = await process_user_morning_push(
        bot=mock_bot,
        session=db_session,
        user=user,
        webapp_url=None,
        now_dt=morning_utc,
    )

    assert triggered is True
    assert mock_bot.send_message.call_count == 1
    call = mock_bot.send_message.call_args
    assert call.kwargs["chat_id"] == 2002
    text = call.kwargs["text"]
    assert "☀️ <b>Доброго ранку!</b>" in text
    assert "На сьогодні у вас немає запланованих завдань." in text
    assert "Відпочиньте або надиктуйте нові плани на день 🚀" in text

    # Fallback button callback_data="open_plan"
    reply_markup = call.kwargs["reply_markup"]
    assert reply_markup is not None
    assert reply_markup.inline_keyboard[0][0].text == "🚀 Відкрити план"
    assert reply_markup.inline_keyboard[0][0].callback_data == "open_plan"

    assert user.last_morning_push_date == date(2026, 11, 21)


@pytest.mark.asyncio
async def test_morning_push_off_window_ignored(
    db_session: AsyncSession,
    mock_bot: AsyncMock,
) -> None:
    """Verifies REQ-SCH-02: Off-window times (e.g. 08:59 or 09:01) do not trigger morning push."""
    user = User(
        telegram_id=2003,
        timezone="Europe/Kyiv",
        last_morning_push_date=None,
    )
    db_session.add(user)
    await db_session.commit()

    # 08:59 Kyiv (06:59 UTC)
    t_0859 = datetime(2026, 11, 21, 6, 59, 0, tzinfo=timezone.utc)
    res_0859 = await process_user_morning_push(mock_bot, db_session, user, now_dt=t_0859)
    assert res_0859 is False
    assert mock_bot.send_message.call_count == 0
    assert user.last_morning_push_date is None

    # 09:01 Kyiv (07:01 UTC)
    t_0901 = datetime(2026, 11, 21, 7, 1, 0, tzinfo=timezone.utc)
    res_0901 = await process_user_morning_push(mock_bot, db_session, user, now_dt=t_0901)
    assert res_0901 is False
    assert mock_bot.send_message.call_count == 0
    assert user.last_morning_push_date is None


@pytest.mark.asyncio
async def test_morning_push_idempotency_prevents_duplicate_runs(
    db_session: AsyncSession,
    mock_bot: AsyncMock,
) -> None:
    """Verifies REQ-SCH-02, REQ-NFR-03: Repeated morning runs on the same date return False."""
    user = User(
        telegram_id=2004,
        timezone="Europe/Kyiv",
        last_morning_push_date=date(2026, 11, 21),
    )
    db_session.add(user)
    await db_session.commit()

    morning_utc = datetime(2026, 11, 21, 7, 0, 0, tzinfo=timezone.utc)
    triggered = await process_user_morning_push(mock_bot, db_session, user, now_dt=morning_utc)

    assert triggered is False
    assert mock_bot.send_message.call_count == 0


# ============================================================================
# Timezone Independence Tests (REQ-SCH-01, REQ-SCH-02, REQ-NFR-02)
# ============================================================================


@pytest.mark.asyncio
async def test_timezone_independence_across_regions(
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    mock_bot: AsyncMock,
) -> None:
    """Verifies REQ-SCH-01, REQ-SCH-02: Independent evaluation of users across multiple timezones."""
    # User 1: Asia/Tokyo (UTC+9)
    u_tokyo = User(telegram_id=3001, timezone="Asia/Tokyo")
    # User 2: Europe/Kyiv (UTC+2)
    u_kyiv = User(telegram_id=3002, timezone="Europe/Kyiv")
    # User 3: America/New_York (UTC-5)
    u_ny = User(telegram_id=3003, timezone="America/New_York")

    db_session.add_all([u_tokyo, u_kyiv, u_ny])
    await db_session.commit()

    # Target 1: UTC 15:00 on 2026-11-21
    # Tokyo local: 2026-11-22 00:00 (Midnight rollover!)
    # Kyiv local:  2026-11-21 17:00 (No trigger)
    # NY local:    2026-11-21 10:00 (No trigger)
    utc_1500 = datetime(2026, 11, 21, 15, 0, 0, tzinfo=timezone.utc)

    stats1 = await run_timezone_checks(
        bot=mock_bot,
        sessionmaker=session_factory,
        reference_time=utc_1500,
    )

    assert stats1["midnight_triggered"] == 1
    assert stats1["morning_triggered"] == 0
    assert stats1["errors"] == 0

    # Refresh users from session
    async with session_factory() as s:
        t_ref = await s.get(User, 3001)
        k_ref = await s.get(User, 3002)
        n_ref = await s.get(User, 3003)

        assert t_ref.last_midnight_review_date == date(2026, 11, 22)
        assert k_ref.last_midnight_review_date is None
        assert n_ref.last_midnight_review_date is None

    # Target 2: UTC 07:00 on 2026-11-21
    # Kyiv local:  2026-11-21 09:00 (Morning push!)
    # Tokyo local: 2026-11-21 16:00 (No trigger)
    # NY local:    2026-11-21 02:00 (No trigger)
    utc_0700 = datetime(2026, 11, 21, 7, 0, 0, tzinfo=timezone.utc)

    stats2 = await run_timezone_checks(
        bot=mock_bot,
        sessionmaker=session_factory,
        reference_time=utc_0700,
    )

    assert stats2["midnight_triggered"] == 0
    assert stats2["morning_triggered"] == 1
    assert stats2["errors"] == 0

    async with session_factory() as s:
        k_ref = await s.get(User, 3002)
        t_ref = await s.get(User, 3001)
        n_ref = await s.get(User, 3003)

        assert k_ref.last_morning_push_date == date(2026, 11, 21)
        assert t_ref.last_morning_push_date is None
        assert n_ref.last_morning_push_date is None


# ============================================================================
# Restart-Resilient Idempotency Tests (REQ-NFR-03)
# ============================================================================


@pytest.mark.asyncio
async def test_restart_resilient_idempotency_in_run_timezone_checks(
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    mock_bot: AsyncMock,
) -> None:
    """Verifies REQ-NFR-03: Repeated run_timezone_checks invocations do not duplicate messages."""
    user = User(
        telegram_id=4001,
        timezone="Europe/Kyiv",
        last_morning_push_date=None,
    )
    db_session.add(user)
    await db_session.commit()

    morning_utc = datetime(2026, 11, 21, 7, 0, 0, tzinfo=timezone.utc)

    # First run: triggers morning push
    stats1 = await run_timezone_checks(
        bot=mock_bot,
        sessionmaker=session_factory,
        reference_time=morning_utc,
    )
    assert stats1["morning_triggered"] == 1
    initial_calls = mock_bot.send_message.call_count
    assert initial_calls == 1

    # Second run (simulating scheduler tick or application restart in same minute)
    stats2 = await run_timezone_checks(
        bot=mock_bot,
        sessionmaker=session_factory,
        reference_time=morning_utc,
    )
    assert stats2["morning_triggered"] == 0
    assert mock_bot.send_message.call_count == initial_calls


# ============================================================================
# Telegram Error and Per-User Isolation Tests (REQ-NFR-02)
# ============================================================================


@pytest.mark.asyncio
async def test_telegram_forbidden_error_handled_gracefully(
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    mock_bot: AsyncMock,
) -> None:
    """Verifies REQ-NFR-02: TelegramForbiddenError (blocked bot) logs warning and marks trigger date."""
    user = User(
        telegram_id=5001,
        timezone="Europe/Kyiv",
        last_morning_push_date=None,
    )
    db_session.add(user)
    await db_session.commit()

    # Simulate bot blocked by user
    mock_bot.send_message.side_effect = TelegramForbiddenError(
        method="sendMessage",
        message="Forbidden: bot was blocked by the user",
    )

    morning_utc = datetime(2026, 11, 21, 7, 0, 0, tzinfo=timezone.utc)

    stats = await run_timezone_checks(
        bot=mock_bot,
        sessionmaker=session_factory,
        reference_time=morning_utc,
    )

    # Should complete cleanly without unhandled exception and with errors=0
    assert stats["errors"] == 0
    assert stats["morning_triggered"] == 0

    # Trigger date marked to prevent continuous retry loops
    async with session_factory() as s:
        refreshed = await s.get(User, 5001)
        assert refreshed.last_morning_push_date == date(2026, 11, 21)


@pytest.mark.asyncio
async def test_per_user_exception_isolation_ensures_other_users_processed(
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    mock_bot: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verifies REQ-NFR-02: Exception in user 1 does not impede processing user 2."""
    user1 = User(telegram_id=6001, timezone="Europe/Kyiv")
    user2 = User(telegram_id=6002, timezone="Europe/Kyiv")
    db_session.add_all([user1, user2])
    await db_session.commit()

    morning_utc = datetime(2026, 11, 21, 7, 0, 0, tzinfo=timezone.utc)

    # Monkeypatch process_user_morning_push to fail ONLY for user 6001
    original_morning_push = process_user_morning_push

    async def faulty_morning_push(bot, session, user, webapp_url=None, now_dt=None):
        if user.telegram_id == 6001:
            raise RuntimeError("Database connection timeout for user 6001")
        return await original_morning_push(bot, session, user, webapp_url, now_dt)

    monkeypatch.setattr("src.scheduler.jobs.process_user_morning_push", faulty_morning_push)

    stats = await run_timezone_checks(
        bot=mock_bot,
        sessionmaker=session_factory,
        reference_time=morning_utc,
    )

    # User 1 failed -> error count incremented
    assert stats["errors"] == 1
    # User 2 succeeded -> morning triggered incremented
    assert stats["morning_triggered"] == 1

    async with session_factory() as s:
        u1_ref = await s.get(User, 6001)
        u2_ref = await s.get(User, 6002)

        assert u1_ref.last_morning_push_date is None
        assert u2_ref.last_morning_push_date == date(2026, 11, 21)


# ============================================================================
# Scheduler Lifecycle Tests (REQ-SCH-01, REQ-SCH-02)
# ============================================================================


@pytest.mark.asyncio
async def test_scheduler_lifecycle_and_configuration(
    session_factory: async_sessionmaker[AsyncSession],
    mock_bot: AsyncMock,
) -> None:
    """Verifies REQ-SCH-01, REQ-SCH-02: create, setup, configure, start, and stop scheduler."""
    scheduler = create_scheduler()
    assert scheduler.timezone == timezone.utc or str(scheduler.timezone) == "UTC"
    assert scheduler.running is False

    setup_scheduler(
        scheduler=scheduler,
        bot=mock_bot,
        sessionmaker=session_factory,
        webapp_url="https://app.tasks.internal",
    )

    job = scheduler.get_job("timezone_checks")
    assert job is not None
    assert job.name == "Timezone-Aware Background Checks"
    assert job.max_instances == 1
    assert job.coalesce is True

    start_scheduler(scheduler)
    assert scheduler.running is True

    # Test idempotency of start_scheduler
    start_scheduler(scheduler)
    assert scheduler.running is True

    stop_scheduler(scheduler, wait=False)
    # AsyncIOScheduler schedules shutdown via call_soon_threadsafe; yield to event loop
    import asyncio
    await asyncio.sleep(0)
    assert scheduler.running is False

    # Test idempotency of stop_scheduler
    stop_scheduler(scheduler, wait=False)
    await asyncio.sleep(0)
    assert scheduler.running is False


# ============================================================================
# Periodic Telegram Reminder Tests (Issue #24)
# ============================================================================


@pytest.mark.asyncio
async def test_morning_push_anchors_periodic_reminder_timestamp(
    db_session: AsyncSession,
    mock_bot: AsyncMock,
) -> None:
    """Verifies Issue #24: 09:00 morning push stamps last_periodic_reminder_at and anchors 4h cadence to 13:00/17:00/21:00."""
    user = User(
        telegram_id=7001,
        timezone="Europe/Kyiv",
        reminder_interval_hours=4,
    )
    db_session.add(user)
    today = date(2026, 11, 21)
    db_session.add(
        Task(
            user_id=7001,
            title="Підготувати презентацію",
            target_date=today,
            status=TaskStatus.todo,
        )
    )
    await db_session.commit()

    # 09:00 Kyiv = 07:00 UTC
    t_0900_utc = datetime(2026, 11, 21, 7, 0, 0, tzinfo=timezone.utc)
    morning_ok = await process_user_morning_push(mock_bot, db_session, user, now_dt=t_0900_utc)
    assert morning_ok is True
    assert user.last_periodic_reminder_at is not None
    assert user.last_periodic_reminder_at.replace(tzinfo=timezone.utc) == t_0900_utc

    # At 09:00, periodic reminder must NOT double-send
    assert await process_user_periodic_reminder(mock_bot, db_session, user, now_dt=t_0900_utc) is False

    # 10:00, 11:00, 12:00 Kyiv -> not yet 4h elapsed
    for local_h in (10, 11, 12):
        utc_dt = datetime(2026, 11, 21, local_h - 2, 0, 0, tzinfo=timezone.utc)
        assert await process_user_periodic_reminder(mock_bot, db_session, user, now_dt=utc_dt) is False

    # 13:00 Kyiv (11:00 UTC) -> 4h elapsed -> fires!
    t_1300_utc = datetime(2026, 11, 21, 11, 0, 0, tzinfo=timezone.utc)
    assert await process_user_periodic_reminder(mock_bot, db_session, user, now_dt=t_1300_utc) is True
    assert mock_bot.send_message.call_count == 2  # 1 morning + 1 periodic

    # 17:00 Kyiv (15:00 UTC) -> fires!
    t_1700_utc = datetime(2026, 11, 21, 15, 0, 0, tzinfo=timezone.utc)
    assert await process_user_periodic_reminder(mock_bot, db_session, user, now_dt=t_1700_utc) is True
    assert mock_bot.send_message.call_count == 3

    # 21:00 Kyiv (19:00 UTC) -> fires!
    t_2100_utc = datetime(2026, 11, 21, 19, 0, 0, tzinfo=timezone.utc)
    assert await process_user_periodic_reminder(mock_bot, db_session, user, now_dt=t_2100_utc) is True
    assert mock_bot.send_message.call_count == 4


@pytest.mark.asyncio
async def test_periodic_reminder_disabled_sends_nothing(
    db_session: AsyncSession,
    mock_bot: AsyncMock,
) -> None:
    """Verifies Issue #24: reminder_interval_hours=None disables periodic reminders."""
    user = User(
        telegram_id=7002,
        timezone="Europe/Kyiv",
        reminder_interval_hours=None,
    )
    db_session.add(user)
    db_session.add(
        Task(
            user_id=7002,
            title="Завдання",
            target_date=date(2026, 11, 21),
            status=TaskStatus.todo,
        )
    )
    await db_session.commit()

    # 13:00 Kyiv
    t_1300_utc = datetime(2026, 11, 21, 11, 0, 0, tzinfo=timezone.utc)
    triggered = await process_user_periodic_reminder(mock_bot, db_session, user, now_dt=t_1300_utc)
    assert triggered is False
    assert mock_bot.send_message.call_count == 0
    assert user.last_periodic_reminder_at is None


@pytest.mark.asyncio
async def test_periodic_reminder_active_hours_quiet_hours_and_intervals(
    db_session: AsyncSession,
    mock_bot: AsyncMock,
) -> None:
    """Verifies Issue #24: quiet hours 23:00-07:59, non-zero minutes, 09:00 skip, and fallback schedule."""
    today = date(2026, 11, 21)

    # 1h interval user with no prior timestamp
    u_1h = User(telegram_id=7003, timezone="UTC", reminder_interval_hours=1)
    # 18h (>13) interval user with no prior timestamp
    u_18h = User(telegram_id=7004, timezone="UTC", reminder_interval_hours=18)
    db_session.add_all([u_1h, u_18h])
    db_session.add_all(
        [
            Task(user_id=7003, title="Task 1h", target_date=today, status=TaskStatus.todo),
            Task(user_id=7004, title="Task 18h", target_date=today, status=TaskStatus.todo),
        ]
    )
    await db_session.commit()

    # Quiet hours & off-minute must NEVER trigger
    for dt in (
        datetime(2026, 11, 21, 0, 0, tzinfo=timezone.utc),
        datetime(2026, 11, 21, 7, 0, tzinfo=timezone.utc),
        datetime(2026, 11, 21, 23, 0, tzinfo=timezone.utc),
        datetime(2026, 11, 21, 13, 1, tzinfo=timezone.utc),
        datetime(2026, 11, 21, 9, 0, tzinfo=timezone.utc),  # 09:00 owned by morning push
    ):
        assert await process_user_periodic_reminder(mock_bot, db_session, u_1h, now_dt=dt) is False

    # 08:00 UTC triggers for 1h user
    t_0800 = datetime(2026, 11, 21, 8, 0, tzinfo=timezone.utc)
    assert await process_user_periodic_reminder(mock_bot, db_session, u_1h, now_dt=t_0800) is True

    # For interval > 13 (18h) with last_periodic_reminder_at=None: only 21:00 triggers
    assert (
        await process_user_periodic_reminder(
            mock_bot, db_session, u_18h, now_dt=datetime(2026, 11, 21, 13, 0, tzinfo=timezone.utc)
        )
        is False
    )
    assert (
        await process_user_periodic_reminder(
            mock_bot, db_session, u_18h, now_dt=datetime(2026, 11, 21, 21, 0, tzinfo=timezone.utc)
        )
        is True
    )


@pytest.mark.asyncio
async def test_periodic_reminder_skips_when_zero_todo_tasks(
    db_session: AsyncSession,
    mock_bot: AsyncMock,
) -> None:
    """Verifies Issue #24: zero uncompleted tasks skips sending and leaves last_periodic_reminder_at unchanged."""
    today = date(2026, 11, 21)
    user = User(telegram_id=7005, timezone="Europe/Kyiv", reminder_interval_hours=4)
    db_session.add(user)
    db_session.add_all(
        [
            Task(user_id=7005, title="Вже виконане", target_date=today, status=TaskStatus.done),
            Task(user_id=7005, title="Скасоване", target_date=today, status=TaskStatus.canceled),
        ]
    )
    await db_session.commit()

    t_1300_utc = datetime(2026, 11, 21, 11, 0, 0, tzinfo=timezone.utc)
    triggered = await process_user_periodic_reminder(mock_bot, db_session, user, now_dt=t_1300_utc)
    assert triggered is False
    assert mock_bot.send_message.call_count == 0
    assert user.last_periodic_reminder_at is None


@pytest.mark.asyncio
async def test_periodic_reminder_formatting_escaping_recurring_and_webapp_keyboard(
    db_session: AsyncSession,
    mock_bot: AsyncMock,
) -> None:
    """Verifies Issue #24: HTML message format, escaping, local deadline, recurring generation, and keyboard."""
    today = date(2026, 11, 21)
    user = User(telegram_id=7006, timezone="Europe/Kyiv", reminder_interval_hours=4)
    db_session.add(user)

    # Task with HTML special chars, tag, and deadline (16:00 UTC = 18:00 Kyiv)
    db_session.add(
        Task(
            user_id=7006,
            title="Перевірити <API> & логи",
            target_date=today,
            priority=TaskPriority.high,
            tag="#робота",
            deadline_at=datetime(2026, 11, 21, 16, 0, 0, tzinfo=timezone.utc),
            status=TaskStatus.todo,
        )
    )
    # Daily recurring task from yesterday -> must be auto-generated for today
    db_session.add(
        Task(
            user_id=7006,
            title="Випити воду",
            target_date=date(2026, 11, 20),
            recurrence="daily",
            priority=TaskPriority.low,
            status=TaskStatus.done,
        )
    )
    await db_session.commit()

    # 13:00 Kyiv = 11:00 UTC
    t_1300_utc = datetime(2026, 11, 21, 11, 0, 0, tzinfo=timezone.utc)
    triggered = await process_user_periodic_reminder(
        bot=mock_bot,
        session=db_session,
        user=user,
        webapp_url="https://app.tasks.internal",
        now_dt=t_1300_utc,
    )
    assert triggered is True
    assert mock_bot.send_message.call_count == 1

    call = mock_bot.send_message.call_args
    assert call.kwargs["chat_id"] == 7006
    assert call.kwargs["parse_mode"] == "HTML"
    text = call.kwargs["text"]
    assert "🔔 <b>Нагадування про завдання на сьогодні:</b>" in text
    assert "2" in text
    assert "• Перевірити &lt;API&gt; &amp; логи — ⚠️ Високий | 🏷️ #робота | 🕒 до 18:00" in text
    assert "• Випити воду — 💤 Низький" in text

    reply_markup = call.kwargs["reply_markup"]
    assert reply_markup.inline_keyboard[0][0].text == "🚀 Відкрити план"
    assert reply_markup.inline_keyboard[0][0].web_app.url == "https://app.tasks.internal"


@pytest.mark.asyncio
async def test_periodic_reminder_elapsed_time_naive_sqlite_and_jitter_tolerance(
    db_session: AsyncSession,
    mock_bot: AsyncMock,
) -> None:
    """Verifies Issue #24: naive SQLite last_periodic_reminder_at normalization, 1m jitter tolerance, and idempotency."""
    today = date(2026, 11, 21)
    # Naive datetime simulating value returned from SQLite (09:00:30 UTC -> 11:00:30 Kyiv)
    user = User(
        telegram_id=7007,
        timezone="Europe/Kyiv",
        reminder_interval_hours=4,
        last_periodic_reminder_at=datetime(2026, 11, 21, 9, 0, 30),  # naive UTC
    )
    db_session.add(user)
    db_session.add(
        Task(user_id=7007, title="Тестова задача", target_date=today, status=TaskStatus.todo)
    )
    await db_session.commit()

    # 13:00:00 UTC (15:00 Kyiv) -> elapsed = 3h 59m 30s >= 3h 59m (239m) -> triggers!
    t_1300_utc = datetime(2026, 11, 21, 13, 0, 0, tzinfo=timezone.utc)
    assert await process_user_periodic_reminder(mock_bot, db_session, user, now_dt=t_1300_utc) is True
    assert mock_bot.send_message.call_count == 1

    # Repeated invocation in the same minute (e.g. restart) -> idempotent, does not resend
    assert await process_user_periodic_reminder(mock_bot, db_session, user, now_dt=t_1300_utc) is False
    assert mock_bot.send_message.call_count == 1


@pytest.mark.asyncio
async def test_periodic_reminder_interval_change_4h_to_2h_and_back(
    db_session: AsyncSession,
    mock_bot: AsyncMock,
) -> None:
    """Verifies Issue #24: changing interval from 4h to 2h takes effect on the next eligible hour without reset."""
    today = date(2026, 11, 21)
    user = User(telegram_id=7008, timezone="Europe/Kyiv", reminder_interval_hours=4)
    db_session.add(user)
    db_session.add(
        Task(user_id=7008, title="Важливе завдання", target_date=today, status=TaskStatus.todo)
    )
    await db_session.commit()

    # 09:00 Kyiv (07:00 UTC) morning push stamps last_periodic_reminder_at
    await process_user_morning_push(
        mock_bot,
        db_session,
        user,
        now_dt=datetime(2026, 11, 21, 7, 0, 0, tzinfo=timezone.utc),
    )

    # User switches interval from 4h to 2h
    user.reminder_interval_hours = 2
    await db_session.commit()

    # 11:00 Kyiv (09:00 UTC) -> 2h elapsed -> triggers immediately!
    assert (
        await process_user_periodic_reminder(
            mock_bot,
            db_session,
            user,
            now_dt=datetime(2026, 11, 21, 9, 0, 0, tzinfo=timezone.utc),
        )
        is True
    )

    # User switches back to 4h -> 13:00 Kyiv (2h later) must NOT trigger; 15:00 Kyiv (4h later) MUST trigger
    user.reminder_interval_hours = 4
    await db_session.commit()

    assert (
        await process_user_periodic_reminder(
            mock_bot,
            db_session,
            user,
            now_dt=datetime(2026, 11, 21, 11, 0, 0, tzinfo=timezone.utc),
        )
        is False
    )
    assert (
        await process_user_periodic_reminder(
            mock_bot,
            db_session,
            user,
            now_dt=datetime(2026, 11, 21, 13, 0, 0, tzinfo=timezone.utc),
        )
        is True
    )


@pytest.mark.asyncio
async def test_run_timezone_checks_periodic_blocked_and_error_isolation(
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    mock_bot: AsyncMock,
) -> None:
    """Verifies Issue #24: run_timezone_checks tracks periodic_triggered, handles TelegramForbiddenError, and isolates errors."""
    today = date(2026, 11, 21)
    u_blocked = User(telegram_id=7101, timezone="Europe/Kyiv", reminder_interval_hours=4)
    u_ok = User(telegram_id=7102, timezone="Europe/Kyiv", reminder_interval_hours=4)
    u_fail = User(telegram_id=7103, timezone="Europe/Kyiv", reminder_interval_hours=4)
    db_session.add_all([u_blocked, u_ok, u_fail])
    db_session.add_all(
        [
            Task(user_id=7101, title="Task blocked", target_date=today, status=TaskStatus.todo),
            Task(user_id=7102, title="Task ok", target_date=today, status=TaskStatus.todo),
            Task(user_id=7103, title="Task fail", target_date=today, status=TaskStatus.todo),
        ]
    )
    await db_session.commit()

    async def fake_send(chat_id, **kwargs):
        if chat_id == 7101:
            raise TelegramForbiddenError(
                method="sendMessage",
                message="Forbidden: bot was blocked by the user",
            )
        if chat_id == 7103:
            raise RuntimeError("Transient network failure")
        return AsyncMock(message_id=200)

    mock_bot.send_message.side_effect = fake_send

    # 13:00 Kyiv = 11:00 UTC
    t_1300_utc = datetime(2026, 11, 21, 11, 0, 0, tzinfo=timezone.utc)
    stats = await run_timezone_checks(
        bot=mock_bot,
        sessionmaker=session_factory,
        reference_time=t_1300_utc,
    )

    assert stats["midnight_triggered"] == 0
    assert stats["morning_triggered"] == 0
    assert stats["periodic_triggered"] == 1
    assert stats["errors"] == 1  # Only u_fail counts as error; u_blocked is handled cleanly

    async with session_factory() as s:
        ref_blocked = await s.get(User, 7101)
        ref_ok = await s.get(User, 7102)
        ref_fail = await s.get(User, 7103)

        assert ref_blocked.last_periodic_reminder_at is not None
        assert ref_ok.last_periodic_reminder_at is not None
        assert ref_fail.last_periodic_reminder_at is None


@pytest.mark.asyncio
async def test_deadline_alerts_still_fire_when_periodic_reminders_disabled(
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    mock_bot: AsyncMock,
) -> None:
    """Verifies Issue #24: -1h and -10m deadline alerts still fire when reminder_interval_hours is None."""
    user = User(
        telegram_id=7201,
        timezone="Europe/Kyiv",
        reminder_interval_hours=None,
    )
    db_session.add(user)
    await db_session.commit()

    now_utc = datetime(2026, 11, 21, 11, 0, 0, tzinfo=timezone.utc)  # 13:00 Kyiv
    task_1h = Task(
        user_id=7201,
        title="Дедлайн за годину",
        target_date=now_utc.date(),
        deadline_at=now_utc + timedelta(minutes=45),
        status=TaskStatus.todo,
    )
    task_10m = Task(
        user_id=7201,
        title="Дедлайн за 10 хвилин",
        target_date=now_utc.date(),
        deadline_at=now_utc + timedelta(minutes=8),
        status=TaskStatus.todo,
    )
    db_session.add_all([task_1h, task_10m])
    await db_session.commit()

    # Periodic reminders must NOT fire
    tz_stats = await run_timezone_checks(
        bot=mock_bot,
        sessionmaker=session_factory,
        reference_time=now_utc,
    )
    assert tz_stats["periodic_triggered"] == 0
    assert mock_bot.send_message.call_count == 0

    # Deadline alerts (-1h and -10m) MUST still fire
    dl_stats = await run_deadline_checks(
        bot=mock_bot,
        sessionmaker=session_factory,
        now_dt=now_utc,
    )
    assert dl_stats["reminders_1h_sent"] == 1
    assert dl_stats["reminders_10m_sent"] == 1
    assert dl_stats["errors"] == 0
    assert mock_bot.send_message.call_count == 2
