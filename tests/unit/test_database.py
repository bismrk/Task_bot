"""Automated unit tests for SQLite database engine, PRAGMAs, and base models."""

from datetime import date, datetime, timezone
import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import StaticPool

from src.core.database import (
    configure_sqlite_pragmas,
    create_db_engine,
    get_session,
    init_db,
)
from src.models import Base, Task, TaskPriority, TaskStatus, User


@pytest.mark.asyncio
async def test_pragma_foreign_keys_enabled(db_session: AsyncSession) -> None:
    """Verifies REQ-NFR-01: PRAGMA foreign_keys is enabled (returns 1) on connections."""
    result = await db_session.execute(text("PRAGMA foreign_keys;"))
    assert result.scalar() == 1


@pytest.mark.asyncio
async def test_pragma_busy_timeout_configured(db_session: AsyncSession) -> None:
    """Verifies REQ-NFR-01: PRAGMA busy_timeout is configured to 5000ms."""
    result = await db_session.execute(text("PRAGMA busy_timeout;"))
    assert result.scalar() == 5000


@pytest.mark.asyncio
async def test_pragma_listener_on_file_engine(tmp_path) -> None:
    """Verifies REQ-NFR-01: File-based SQLite engine sets PRAGMA journal_mode=WAL."""
    db_file = tmp_path / "test_wal.db"
    file_engine = create_db_engine(f"sqlite+aiosqlite:///{db_file}")

    async with file_engine.connect() as conn:
        jm = await conn.execute(text("PRAGMA journal_mode;"))
        assert jm.scalar().lower() == "wal"
        fk = await conn.execute(text("PRAGMA foreign_keys;"))
        assert fk.scalar() == 1
        bt = await conn.execute(text("PRAGMA busy_timeout;"))
        assert bt.scalar() == 5000

    await file_engine.dispose()


@pytest.mark.asyncio
async def test_user_creation_with_defaults(db_session: AsyncSession) -> None:
    """Verifies REQ-USR-01: User is created with default timezone 'Europe/Kyiv' and UTC timestamp."""
    user = User(telegram_id=123456789)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    assert user.telegram_id == 123456789
    assert user.timezone == "Europe/Kyiv"
    assert isinstance(user.created_at, datetime)
    assert user.created_at is not None


@pytest.mark.asyncio
async def test_user_creation_with_custom_timezone(db_session: AsyncSession) -> None:
    """Verifies REQ-USR-01: User can be created with explicit custom timezone."""
    user = User(telegram_id=987654321, timezone="Europe/Warsaw")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    assert user.telegram_id == 987654321
    assert user.timezone == "Europe/Warsaw"


