"""Pydantic schemas for task extraction, creation, update, and reading."""

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.models.task import TaskPriority, TaskStatus


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


class TaskCreate(BaseModel):
    """Schema for creating a new task."""

    title: str = Field(..., max_length=255)
    target_date: date
    deadline_at: datetime | None = None
    priority: TaskPriority = TaskPriority.medium
    tag: str | None = Field(default=None, max_length=50)
    recurrence: str | None = None

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


class TaskUpdate(BaseModel):
    """Schema for partially updating an existing task."""

    title: str | None = None
    target_date: date | None = None
    deadline_at: datetime | None = None
    priority: TaskPriority | None = None
    tag: str | None = None
    status: TaskStatus | None = None
    recurrence: str | None = None

    @field_validator("title", mode="before")
    @classmethod
    def validate_title(cls, v: Any) -> str | None:
        """Ensure title if provided is a non-empty string and stripped of whitespace."""
        if v is None:
            return None
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
    def validate_priority(cls, v: Any) -> TaskPriority | None:
        """Normalize priority strings to TaskPriority enum if provided."""
        if v is None:
            return None
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

    @field_validator("status", mode="before")
    @classmethod
    def validate_status(cls, v: Any) -> TaskStatus | None:
        """Normalize status strings to TaskStatus enum if provided."""
        if v is None:
            return None
        if isinstance(v, TaskStatus):
            return v
        if isinstance(v, str):
            val = v.strip().lower()
            if val in ("todo", "активно", "до виконання"):
                return TaskStatus.todo
            if val in ("done", "виконано", "зроблено"):
                return TaskStatus.done
            if val in ("canceled", "cancelled", "скасовано"):
                return TaskStatus.canceled
            try:
                return TaskStatus(val)
            except ValueError:
                raise ValueError(f"Invalid status: {v}")
        raise ValueError("Invalid status type")

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


class TaskRead(BaseModel):
    """Schema for reading a persisted task record."""

    id: int
    user_id: int
    title: str
    status: TaskStatus
    priority: TaskPriority
    tag: str | None = None
    target_date: date
    deadline_at: datetime | None = None
    recurrence: str | None = None
    reminder_sent_1h: bool
    reminder_sent_10m: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CalendarDaySummary(BaseModel):
    """Daily summary representing task aggregation and status for calendar view (REQ-TMA-03)."""

    date: date
    total_tasks: int = Field(default=0, ge=0)
    completed_tasks: int = Field(default=0, ge=0)
    status: Literal["all_done", "partial", "todo_only"]

    @model_validator(mode="before")
    @classmethod
    def compute_status_if_missing(cls, data: Any) -> Any:
        """Infer status from completed_tasks and total_tasks if not explicitly provided."""
        if isinstance(data, dict):
            total = data.get("total_tasks", 0)
            completed = data.get("completed_tasks", 0)
            if "status" not in data or data["status"] is None:
                if completed == total and total > 0:
                    data["status"] = "all_done"
                elif 0 < completed < total:
                    data["status"] = "partial"
                else:
                    data["status"] = "todo_only"
        return data

    @model_validator(mode="after")
    def verify_status_consistency(self) -> "CalendarDaySummary":
        """Verify that status accurately reflects the completion ratio."""
        if self.completed_tasks == self.total_tasks and self.total_tasks > 0:
            expected = "all_done"
        elif 0 < self.completed_tasks < self.total_tasks:
            expected = "partial"
        else:
            expected = "todo_only"
        if self.status != expected:
            raise ValueError(
                f"Status '{self.status}' does not match completion ratio: "
                f"total={self.total_tasks}, completed={self.completed_tasks} (expected '{expected}')"
            )
        return self

    model_config = ConfigDict(from_attributes=True)

