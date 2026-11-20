"""Rollover inline keyboards and callback data."""

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


class RolloverCallback(CallbackData, prefix="rollover"):
    """Callback data schema for midnight task rollover actions."""

    action: str
    task_id: int | None = None
    user_id: int


def get_task_rollover_keyboard(task_id: int, user_id: int) -> InlineKeyboardMarkup:
    """Generate inline keyboard for a single overdue task rollover.

    Buttons:
    - [⏩ Перенести на сьогодні] (action="postpone", task_id=task_id, user_id=user_id)
    - [❌ Закрити] (action="close", task_id=task_id, user_id=user_id)
    Arranged with max 2 buttons per row per design system.
    """
    postpone_btn = InlineKeyboardButton(
        text="⏩ Перенести на сьогодні",
        callback_data=RolloverCallback(action="postpone", task_id=task_id, user_id=user_id).pack(),
    )
    close_btn = InlineKeyboardButton(
        text="❌ Закрити",
        callback_data=RolloverCallback(action="close", task_id=task_id, user_id=user_id).pack(),
    )
    return InlineKeyboardMarkup(inline_keyboard=[[postpone_btn, close_btn]])


def get_batch_rollover_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Generate inline keyboard for batch overdue tasks rollover.

    Buttons:
    - [⏩ Перенести всі] (action="postpone_all", task_id=None, user_id=user_id)
    - [❌ Закрити всі] (action="close_all", task_id=None, user_id=user_id)
    Arranged with max 2 buttons per row per design system.
    """
    postpone_all_btn = InlineKeyboardButton(
        text="⏩ Перенести всі",
        callback_data=RolloverCallback(action="postpone_all", task_id=None, user_id=user_id).pack(),
    )
    close_all_btn = InlineKeyboardButton(
        text="❌ Закрити всі",
        callback_data=RolloverCallback(action="close_all", task_id=None, user_id=user_id).pack(),
    )
    return InlineKeyboardMarkup(inline_keyboard=[[postpone_all_btn, close_all_btn]])
