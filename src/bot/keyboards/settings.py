"""Keyboards for bot user settings and timezone selection."""

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

TIMEZONE_PRESETS = [
    ("🇺🇦 Київ", "Europe/Kyiv"),
    ("🇵🇱 Варшава", "Europe/Warsaw"),
    ("🇬🇧 Лондон", "Europe/London"),
    ("🇺🇸 Нью-Йорк", "America/New_York"),
    ("🇯🇵 Токіо", "Asia/Tokyo"),
]


class TimezoneCallback(CallbackData, prefix="tz"):
    """Callback data for quick timezone selection buttons."""

    timezone: str


def get_settings_keyboard(
    current_tz: str,
    webapp_url: str | None = None,
) -> InlineKeyboardMarkup:
    """Generate inline keyboard for /settings command with quick presets and Mini App launcher.

    Arranges quick timezone buttons with a maximum of 2 buttons per row per _docs/design-system.md,
    marking the currently active timezone with a checkmark ('✓').
    Adds a bottom row with a button to launch the Mini App Settings.
    """
    keyboard: list[list[InlineKeyboardButton]] = []
    current_row: list[InlineKeyboardButton] = []

    for label, tz in TIMEZONE_PRESETS:
        btn_text = f"{label} ✓" if tz == current_tz else label
        btn = InlineKeyboardButton(
            text=btn_text,
            callback_data=TimezoneCallback(timezone=tz).pack(),
        )
        current_row.append(btn)
        if len(current_row) == 2:
            keyboard.append(current_row)
            current_row = []

    if current_row:
        keyboard.append(current_row)

    # Mini App Settings launcher button
    if webapp_url and webapp_url.strip():
        app_btn = InlineKeyboardButton(
            text="⚙️ Відкрити в Mini App",
            web_app=WebAppInfo(url=webapp_url.strip()),
        )
    else:
        app_btn = InlineKeyboardButton(
            text="⚙️ Відкрити в Mini App",
            callback_data="open_settings_app",
        )
    keyboard.append([app_btn])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


__all__ = ["TimezoneCallback", "get_settings_keyboard", "TIMEZONE_PRESETS"]
