"""User management service and timezone handling logic."""

from datetime import datetime, timezone as dt_timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user import User


def validate_timezone(timezone: str) -> str:
    """Validate an IANA timezone string using zoneinfo.ZoneInfo.

    Args:
        timezone: The timezone string to validate.

    Returns:
        The validated timezone string.

    Raises:
        ValueError: If the timezone identifier is invalid.
    """
    try:
        ZoneInfo(timezone)
    except Exception as e:
        raise ValueError(f"Invalid timezone: {timezone}") from e
    return timezone


async def get_user(session: AsyncSession, telegram_id: int) -> User | None:
    """Retrieve a User database record by telegram_id.

    Args:
        session: Active SQLAlchemy async session.
        telegram_id: Telegram user ID.

    Returns:
        The User record if found, or None if the user does not exist.
    """
    stmt = select(User).where(User.telegram_id == telegram_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_or_create_user(
    session: AsyncSession,
    telegram_id: int,
    timezone: str = "Europe/Kyiv",
) -> tuple[User, bool]:
    """Retrieve an existing user or insert and commit a new user record.

    If a user with the given telegram_id exists, returns (user, False)
    without modifying the user's existing timezone or attributes.

    If no user exists, validates the timezone, creates and commits the User,
    and returns (user, True). If the timezone is invalid for a non-existent user,
    raises ValueError and does not insert any record.

    Args:
        session: Active SQLAlchemy async session.
        telegram_id: Telegram user ID.
        timezone: IANA timezone identifier, defaults to 'Europe/Kyiv'.

    Returns:
        A tuple of (user, created) where created is True if a new user was inserted.

    Raises:
        ValueError: If the timezone identifier is invalid for a new user.
    """
    user = await get_user(session, telegram_id)
    if user is not None:
        return user, False

    validated_tz = validate_timezone(timezone)
    user = User(telegram_id=telegram_id, timezone=validated_tz)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user, True


async def update_user_timezone(
    session: AsyncSession,
    telegram_id: int,
    timezone: str,
) -> User:
    """Update a user's timezone preference and commit the transaction.

    Validates that the timezone is a valid IANA timezone and that the user exists.
    Updates user.timezone, commits the transaction, and returns the updated User.

    Args:
        session: Active SQLAlchemy async session.
        telegram_id: Telegram user ID.
        timezone: New IANA timezone identifier.

    Returns:
        The updated User record.

    Raises:
        ValueError: If the timezone identifier is invalid.
        ValueError: If no user with telegram_id exists.
    """
    validated_tz = validate_timezone(timezone)

    user = await get_user(session, telegram_id)
    if user is None:
        raise ValueError(f"User with telegram_id {telegram_id} does not exist")

    user.timezone = validated_tz
    await session.commit()
    await session.refresh(user)
    return user


def validate_reminder_interval(interval: int | None) -> int | None:
    """Validate a periodic reminder interval in hours (1..24) or None (disabled).

    Args:
        interval: The reminder interval in hours (1..24) or None.

    Returns:
        The validated interval or None.

    Raises:
        ValueError: If the interval is a boolean, not an integer, or outside 1..24.
    """
    if interval is None:
        return None
    if isinstance(interval, bool) or not isinstance(interval, int):
        raise ValueError(
            f"Invalid reminder interval: {interval}. Must be an integer between 1 and 24, or None."
        )
    if interval < 1 or interval > 24:
        raise ValueError(
            f"Invalid reminder interval: {interval}. Must be between 1 and 24 hours."
        )
    return interval


async def update_user_reminder_interval(
    session: AsyncSession,
    telegram_id: int,
    reminder_interval_hours: int | None,
) -> User:
    """Update a user's periodic reminder interval preference and commit the transaction.

    Args:
        session: Active SQLAlchemy async session.
        telegram_id: Telegram user ID.
        reminder_interval_hours: Interval in hours (1..24) or None to disable.

    Returns:
        The updated User record.

    Raises:
        ValueError: If the interval is invalid or no user with telegram_id exists.
    """
    validated_interval = validate_reminder_interval(reminder_interval_hours)

    user = await get_user(session, telegram_id)
    if user is None:
        raise ValueError(f"User with telegram_id {telegram_id} does not exist")

    user.reminder_interval_hours = validated_interval
    await session.commit()
    await session.refresh(user)
    return user


def get_user_local_time(user: User, dt: datetime | None = None) -> datetime:
    """Return a timezone-aware datetime in the user's local timezone.

    If dt is None, uses current UTC time.
    If dt is naive (no tzinfo), treats it as UTC before converting.

    Args:
        user: The User database record.
        dt: Optional datetime to convert.

    Returns:
        Timezone-aware datetime converted to the user's timezone.
    """
    user_tz = ZoneInfo(user.timezone)
    if dt is None:
        target_dt = datetime.now(dt_timezone.utc)
    elif dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        target_dt = dt.replace(tzinfo=dt_timezone.utc)
    else:
        target_dt = dt

    return target_dt.astimezone(user_tz)
