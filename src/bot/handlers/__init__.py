"""Telegram bot handlers package."""

from src.bot.handlers.callbacks import callbacks_router, router as _callbacks_router
from src.bot.handlers.deadline import deadline_router, router as _deadline_router
from src.bot.handlers.rollover import rollover_router, router as _rollover_router
from src.bot.handlers.start import router as start_router
from src.bot.handlers.voice_text import router as voice_text_router, voice_text_router as _vtr

__all__ = [
    "callbacks_router",
    "deadline_router",
    "rollover_router",
    "start_router",
    "voice_text_router",
]
