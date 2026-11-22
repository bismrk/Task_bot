"""Automated unit tests for user service, timezone operations, and Pydantic schemas."""

from datetime import datetime, timezone
import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from zoneinfo import ZoneInfo

from src.models.user import User
from src.schemas.user import (
    ReminderIntervalUpdate,
    UserBase,
    UserCreate,
    UserRead,
    UserUpdate,
)
from src.services.user_service import (
    get_or_create_user,
    get_user,
    get_user_local_time,
    update_user_reminder_interval,
    update_user_timezone,
    validate_reminder_interval,
    validate_timezone,
)


# ============================================================================
# validate_timezone Tests
# ============================================================================


def test_validate_timezone_with_valid_identifiers() -> None:
    """Verifies REQ-USR-02: validate_timezone accepts valid IANA timezone identifiers."""
    valid_zones = ["Europe/Kyiv", "UTC", "America/New_York", "Asia/Tokyo", "Australia/Sydney"]
    for tz in valid_zones:
        assert validate_timezone(tz) == tz


def test_validate_timezone_with_invalid_identifiers() -> None:
    """Verifies REQ-USR-02: validate_timezone raises ValueError on invalid timezone strings."""
    invalid_zones = ["Mars/Olympus", "Invalid/TZ", "", "Kyiv", "Europe/InvalidCity"]
    for tz in invalid_zones:
        with pytest.raises(ValueError, match=f"Invalid timezone: {tz}"):
            validate_timezone(tz)


# ============================================================================
# get_user Tests
# ============================================================================


@pytest.mark.asyncio
async def test_get_user_returns_user_when_exists(db_session: AsyncSession) -> None:
    """Verifies REQ-USR-01: get_user returns the User database record if found."""
    new_user = User(telegram_id=123456789, timezone="Europe/Kyiv")
    db_session.add(new_user)
    await db_session.commit()

    retrieved = await get_user(db_session, 123456789)
    assert retrieved is not None
    assert retrieved.telegram_id == 123456789
    assert retrieved.timezone == "Europe/Kyiv"


@pytest.mark.asyncio
async def test_get_user_returns_none_when_not_found(db_session: AsyncSession) -> None:
    """Verifies REQ-USR-01: get_user returns None when the user does not exist."""
    retrieved = await get_user(db_session, 999999999)
    assert retrieved is None


# ============================================================================
# get_or_create_user Tests
# ============================================================================


@pytest.mark.asyncio
async def test_get_or_create_user_creates_new_user_with_default_timezone(
    db_session: AsyncSession,
) -> None:
    """Verifies REQ-USR-01: get_or_create_user creates new User with default 'Europe/Kyiv' timezone."""
    telegram_id = 111222333

    user, created = await get_or_create_user(db_session, telegram_id)

    assert created is True
    assert user.telegram_id == telegram_id
    assert user.timezone == "Europe/Kyiv"
    assert user.created_at is not None

    # Verify directly from database session
    stmt = select(User).where(User.telegram_id == telegram_id)
    persisted = (await db_session.execute(stmt)).scalar_one_or_none()
    assert persisted is not None
    assert persisted.telegram_id == telegram_id
    assert persisted.timezone == "Europe/Kyiv"


@pytest.mark.asyncio
async def test_get_or_create_user_with_custom_valid_timezone(
    db_session: AsyncSession,
) -> None:
    """Verifies REQ-USR-01: get_or_create_user creates new User with custom valid timezone."""
    telegram_id = 444555666
    custom_tz = "America/New_York"

    user, created = await get_or_create_user(db_session, telegram_id, timezone=custom_tz)

    assert created is True
    assert user.telegram_id == telegram_id
    assert user.timezone == custom_tz


@pytest.mark.asyncio
async def test_get_or_create_user_idempotent_preserves_existing_user(
    db_session: AsyncSession,
) -> None:
    """Verifies REQ-USR-01: get_or_create_user returns (user, False) and preserves custom timezone."""
    telegram_id = 777888999
    initial_tz = "Europe/Warsaw"

    # Initial creation with custom timezone
    user1, created1 = await get_or_create_user(db_session, telegram_id, timezone=initial_tz)
    assert created1 is True
    assert user1.timezone == initial_tz
    original_created_at = user1.created_at

    # Subsequent call with default or different timezone must not overwrite
    user2, created2 = await get_or_create_user(db_session, telegram_id, timezone="Europe/Kyiv")
    assert created2 is False
    assert user2.telegram_id == telegram_id
    assert user2.timezone == initial_tz
    assert user2.created_at == original_created_at

    # Check total row count in users table
    stmt = select(User).where(User.telegram_id == telegram_id)
    records = (await db_session.execute(stmt)).scalars().all()
    assert len(records) == 1


