"""Deadline reminder inline keyboards and callback data."""

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


class DeadlineCallback(CallbackData, prefix="deadline"):
    """Callback data schema for deadline reminder actions."""

    action: str
    task_id: int
    user_id: int
    minutes: int = 15


def get_deadline_keyboard(
    task_id: int,
    user_id: int,
    snooze_minutes: int = 15,
) -> InlineKeyboardMarkup:
    """Generate inline keyboard for deadline reminder notification.

    Buttons:
    - Row 1:
      - [✅ Виконано] (action="done", task_id=task_id, user_id=user_id, minutes=snooze_minutes)
      - [⏰ +15 хв] (action="snooze", task_id=task_id, user_id=user_id, minutes=snooze_minutes)
    - Row 2:
      - [🔔 Нагадати через 15 хв] (action="remind", task_id=task_id, user_id=user_id, minutes=snooze_minutes)
    Arranged with max 2 buttons per row per design system.
    """
    done_btn = InlineKeyboardButton(
        text="✅ Виконано",
        callback_data=DeadlineCallback(
            action="done",
            task_id=task_id,
            user_id=user_id,
            minutes=snooze_minutes,
        ).pack(),
    )
    snooze_btn = InlineKeyboardButton(
        text=f"⏰ +{snooze_minutes} хв",
        callback_data=DeadlineCallback(
            action="snooze",
            task_id=task_id,
            user_id=user_id,
            minutes=snooze_minutes,
        ).pack(),
    )
    remind_btn = InlineKeyboardButton(
        text=f"🔔 Нагадати через {snooze_minutes} хв",
        callback_data=DeadlineCallback(
            action="remind",
            task_id=task_id,
            user_id=user_id,
            minutes=snooze_minutes,
        ).pack(),
    )
    return InlineKeyboardMarkup(inline_keyboard=[[done_btn, snooze_btn], [remind_btn]])
