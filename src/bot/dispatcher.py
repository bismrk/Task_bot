"""Telegram bot and dispatcher initialization."""

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.bot.handlers import start_router
from src.bot.middlewares import DbSessionMiddleware
from src.core.config import get_settings


def create_bot(
    token: str | None = None,
    default_parse_mode: ParseMode = ParseMode.HTML,
) -> Bot:
    """Initialize and configure aiogram Bot instance.

    Uses provided token or falls back to Settings.BOT_TOKEN.
    Raises ValueError if no token is available or token is empty.
    """
    bot_token = token if token is not None else get_settings().BOT_TOKEN
    if not bot_token or not bot_token.strip():
        raise ValueError("BOT_TOKEN is not set")

    return Bot(
        token=bot_token.strip(),
        default=DefaultBotProperties(parse_mode=default_parse_mode),
    )


def create_dispatcher(
    sessionmaker: async_sessionmaker[AsyncSession] | None = None,
    webapp_url: str | None = None,
) -> Dispatcher:
    """Initialize and configure aiogram Dispatcher.

    Attaches DbSessionMiddleware to message and callback_query routers,
    passes webapp_url into workflow data, and includes start_router.
    """
    dp = Dispatcher()

    # Pass webapp_url to handlers via workflow_data
    dp.workflow_data["webapp_url"] = webapp_url

    # Register database session middleware
    db_middleware = DbSessionMiddleware(sessionmaker=sessionmaker)
    dp.message.middleware(db_middleware)
    dp.callback_query.middleware(db_middleware)

    # Detach router if previously attached in factory context, then include
    if start_router._parent_router is not None:
        start_router._parent_router = None
    dp.include_router(start_router)

    return dp
