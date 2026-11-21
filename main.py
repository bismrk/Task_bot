"""Unified application runner for Telegram Task Tracker Bot & Mini App.

Concurrently runs the FastAPI REST API/static asset server, the aiogram Telegram
bot polling service, and the APScheduler background service within a single asyncio event loop.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
import signal
import sys
from typing import Final

import uvicorn
from aiogram import Bot, Dispatcher
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from src.api.app import DEFAULT_FRONTEND_DIST, create_app
from src.bot.dispatcher import create_bot, create_dispatcher
from src.core.config import Settings, get_settings
from src.core.database import async_session_maker, engine as default_engine, init_db
from src.scheduler.manager import (
    create_scheduler,
    setup_scheduler,
    start_scheduler,
    stop_scheduler,
)

logger = logging.getLogger("tasks_bot.main")


@dataclass
class ApplicationComponents:
    """Encapsulates all initialized services and application components."""

    settings: Settings
    engine: AsyncEngine
    sessionmaker: async_sessionmaker[AsyncSession]
    bot: Bot
    dp: Dispatcher
    scheduler: AsyncIOScheduler
    app: FastAPI
    server: uvicorn.Server


async def setup_application(
    settings: Settings | None = None,
    engine: AsyncEngine | None = None,
    sessionmaker: async_sessionmaker[AsyncSession] | None = None,
) -> ApplicationComponents:
    """Initialize and configure all application components and services (REQ-NFR-01, REQ-NFR-03).

    1. Validates and loads application settings.
    2. Initializes SQLite database tables asynchronously.
    3. Creates aiogram Bot instance.
    4. Creates aiogram Dispatcher with database session middleware and routers.
    5. Configures and starts APScheduler for timezone and deadline checks (REQ-SCH-01, REQ-SCH-02, REQ-SCH-03).
    6. Creates FastAPI application and mounts static Mini App assets (REQ-API-01, REQ-API-02).
    7. Configures uvicorn Server.
    """
    resolved_settings = settings if settings is not None else get_settings()

    if not resolved_settings.BOT_TOKEN or not resolved_settings.BOT_TOKEN.strip():
        logger.error("BOT_TOKEN is not configured in settings or environment.")
        raise ValueError("BOT_TOKEN is not configured")

    if not resolved_settings.WEBAPP_URL:
        fallback_url = f"http://{resolved_settings.HOST}:{resolved_settings.PORT}"
        logger.info(
            "WEBAPP_URL is not set; falling back to local Mini App serving at %s",
            fallback_url,
        )

    resolved_engine = engine if engine is not None else default_engine
    resolved_sessionmaker = (
        sessionmaker if sessionmaker is not None else async_session_maker
    )

    # 1. Asynchronously initialize database tables
    try:
        await init_db(resolved_engine)
        logger.info("Database initialized successfully.")
    except Exception as exc:
        logger.error("Failed to initialize database tables: %s", exc)
        raise

    # 2. Initialize Telegram Bot
    bot = create_bot(token=resolved_settings.BOT_TOKEN)

    # 3. Initialize Telegram Dispatcher
    dp = create_dispatcher(
        sessionmaker=resolved_sessionmaker,
        webapp_url=resolved_settings.WEBAPP_URL,
    )

    # 4. Initialize and start background scheduler
    scheduler = create_scheduler()
    setup_scheduler(
        scheduler=scheduler,
        bot=bot,
        sessionmaker=resolved_sessionmaker,
        webapp_url=resolved_settings.WEBAPP_URL,
    )
    start_scheduler(scheduler)

    # 5. Initialize FastAPI application
    app = create_app(
        settings=resolved_settings,
        sessionmaker=resolved_sessionmaker,
        frontend_dist=DEFAULT_FRONTEND_DIST,
    )

    # 6. Configure uvicorn Server
    server_config = uvicorn.Config(
        app=app,
        host=resolved_settings.HOST,
        port=resolved_settings.PORT,
        log_level="info" if not resolved_settings.DEBUG else "debug",
    )
    server = uvicorn.Server(config=server_config)

    return ApplicationComponents(
        settings=resolved_settings,
        engine=resolved_engine,
        sessionmaker=resolved_sessionmaker,
        bot=bot,
        dp=dp,
        scheduler=scheduler,
        app=app,
        server=server,
    )


# Alias per specification
init_app_components = setup_application


async def shutdown_application(
    components: ApplicationComponents | None = None,
    *,
    scheduler: AsyncIOScheduler | None = None,
    dp: Dispatcher | None = None,
    bot: Bot | None = None,
    server: uvicorn.Server | None = None,
    engine: AsyncEngine | None = None,
) -> None:
    """Gracefully stop and clean up application services (REQ-NFR-03).

    - Stops the background scheduler cleanly ensuring no orphaned background jobs continue running.
    - Stops bot polling and closes the bot HTTP session.
    - Signals Uvicorn server to exit.
    - Disposes the SQLAlchemy async database engine.
    """
    target_scheduler = scheduler or (components.scheduler if components else None)
    target_dp = dp or (components.dp if components else None)
    target_bot = bot or (components.bot if components else None)
    target_server = server or (components.server if components else None)
    target_engine = engine or (components.engine if components else None)

    logger.info("Executing graceful shutdown of application components...")

    # 1. Stop background scheduler cleanly
    if target_scheduler is not None:
        try:
            stop_scheduler(target_scheduler, wait=False)
            logger.info("Background scheduler stopped cleanly.")
        except Exception as exc:
            logger.warning("Error stopping background scheduler: %s", exc)

    # 2. Stop bot polling
    if target_dp is not None:
        try:
            await target_dp.stop_polling()
            logger.info("Bot polling stopped cleanly.")
        except RuntimeError as exc:
            if "Polling is not started" not in str(exc):
                logger.warning("Runtime error stopping bot polling: %s", exc)
        except Exception as exc:
            logger.warning("Error stopping bot polling: %s", exc)

    # 3. Close bot session
    if target_bot is not None and getattr(target_bot, "session", None) is not None:
        try:
            await target_bot.session.close()
            logger.info("Bot HTTP session closed.")
        except Exception as exc:
            logger.warning("Error closing bot session: %s", exc)

    # 4. Signal Uvicorn server to exit
    if target_server is not None:
        target_server.should_exit = True
        logger.info("Uvicorn server exit signaled.")

    # 5. Dispose database engine
    if target_engine is not None:
        try:
            await target_engine.dispose()
            logger.info("Database engine disposed.")
        except Exception as exc:
            logger.warning("Error disposing database engine: %s", exc)


async def run_application(components: ApplicationComponents) -> None:
    """Run FastAPI server and Telegram bot polling concurrently with graceful shutdown."""
    loop = asyncio.get_running_loop()

    def _on_signal() -> None:
        logger.info("OS shutdown signal received. Triggering server and bot exit...")
        components.server.should_exit = True
        try:
            asyncio.create_task(components.dp.stop_polling())
        except Exception:
            pass

    # Cross-platform signal handling: register on non-Windows platforms
    if sys.platform != "win32":
        for sig in (signal.SIGINT, signal.SIGTERM):
            if hasattr(signal, sig.name):
                try:
                    loop.add_signal_handler(sig, _on_signal)
                except (NotImplementedError, RuntimeError):
                    pass

    async def _run_server() -> None:
        try:
            await components.server.serve()
        finally:
            try:
                await components.dp.stop_polling()
            except Exception:
                pass

    async def _run_bot() -> None:
        try:
            await components.dp.start_polling(components.bot, handle_signals=False)
        finally:
            components.server.should_exit = True

    try:
        await asyncio.gather(_run_server(), _run_bot())
    except (asyncio.CancelledError, KeyboardInterrupt):
        logger.info("Application execution cancelled or interrupted.")
    finally:
        await shutdown_application(components)


async def main() -> int:
    """Main async entrypoint returning process exit code."""
    try:
        components = await setup_application()
    except Exception as exc:
        logger.error("Failed to initialize application components: %s", exc)
        return 1

    try:
        await run_application(components)
        return 0
    except (asyncio.CancelledError, KeyboardInterrupt):
        logger.info("Application shutdown requested via interrupt/cancel.")
        return 0
    except Exception as exc:
        logger.exception("Unexpected error during application execution: %s", exc)
        return 1


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except (KeyboardInterrupt, SystemExit):
        sys.exit(0)