@pytest.mark.asyncio
async def test_get_or_create_user_with_invalid_timezone_raises_value_error(
    db_session: AsyncSession,
) -> None:
    """Verifies REQ-USR-01 & REQ-USR-02: get_or_create_user with invalid timezone raises ValueError and does not persist."""
    telegram_id = 555666777
    invalid_tz = "Mars/Olympus"

    with pytest.raises(ValueError, match=f"Invalid timezone: {invalid_tz}"):
        await get_or_create_user(db_session, telegram_id, timezone=invalid_tz)

    # Verify no record was inserted
    user = await get_user(db_session, telegram_id)
    assert user is None


# ============================================================================
# update_user_timezone Tests
# ============================================================================


@pytest.mark.asyncio
async def test_update_user_timezone_success(db_session: AsyncSession) -> None:
    """Verifies REQ-USR-02: update_user_timezone updates and commits valid IANA timezone."""
    telegram_id = 123123123
    user, _ = await get_or_create_user(db_session, telegram_id, timezone="Europe/Kyiv")
    assert user.timezone == "Europe/Kyiv"

    updated_user = await update_user_timezone(db_session, telegram_id, timezone="Europe/London")
    assert updated_user.timezone == "Europe/London"

    # Verify directly from database session
    stmt = select(User).where(User.telegram_id == telegram_id)
    persisted = (await db_session.execute(stmt)).scalar_one_or_none()
    assert persisted is not None
    assert persisted.timezone == "Europe/London"


@pytest.mark.asyncio
async def test_update_user_timezone_invalid_raises_value_error_and_preserves_db(
    db_session: AsyncSession,
) -> None:
    """Verifies REQ-USR-02: update_user_timezone with invalid timezone raises ValueError and preserves previous timezone."""
    telegram_id = 234234234
    user, _ = await get_or_create_user(db_session, telegram_id, timezone="Europe/Kyiv")
    assert user.timezone == "Europe/Kyiv"

    invalid_tz = "Mars/Olympus"
    with pytest.raises(ValueError, match=f"Invalid timezone: {invalid_tz}"):
        await update_user_timezone(db_session, telegram_id, timezone=invalid_tz)

    # Verify original timezone is preserved in database
    persisted = await get_user(db_session, telegram_id)
    assert persisted is not None
    assert persisted.timezone == "Europe/Kyiv"


@pytest.mark.asyncio
async def test_update_user_timezone_non_existent_user_raises_value_error(
    db_session: AsyncSession,
) -> None:
    """Verifies REQ-USR-02: update_user_timezone for non-existent user raises ValueError."""
    non_existent_id = 987987987
    with pytest.raises(ValueError, match=f"User with telegram_id {non_existent_id} does not exist"):
        await update_user_timezone(db_session, non_existent_id, timezone="UTC")


# ============================================================================
# get_user_local_time Tests
# ============================================================================


def test_get_user_local_time_default_none() -> None:
    """Verifies REQ-USR-01 & REQ-USR-02: get_user_local_time uses current UTC time when dt is None."""
    user = User(telegram_id=1, timezone="Europe/Kyiv")
    before_utc = datetime.now(timezone.utc)
    local_time = get_user_local_time(user)
    after_utc = datetime.now(timezone.utc)

    assert local_time.tzinfo is not None
    assert str(local_time.tzinfo) == "Europe/Kyiv"
    # Local time converted back to UTC should be bounded by before and after
    local_utc = local_time.astimezone(timezone.utc)
    assert before_utc <= local_utc <= after_utc


def test_get_user_local_time_explicit_utc() -> None:
    """Verifies REQ-USR-01 & REQ-USR-02: get_user_local_time converts explicit UTC datetime to user timezone."""
    user = User(telegram_id=1, timezone="Europe/Kyiv")
    # In winter time (standard time), Kyiv is UTC+2
    dt_utc = datetime(2026, 11, 19, 12, 0, 0, tzinfo=timezone.utc)
    local_time = get_user_local_time(user, dt_utc)

    assert local_time.tzinfo is not None
    assert str(local_time.tzinfo) == "Europe/Kyiv"
    assert local_time.year == 2026
    assert local_time.month == 11
    assert local_time.day == 19
    assert local_time.hour == 14
    assert local_time.minute == 0
    assert local_time.second == 0


