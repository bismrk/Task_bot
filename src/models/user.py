"""User database model."""

from datetime import date, datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Date, DateTime, Integer, String, event, null
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.orm.attributes import set_committed_value

from src.models.base import Base

if TYPE_CHECKING:
    from src.models.task import Task


def utc_now() -> datetime:
    """Return the current timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


class User(Base):
    """Telegram user model representing registered bot and Mini App users."""

    __tablename__ = "users"

    telegram_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        nullable=False,
    )
    timezone: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default="Europe/Kyiv",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    last_midnight_review_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        default=None,
    )
    last_morning_push_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        default=None,
    )
    last_evening_summary_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        default=None,
    )
    reminder_interval_hours: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        default=4,
        server_default="4",
    )
    last_periodic_reminder_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )

    tasks: Mapped[list["Task"]] = relationship(
        "Task",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def __init__(self, **kwargs):
        if "reminder_interval_hours" not in kwargs:
            kwargs["reminder_interval_hours"] = 4
            self._explicit_null_reminder_interval = False
        else:
            self._explicit_null_reminder_interval = (
                kwargs["reminder_interval_hours"] is None
            )
        super().__init__(**kwargs)


@event.listens_for(User, "before_insert")
def _preserve_explicit_null_reminder_interval(mapper, connection, target: User) -> None:
    """Ensure explicitly disabled reminder_interval_hours=None inserts NULL rather than column default."""
    if (
        getattr(target, "_explicit_null_reminder_interval", False)
        and target.reminder_interval_hours is None
    ):
        target.reminder_interval_hours = null()  # type: ignore[assignment]


@event.listens_for(User, "after_insert")
def _restore_explicit_null_reminder_interval(mapper, connection, target: User) -> None:
    """Restore Python None on the ORM instance after inserting SQL NULL."""
    if getattr(target, "_explicit_null_reminder_interval", False):
        set_committed_value(target, "reminder_interval_hours", None)
        target._explicit_null_reminder_interval = False
