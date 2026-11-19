"""Start command keyboards."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo


def get_start_keyboard(webapp_url: str | None = None) -> InlineKeyboardMarkup:
    """Generate inline keyboard for the /start command.

    If webapp_url is provided and non-empty, creates a WebApp button.
    Otherwise, creates a fallback button with callback_data="open_plan".
    Complies with design system: maximum 2 buttons per row.
    """
    if webapp_url and webapp_url.strip():
        button = InlineKeyboardButton(
            text="🚀 Відкрити план",
            web_app=WebAppInfo(url=webapp_url.strip()),
        )
    else:
        button = InlineKeyboardButton(
            text="🚀 Відкрити план",
            callback_data="open_plan",
        )
    return InlineKeyboardMarkup(inline_keyboard=[[button]])