@pytest.mark.asyncio
async def test_task_creation_with_defaults(db_session: AsyncSession) -> None:
    """Verifies REQ-TSK-01: Task is created with default status, priority, and reminder flags."""
    user = User(telegram_id=111222333)
    db_session.add(user)
    await db_session.commit()

    task = Task(
        user_id=111222333,
        title="Buy groceries",
        target_date=date(2026, 11, 20),
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    assert task.id is not None
    assert task.user_id == 111222333
    assert task.title == "Buy groceries"
    assert task.status == TaskStatus.todo
    assert task.priority == TaskPriority.medium
    assert task.tag is None
    assert task.target_date == date(2026, 11, 20)
    assert task.deadline_at is None
    assert task.recurrence is None
    assert task.reminder_sent_1h is False
    assert task.reminder_sent_10m is False
    assert isinstance(task.created_at, datetime)
    assert task.user.telegram_id == 111222333


@pytest.mark.asyncio
async def test_task_creation_with_all_fields(db_session: AsyncSession) -> None:
    """Verifies REQ-TSK-01: Task correctly persists all optional and custom attributes."""
    user = User(telegram_id=444555666)
    db_session.add(user)
    await db_session.commit()

    deadline = datetime(2026, 11, 20, 18, 0, 0, tzinfo=timezone.utc)
    task = Task(
        user_id=444555666,
        title="Prepare presentation",
        status=TaskStatus.done,
        priority=TaskPriority.high,
        tag="work",
        target_date=date(2026, 11, 20),
        deadline_at=deadline,
        recurrence="weekdays:[0,1,2,3,4]",
        reminder_sent_1h=True,
        reminder_sent_10m=True,
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    assert task.title == "Prepare presentation"
    assert task.status == TaskStatus.done
    assert task.priority == TaskPriority.high
    assert task.tag == "work"
    assert task.target_date == date(2026, 11, 20)
    assert task.deadline_at is not None
    assert (
        task.deadline_at == deadline
        or task.deadline_at.replace(tzinfo=timezone.utc) == deadline
    )
    assert task.recurrence == "weekdays:[0,1,2,3,4]"
    assert task.reminder_sent_1h is True
    assert task.reminder_sent_10m is True


@pytest.mark.asyncio
async def test_foreign_key_enforcement_raises_integrity_error(db_session: AsyncSession) -> None:
    """Verifies REQ-TSK-01 & REQ-NFR-01: Inserting Task with unpersisted user_id raises IntegrityError."""
    orphan_task = Task(
        user_id=999999999,  # Unpersisted user ID
        title="Orphan task",
        target_date=date(2026, 11, 20),
    )
    db_session.add(orphan_task)

    with pytest.raises(IntegrityError):
        await db_session.commit()

    await db_session.rollback()


@pytest.mark.asyncio
async def test_cascade_delete_removes_associated_tasks(db_session: AsyncSession) -> None:
    """Verifies REQ-USR-01 & REQ-TSK-01: Deleting a User cascades and deletes all associated Tasks."""
    user = User(telegram_id=555666777)
    db_session.add(user)
    await db_session.commit()

    task1 = Task(
        user_id=555666777,
        title="Task 1",
        target_date=date(2026, 11, 20),
    )
    task2 = Task(
        user_id=555666777,
        title="Task 2",
        target_date=date(2026, 11, 21),
    )
    db_session.add_all([task1, task2])
    await db_session.commit()

    # Confirm tasks exist
    stmt = select(Task).where(Task.user_id == 555666777)
    tasks = (await db_session.execute(stmt)).scalars().all()
    assert len(tasks) == 2

    # Delete user
    await db_session.delete(user)
    await db_session.commit()

    # Verify associated tasks are deleted
    tasks_after_delete = (await db_session.execute(stmt)).scalars().all()
    assert len(tasks_after_delete) == 0


@pytest.mark.asyncio
async def test_init_db_creates_all_tables() -> None:
    """Verifies REQ-NFR-01: init_db utility creates all declarative metadata tables."""
    test_engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    configure_sqlite_pragmas(test_engine)

    await init_db(engine=test_engine)

    async with test_engine.connect() as conn:
        result = await conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table';")
        )
        tables = {row[0] for row in result.fetchall()}
        assert "users" in tables
        assert "tasks" in tables

    await test_engine.dispose()


@pytest.mark.asyncio
async def test_get_session_context_manager() -> None:
    """Verifies REQ-NFR-01: get_session provides an AsyncSession context manager."""
    async with get_session() as session:
        assert isinstance(session, AsyncSession)
        result = await session.execute(text("SELECT 1;"))
        assert result.scalar() == 1


@pytest.mark.asyncio
async def test_user_reminder_interval_defaults_and_explicit_null(
    db_session: AsyncSession,
) -> None:
    """Verifies Issue #24: User defaults to 4h interval & None timestamp; explicit None persists as SQL NULL."""
    default_user = User(telegram_id=700001)
    disabled_user = User(telegram_id=700002, reminder_interval_hours=None)
    custom_user = User(telegram_id=700003, reminder_interval_hours=8)

    assert default_user.reminder_interval_hours == 4
    assert disabled_user.reminder_interval_hours is None
    assert custom_user.reminder_interval_hours == 8

    db_session.add_all([default_user, disabled_user, custom_user])
    await db_session.commit()
    await db_session.refresh(default_user)
    await db_session.refresh(disabled_user)
    await db_session.refresh(custom_user)

    assert default_user.reminder_interval_hours == 4
    assert default_user.last_periodic_reminder_at is None
    assert disabled_user.reminder_interval_hours is None
    assert custom_user.reminder_interval_hours == 8

    # Confirm raw SQLite values
    rows = (
        await db_session.execute(
            text(
                "SELECT telegram_id, reminder_interval_hours, last_periodic_reminder_at "
                "FROM users WHERE telegram_id IN (700001, 700002, 700003) ORDER BY telegram_id"
            )
        )
    ).fetchall()
    assert rows == [
        (700001, 4, None),
        (700002, None, None),
        (700003, 8, None),
    ]

    # Disabling reminders on an existing user persists as NULL
    default_user.reminder_interval_hours = None
    await db_session.commit()
    val = (
        await db_session.execute(
            text("SELECT reminder_interval_hours FROM users WHERE telegram_id = 700001")
        )
    ).scalar()
    assert val is None


@pytest.mark.asyncio
async def test_init_db_migrates_legacy_users_table_idempotently(tmp_path) -> None:
    """Verifies Issue #24: init_db safely adds missing reminder columns, backfills 4, and is idempotent."""
    db_file = tmp_path / "legacy.db"
    legacy_engine = create_db_engine(f"sqlite+aiosqlite:///{db_file}")

    # Create legacy schema without reminder_interval_hours and last_periodic_reminder_at
    async with legacy_engine.begin() as conn:
        await conn.execute(
            text(
                """
                CREATE TABLE users (
                    telegram_id BIGINT PRIMARY KEY NOT NULL,
                    timezone VARCHAR NOT NULL DEFAULT 'Europe/Kyiv',
                    created_at DATETIME NOT NULL,
                    last_midnight_review_date DATE,
                    last_morning_push_date DATE
                )
                """
            )
        )
        await conn.execute(
            text(
                """
                INSERT INTO users (telegram_id, timezone, created_at)
                VALUES
                    (800001, 'Europe/Kyiv', '2026-11-01 08:00:00'),
                    (800002, 'America/New_York', '2026-11-02 09:00:00')
                """
            )
        )

    # First migration run
    await init_db(engine=legacy_engine)

    async with legacy_engine.connect() as conn:
        cols = {
            row[1]
            for row in (await conn.execute(text("PRAGMA table_info(users)"))).fetchall()
        }
        assert "reminder_interval_hours" in cols
        assert "last_periodic_reminder_at" in cols

        rows = (
            await conn.execute(
                text(
                    "SELECT telegram_id, timezone, reminder_interval_hours, last_periodic_reminder_at "
                    "FROM users ORDER BY telegram_id"
                )
            )
        ).fetchall()
        assert rows == [
            (800001, "Europe/Kyiv", 4, None),
            (800002, "America/New_York", 4, None),
        ]

    # Set custom values including NULL
    async with legacy_engine.begin() as conn:
        await conn.execute(
            text("UPDATE users SET reminder_interval_hours = NULL WHERE telegram_id = 800001")
        )
        await conn.execute(
            text("UPDATE users SET reminder_interval_hours = 2 WHERE telegram_id = 800002")
        )

    # Repeated runs must succeed without errors and preserve custom & NULL values
    await init_db(engine=legacy_engine)
    await init_db(engine=legacy_engine)

    async with legacy_engine.connect() as conn:
        rows_after = (
            await conn.execute(
                text(
                    "SELECT telegram_id, reminder_interval_hours "
                    "FROM users ORDER BY telegram_id"
                )
            )
        ).fetchall()
        assert rows_after == [
            (800001, None),
            (800002, 2),
        ]

    await legacy_engine.dispose()


@pytest.mark.asyncio
async def test_user_last_evening_summary_date_default_and_persistence(
    db_session: AsyncSession,
) -> None:
    """Verifies Issue #26: User.last_evening_summary_date defaults to None and persists dates."""
    user = User(telegram_id=700010)
    assert user.last_evening_summary_date is None

    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    assert user.last_evening_summary_date is None

    user.last_evening_summary_date = date(2026, 11, 21)
    await db_session.commit()
    await db_session.refresh(user)
    assert user.last_evening_summary_date == date(2026, 11, 21)


@pytest.mark.asyncio
async def test_init_db_migrates_last_evening_summary_date_idempotently(tmp_path) -> None:
    """Verifies Issue #26: init_db safely adds last_evening_summary_date, preserves records, and is idempotent."""
    db_file = tmp_path / "legacy_evening.db"
    legacy_engine = create_db_engine(f"sqlite+aiosqlite:///{db_file}")

    async with legacy_engine.begin() as conn:
        await conn.execute(
            text(
                """
                CREATE TABLE users (
                    telegram_id BIGINT PRIMARY KEY NOT NULL,
                    timezone VARCHAR NOT NULL DEFAULT 'Europe/Kyiv',
                    created_at DATETIME NOT NULL,
                    last_midnight_review_date DATE,
                    last_morning_push_date DATE,
                    reminder_interval_hours INTEGER DEFAULT 4,
                    last_periodic_reminder_at DATETIME
                )
                """
            )
        )
        await conn.execute(
            text(
                """
                INSERT INTO users (telegram_id, timezone, created_at, reminder_interval_hours)
                VALUES
                    (810001, 'Europe/Kyiv', '2026-11-01 08:00:00', 4),
                    (810002, 'Asia/Tokyo', '2026-11-02 09:00:00', NULL)
                """
            )
        )

    await init_db(engine=legacy_engine)

    async with legacy_engine.connect() as conn:
        cols = {
            row[1]
            for row in (await conn.execute(text("PRAGMA table_info(users)"))).fetchall()
        }
        assert "last_evening_summary_date" in cols

        rows = (
            await conn.execute(
                text(
                    "SELECT telegram_id, timezone, reminder_interval_hours, last_evening_summary_date "
                    "FROM users ORDER BY telegram_id"
                )
            )
        ).fetchall()
        assert rows == [
            (810001, "Europe/Kyiv", 4, None),
            (810002, "Asia/Tokyo", None, None),
        ]

    async with legacy_engine.begin() as conn:
        await conn.execute(
            text(
                "UPDATE users SET last_evening_summary_date = '2026-11-21' "
                "WHERE telegram_id = 810001"
            )
        )

    # Re-running init_db must be idempotent and preserve existing rows & values
    await init_db(engine=legacy_engine)
    await init_db(engine=legacy_engine)

    async with legacy_engine.connect() as conn:
        rows_after = (
            await conn.execute(
                text(
                    "SELECT telegram_id, last_evening_summary_date "
                    "FROM users ORDER BY telegram_id"
                )
            )
        ).fetchall()
        assert rows_after == [
            (810001, "2026-11-21"),
            (810002, None),
        ]

    await legacy_engine.dispose()
