"""Task confirmation keyboards and callback data."""

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


class TaskConfirmCallback(CallbackData, prefix="task_confirm"):
    """Callback data schema for task confirmation actions."""

    action: str
    user_id: int


def get_task_confirmation_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Generate inline keyboard for task confirmation with max 2 buttons per row.

    Buttons:
    - [✅ Зберегти] (action="save", user_id=user_id)
    - [✏️ Виправити] (action="edit", user_id=user_id)
    """
    save_button = InlineKeyboardButton(
        text="✅ Зберегти",
        callback_data=TaskConfirmCallback(action="save", user_id=user_id).pack(),
    )
    edit_button = InlineKeyboardButton(
        text="✏️ Виправити",
        callback_data=TaskConfirmCallback(action="edit", user_id=user_id).pack(),
    )
    return InlineKeyboardMarkup(inline_keyboard=[[save_button, edit_button]])
