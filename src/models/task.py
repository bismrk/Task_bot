"""Task database model and status/priority enums."""

import enum
from datetime import date, datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base

if TYPE_CHECKING:
    from src.models.user import User


class TaskStatus(str, enum.Enum):
    """Task lifecycle statuses."""

    todo = "todo"
    done = "done"
    canceled = "canceled"


class TaskPriority(str, enum.Enum):
    """Task urgency/importance levels."""

    low = "low"
    medium = "medium"
    high = "high"


def utc_now() -> datetime:
    """Return the current timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


class Task(Base):
    """Task entity representing a user task with scheduling, recurrence, and reminders."""

    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.telegram_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    status: Mapped[TaskStatus] = mapped_column(
        SAEnum(TaskStatus),
        nullable=False,
        default=TaskStatus.todo,
    )
    priority: Mapped[TaskPriority] = mapped_column(
        SAEnum(TaskPriority),
        nullable=False,
        default=TaskPriority.medium,
    )
    tag: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        default=None,
    )
    target_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )
    deadline_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )
    recurrence: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        default=None,
    )
    reminder_sent_1h: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    reminder_sent_10m: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    user: Mapped["User"] = relationship(
        "User",
        back_populates="tasks",
    )
