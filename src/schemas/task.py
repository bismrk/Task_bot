"""Pydantic schemas for task extraction, creation, update, and reading."""

from datetime import date, datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.models.task import TaskPriority, TaskStatus


def validate_recurrence_rule(v: Any) -> str | None:
    """Validate and normalize recurrence rule string.

    Accepts None, 'daily', 'weekdays', or 'weekdays:[<digits>]' with digits in range 0..6.
    Normalizes custom weekdays into unique sorted ascending list.
    Rejects empty list, invalid digits, or unknown formats with ValueError.
    """
    if v is None:
        return None
    if not isinstance(v, str):
        raise ValueError("Recurrence must be a string or None")
    val = v.strip()
    if not val:
        raise ValueError("Recurrence cannot be empty")
    val_lower = val.lower()
    if val_lower == "daily":
        return "daily"
    if val_lower == "weekdays":
        return "weekdays"
    if val_lower.startswith("weekdays:[") and val_lower.endswith("]"):
        inner = val[len("weekdays:[") : -1].strip()
        if not inner:
            raise ValueError("Recurrence weekdays list cannot be empty")
        parts = inner.split(",")
        days: set[int] = set()
        for part in parts:
            p = part.strip()
            if not p or not p.isdigit():
                raise ValueError(f"Invalid weekday index: {p}")
            day = int(p)
            if day < 0 or day > 6:
                raise ValueError(f"Weekday index out of range (0..6): {day}")
            days.add(day)
        if not days:
            raise ValueError("Recurrence weekdays list cannot be empty")
        return f"weekdays:[{','.join(str(d) for d in sorted(days))}]"
    raise ValueError(f"Invalid recurrence format: '{v}'")


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
        """Ensure deadline_at is timezone-aware if present and normalized to UTC."""
        if v is not None and v.tzinfo is None:
            raise ValueError("deadline_at must be timezone-aware")
        if v is not None:
            return v.astimezone(timezone.utc)
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

    @field_validator("recurrence", mode="before")
    @classmethod
    def validate_recurrence(cls, v: Any) -> str | None:
        """Validate and normalize recurrence rule."""
        return validate_recurrence_rule(v)

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
        """Ensure deadline_at is timezone-aware if present and normalized to UTC."""
        if v is not None and v.tzinfo is None:
            raise ValueError("deadline_at must be timezone-aware")
        if v is not None:
            return v.astimezone(timezone.utc)
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

    @field_validator("recurrence", mode="before")
    @classmethod
    def validate_recurrence(cls, v: Any) -> str | None:
        """Validate and normalize recurrence rule if provided."""
        return validate_recurrence_rule(v)

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
        """Ensure deadline_at is timezone-aware if present and normalized to UTC."""
        if v is not None and v.tzinfo is None:
            raise ValueError("deadline_at must be timezone-aware")
        if v is not None:
            return v.astimezone(timezone.utc)
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

    @field_validator("deadline_at", "created_at", mode="after")
    @classmethod
    def normalize_utc_datetimes(cls, v: datetime | None) -> datetime | None:
        """Normalize naive or non-UTC datetimes to timezone-aware UTC."""
        if v is None:
            return None
        if v.tzinfo is None or v.tzinfo.utcoffset(v) is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)

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


class DailyTrendItem(BaseModel):
    """Daily productivity aggregation item for charts and trend tracking."""

    date: date
    completed_tasks: int = Field(default=0, ge=0)
    total_tasks: int = Field(default=0, ge=0)
    completion_rate: float = Field(default=0.0, ge=0.0, le=100.0)

    model_config = ConfigDict(from_attributes=True)


class TagBreakdownItem(BaseModel):
    """Category tag aggregation breakdown item."""

    tag: str
    count: int = Field(default=0, ge=0)
    completed_count: int = Field(default=0, ge=0)
    percentage: float = Field(default=0.0, ge=0.0, le=100.0)

    model_config = ConfigDict(from_attributes=True)


class AnalyticsResponse(BaseModel):
    """Productivity analytics dashboard response."""

    streak_current: int = Field(default=0, ge=0)
    streak_longest: int = Field(default=0, ge=0)
    total_tasks: int = Field(default=0, ge=0)
    completed_tasks: int = Field(default=0, ge=0)
    completion_rate: float = Field(default=0.0, ge=0.0, le=100.0)
    daily_trends: list[DailyTrendItem] = Field(default_factory=list)
    tag_breakdown: list[TagBreakdownItem] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