def test_get_user_local_time_naive_datetime() -> None:
    """Verifies REQ-USR-01 & REQ-USR-02: get_user_local_time treats naive datetime inputs as UTC."""
    # America/New_York in winter (EST) is UTC-5
    user = User(telegram_id=1, timezone="America/New_York")
    naive_dt = datetime(2026, 11, 19, 15, 0, 0)

    local_time = get_user_local_time(user, naive_dt)

    assert local_time.tzinfo is not None
    assert str(local_time.tzinfo) == "America/New_York"
    # 15:00 UTC - 5 hours = 10:00 EST
    assert local_time.year == 2026
    assert local_time.month == 11
    assert local_time.day == 19
    assert local_time.hour == 10
    assert local_time.minute == 0
    assert local_time.second == 0


# ============================================================================
# Pydantic Schema Tests
# ============================================================================


def test_pydantic_user_base_schema() -> None:
    """Verifies REQ-USR-02: UserBase defaults timezone to 'Europe/Kyiv' and validates IANA identifiers."""
    # Default timezone
    base = UserBase()
    assert base.timezone == "Europe/Kyiv"

    # Valid custom timezone
    custom_base = UserBase(timezone="UTC")
    assert custom_base.timezone == "UTC"

    # Invalid timezone raises ValidationError
    with pytest.raises(ValidationError) as exc_info:
        UserBase(timezone="Mars/Olympus")
    assert "Invalid timezone: Mars/Olympus" in str(exc_info.value)


def test_pydantic_user_create_schema() -> None:
    """Verifies REQ-USR-01 & REQ-USR-02: UserCreate defines telegram_id, inherits default timezone, validates custom tz."""
    # Default timezone inheritance
    created = UserCreate(telegram_id=12345)
    assert created.telegram_id == 12345
    assert created.timezone == "Europe/Kyiv"

    # Custom timezone
    created_custom = UserCreate(telegram_id=12345, timezone="Asia/Tokyo")
    assert created_custom.telegram_id == 12345
    assert created_custom.timezone == "Asia/Tokyo"

    # Missing telegram_id raises ValidationError
    with pytest.raises(ValidationError):
        UserCreate()  # type: ignore[call-arg]

    # Invalid timezone raises ValidationError
    with pytest.raises(ValidationError) as exc_info:
        UserCreate(telegram_id=12345, timezone="Atlantis/City")
    assert "Invalid timezone: Atlantis/City" in str(exc_info.value)


def test_pydantic_user_update_schema() -> None:
    """Verifies REQ-USR-02: UserUpdate defines required timezone and validates IANA timezone identifiers."""
    # Valid timezone
    update = UserUpdate(timezone="Europe/Berlin")
    assert update.timezone == "Europe/Berlin"

    # Missing timezone raises ValidationError (it is required)
    with pytest.raises(ValidationError):
        UserUpdate()  # type: ignore[call-arg]

    # Invalid timezone raises ValidationError
    with pytest.raises(ValidationError) as exc_info:
        UserUpdate(timezone="Mars/Olympus")
    assert "Invalid timezone: Mars/Olympus" in str(exc_info.value)


def test_pydantic_user_read_schema() -> None:
    """Verifies REQ-USR-01 & REQ-USR-02: UserRead validates, serializes, and supports from_attributes."""
    now = datetime.now(timezone.utc)

    # Direct initialization
    user_read = UserRead(
        telegram_id=987654,
        timezone="Europe/Kyiv",
        created_at=now,
    )
    assert user_read.telegram_id == 987654
    assert user_read.timezone == "Europe/Kyiv"
    assert user_read.created_at == now

    # Serialization to dict
    dumped = user_read.model_dump()
    assert dumped["telegram_id"] == 987654
    assert dumped["timezone"] == "Europe/Kyiv"
    assert dumped["created_at"] == now

    # Validation from ORM object (from_attributes=True)
    orm_user = User(
        telegram_id=112233,
        timezone="America/Chicago",
        created_at=now,
    )
    from_orm = UserRead.model_validate(orm_user)
    assert from_orm.telegram_id == 112233
    assert from_orm.timezone == "America/Chicago"
    assert from_orm.created_at == now

    # Invalid timezone raises ValidationError
    with pytest.raises(ValidationError) as exc_info:
        UserRead(telegram_id=1, timezone="Moon/Base", created_at=now)
    assert "Invalid timezone: Moon/Base" in str(exc_info.value)


# ============================================================================
# Reminder Interval Validation, Service & Schema Tests (Issue #24)
# ============================================================================


