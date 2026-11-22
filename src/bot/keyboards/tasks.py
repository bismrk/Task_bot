"""Task confirmation and tomorrow planning keyboards and callback data."""

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo


class TaskConfirmCallback(CallbackData, prefix="task_confirm"):
    """Callback data schema for task confirmation actions."""

    action: str
    user_id: int


class PlanTomorrowCallback(CallbackData, prefix="plan_tomorrow"):
    """Callback data schema for tomorrow task planning actions."""

    action: str
    user_id: int


def get_task_confirmation_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Generate inline keyboard for task confirmation with max 2 buttons per row.

    Buttons:
    - Row 1:
      - [✅ Зберегти] (action="save", user_id=user_id)
      - [✏️ Виправити] (action="edit", user_id=user_id)
    - Row 2:
      - [🗑️ Видалити] (action="delete", user_id=user_id)
    """
    save_button = InlineKeyboardButton(
        text="✅ Зберегти",
        callback_data=TaskConfirmCallback(action="save", user_id=user_id).pack(),
    )
    edit_button = InlineKeyboardButton(
        text="✏️ Виправити",
        callback_data=TaskConfirmCallback(action="edit", user_id=user_id).pack(),
    )
    delete_button = InlineKeyboardButton(
        text="🗑️ Видалити",
        callback_data=TaskConfirmCallback(action="delete", user_id=user_id).pack(),
    )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [save_button, edit_button],
            [delete_button],
        ]
    )


def get_evening_summary_keyboard(
    user_id: int,
    webapp_url: str | None = None,
) -> InlineKeyboardMarkup:
    """Generate inline keyboard for the 22:00 evening analytics summary (max 2 buttons/row).

    Buttons (Row 1):
    - [📝 План на завтра] (PlanTomorrowCallback(action="start", user_id=user_id))
    - [🚀 Відкрити план] (WebAppInfo when webapp_url is non-empty, else callback_data="open_plan")
    """
    plan_button = InlineKeyboardButton(
        text="📝 План на завтра",
        callback_data=PlanTomorrowCallback(action="start", user_id=user_id).pack(),
    )
    if webapp_url and webapp_url.strip():
        open_button = InlineKeyboardButton(
            text="🚀 Відкрити план",
            web_app=WebAppInfo(url=webapp_url.strip()),
        )
    else:
        open_button = InlineKeyboardButton(
            text="🚀 Відкрити план",
            callback_data="open_plan",
        )
    return InlineKeyboardMarkup(inline_keyboard=[[plan_button, open_button]])


def get_plan_tomorrow_cancel_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Generate inline keyboard with [❌ Скасувати] button for tomorrow planning mode."""
    cancel_button = InlineKeyboardButton(
        text="❌ Скасувати",
        callback_data=PlanTomorrowCallback(action="cancel", user_id=user_id).pack(),
    )
    return InlineKeyboardMarkup(inline_keyboard=[[cancel_button]])
