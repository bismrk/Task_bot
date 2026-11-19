"""Pydantic schemas for task extraction via Gemini AI."""

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from src.models.task import TaskPriority


class ExtractedTask(BaseModel):
    """Structured representation of an extracted task from text or voice."""

    title: str = Field(..., max_length=255)
    target_date: date
    deadline_at: datetime | None = None
    priority: TaskPriority = TaskPriority.medium
    tag: str | None = Field(default=None, max_length=50)

    @field_validator("title", mode="before")
    @classmethod
    def validate_title(cls, v: Any) -> str:
        """Ensure title is a non-empty string and stripped of whitespace."""
        if not isinstance(v, str):
            raise ValueError("Title must be a string")
        v = v.strip()
        if not v:
            raise ValueError("Title cannot be empty")
        if len(v) > 255:
            raise ValueError("Title must be at most 255 characters")
        return v

    @field_validator("priority", mode="before")
    @classmethod
    def validate_priority(cls, v: Any) -> TaskPriority:
        """Normalize priority strings to TaskPriority enum."""
        if isinstance(v, TaskPriority):
            return v
        if isinstance(v, str):
            val = v.strip().lower()
            if val in ("high", "терміново", "важливо", "високий", "urgent"):
                return TaskPriority.high
            if val in ("low", "низький"):
                return TaskPriority.low
            if val in ("medium", "середній"):
                return TaskPriority.medium
            try:
                return TaskPriority(val)
            except ValueError:
                return TaskPriority.medium
        return TaskPriority.medium

    @field_validator("tag", mode="before")
    @classmethod
    def validate_tag(cls, v: Any) -> str | None:
        """Strip '#' prefix, trim whitespace, and limit length to 50 chars."""
        if v is None:
            return None
        if not isinstance(v, str):
            return None
        v = v.strip()
        if v.startswith("#"):
            v = v.lstrip("#").strip()
        if not v:
            return None
        return v[:50]

    @field_validator("deadline_at", mode="after")
    @classmethod
    def check_deadline_at_timezone(cls, v: datetime | None) -> datetime | None:
        """Ensure deadline_at is timezone-aware if present."""
        if v is not None and v.tzinfo is None:
            raise ValueError("deadline_at must be timezone-aware")
        return v


class TaskExtractionResult(BaseModel):
    """Container schema for parsed tasks from Gemini."""

    tasks: list[ExtractedTask] = Field(default_factory=list)
