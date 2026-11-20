"""Telegram bot handlers package."""

from src.bot.handlers.callbacks import callbacks_router, router as _callbacks_router
from src.bot.handlers.start import router as start_router
from src.bot.handlers.voice_text import router as voice_text_router, voice_text_router as _vtr

__all__ = [
    "callbacks_router",
    "start_router",
    "voice_text_router",
]