def test_validate_reminder_interval_valid() -> None:
    """Verifies Issue #24: validate_reminder_interval accepts None and integers 1..24."""
    assert validate_reminder_interval(None) is None
    for hours in range(1, 25):
        assert validate_reminder_interval(hours) == hours


@pytest.mark.parametrize(
    "invalid_value",
    [0, -1, -24, 25, 100, True, False, 2.5, 4.0, "4", "abc"],
)
def test_validate_reminder_interval_invalid(invalid_value) -> None:
    """Verifies Issue #24: validate_reminder_interval rejects 0, negatives, >24, booleans, floats, strings."""
    with pytest.raises(ValueError):
        validate_reminder_interval(invalid_value)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_update_user_reminder_interval_success_and_disable(
    db_session: AsyncSession,
) -> None:
    """Verifies Issue #24: update_user_reminder_interval updates, disables (NULL), and re-enables."""
    telegram_id = 333444555
    user, _ = await get_or_create_user(db_session, telegram_id)
    assert user.reminder_interval_hours == 4

    # Update to custom value 7
    updated = await update_user_reminder_interval(db_session, telegram_id, 7)
    assert updated.reminder_interval_hours == 7

    # Disable (None)
    disabled = await update_user_reminder_interval(db_session, telegram_id, None)
    assert disabled.reminder_interval_hours is None

    # Verify persisted NULL from fresh query
    persisted = await get_user(db_session, telegram_id)
    assert persisted is not None
    assert persisted.reminder_interval_hours is None

    # Re-enable to 24
    reenabled = await update_user_reminder_interval(db_session, telegram_id, 24)
    assert reenabled.reminder_interval_hours == 24


@pytest.mark.asyncio
async def test_update_user_reminder_interval_invalid_preserves_db(
    db_session: AsyncSession,
) -> None:
    """Verifies Issue #24: invalid reminder interval raises ValueError and leaves DB untouched."""
    telegram_id = 333444556
    await get_or_create_user(db_session, telegram_id)

    for bad in (0, -3, 25, True, False):
        with pytest.raises(ValueError):
            await update_user_reminder_interval(db_session, telegram_id, bad)  # type: ignore[arg-type]

    persisted = await get_user(db_session, telegram_id)
    assert persisted is not None
    assert persisted.reminder_interval_hours == 4


@pytest.mark.asyncio
async def test_update_user_reminder_interval_missing_user_raises(
    db_session: AsyncSession,
) -> None:
    """Verifies Issue #24: update_user_reminder_interval raises ValueError for non-existent user."""
    with pytest.raises(ValueError, match="does not exist"):
        await update_user_reminder_interval(db_session, 999888777, 2)


def test_pydantic_reminder_interval_update_schema() -> None:
    """Verifies Issue #24: ReminderIntervalUpdate accepts None and 1..24, rejects invalid values & missing key."""
    assert ReminderIntervalUpdate(reminder_interval_hours=None).reminder_interval_hours is None
    for hours in (1, 4, 12, 24):
        assert ReminderIntervalUpdate(reminder_interval_hours=hours).reminder_interval_hours == hours

    # Missing required field
    with pytest.raises(ValidationError):
        ReminderIntervalUpdate()  # type: ignore[call-arg]

    # Out of bounds, booleans, floats, strings
    for invalid in (0, -1, 25, True, False, 2.5, 4.0, "4", "abc"):
        with pytest.raises(ValidationError):
            ReminderIntervalUpdate(reminder_interval_hours=invalid)  # type: ignore[arg-type]


def test_pydantic_user_read_reminder_interval_hours() -> None:
    """Verifies Issue #24: UserRead defaults reminder_interval_hours to 4 and preserves None/custom from ORM."""
    now = datetime.now(timezone.utc)

    default_read = UserRead(telegram_id=1, timezone="Europe/Kyiv", created_at=now)
    assert default_read.reminder_interval_hours == 4

    disabled_read = UserRead(
        telegram_id=2,
        timezone="Europe/Kyiv",
        reminder_interval_hours=None,
        created_at=now,
    )
    assert disabled_read.reminder_interval_hours is None

    orm_default = User(telegram_id=3, timezone="UTC", created_at=now)
    assert UserRead.model_validate(orm_default).reminder_interval_hours == 4

    orm_disabled = User(
        telegram_id=4,
        timezone="UTC",
        reminder_interval_hours=None,
        created_at=now,
    )
    assert UserRead.model_validate(orm_disabled).reminder_interval_hours is None
