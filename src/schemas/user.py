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


class UserRead(UserBase):
    """User read schema for serializing user records from database or API."""

    model_config = ConfigDict(from_attributes=True)

    telegram_id: int
    timezone: str
    created_at: datetime
