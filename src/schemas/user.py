"""Pydantic schemas for user data validation and serialization."""

from datetime import datetime
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, field_validator


def _validate_timezone(tz: str) -> str:
    """Validate that the string is a recognized IANA timezone identifier."""
    try:
        ZoneInfo(tz)
    except Exception as e:
        raise ValueError(f"Invalid timezone: {tz}") from e
    return tz


class UserBase(BaseModel):
    """Base user schema containing shared user attributes."""

    timezone: str = "Europe/Kyiv"

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v: str) -> str:
        return _validate_timezone(v)


class UserCreate(UserBase):
    """User creation schema requiring telegram_id and inheriting timezone default."""

    telegram_id: int


class UserUpdate(BaseModel):
    """User update schema for updating user timezone."""

    timezone: str

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v: str) -> str:
        return _validate_timezone(v)


class TimezoneUpdate(BaseModel):
    """Schema for updating user timezone."""

    timezone: str

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v: str) -> str:
        return _validate_timezone(v)


class ReminderIntervalUpdate(BaseModel):
    """Schema for updating user periodic reminder interval."""

    reminder_interval_hours: int | None

    @field_validator("reminder_interval_hours", mode="before")
    @classmethod
    def validate_reminder_interval(cls, v: object) -> int | None:
        if v is None:
            return None
        if isinstance(v, bool) or not isinstance(v, int):
            raise ValueError(
                "reminder_interval_hours must be an integer between 1 and 24, or null"
            )
        if v < 1 or v > 24:
            raise ValueError(
                "reminder_interval_hours must be between 1 and 24, or null"
            )
        return v


class UserRead(UserBase):
    """User read schema for serializing user records from database or API."""

    model_config = ConfigDict(from_attributes=True)

    telegram_id: int
    timezone: str
    reminder_interval_hours: int | None = 4
    created_at: datetime
