"""Telegram bot middlewares package."""

from src.bot.middlewares.db import DbSessionMiddleware

__all__ = ["DbSessionMiddleware"]
