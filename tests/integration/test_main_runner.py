"""Automated integration tests for unified application runner (main.py).

Verifies component factory wiring, concurrent execution of server and bot polling,
graceful shutdown lifecycle, and configuration validation without real network calls.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from main import (
    ApplicationComponents,
    main,
    run_application,
    setup_application,
    shutdown_application,
)
from src.core.config import Settings
from src.core.database import create_db_engine


@pytest.fixture
def test_engine():
    """Isolated in-memory SQLite database engine for runner tests."""
    eng = create_db_engine("sqlite+aiosqlite:///:memory:")
    yield eng


@pytest.fixture
def valid_settings():
    """Valid mock Settings configuration."""
    return Settings(
        BOT_TOKEN="123456789:ABCdefGHIjklMNOpqrsTUVwxyz",
        GEMINI_API_KEY="mock-gemini-key",
        DATABASE_URL="sqlite+aiosqlite:///:memory:",
        WEBAPP_URL="https://example.com/app",
        HOST="127.0.0.1",
        PORT=8000,
        DEBUG=True,
    )


@pytest.mark.asyncio
async def test_setup_application_wiring(test_engine, valid_settings):
    """Verifies REQ-NFR-03 & REQ-NFR-01: setup_application initializes and wires all stack components."""
    with patch("main.create_bot") as mock_create_bot:
        mock_bot = AsyncMock()
        mock_bot.session = AsyncMock()
        mock_create_bot.return_value = mock_bot

        components = await setup_application(
            settings=valid_settings,
            engine=test_engine,
        )

        try:
            assert isinstance(components, ApplicationComponents)
            assert components.settings == valid_settings
            assert components.engine == test_engine
            assert components.bot == mock_bot
            assert components.dp is not None
            assert components.scheduler is not None
            assert isinstance(components.scheduler, AsyncIOScheduler)
            assert components.scheduler.running is True

            # Verify registered scheduler jobs
            job_ids = [job.id for job in components.scheduler.get_jobs()]
            assert "timezone_checks" in job_ids
            assert "deadline_checks" in job_ids

            # Verify FastAPI application and Uvicorn server configuration
            assert components.app is not None
            assert components.server is not None
            assert components.server.config.host == valid_settings.HOST
            assert components.server.config.port == valid_settings.PORT
        finally:
            await shutdown_application(components)


@pytest.mark.asyncio
async def test_setup_application_missing_bot_token(test_engine):
    """Verifies REQ-NFR-03: setup_application raises ValueError when BOT_TOKEN is empty or missing."""
    empty_token_settings = Settings(
        BOT_TOKEN="",
        DATABASE_URL="sqlite+aiosqlite:///:memory:",
    )

    with pytest.raises(ValueError, match="BOT_TOKEN is not configured"):
        await setup_application(settings=empty_token_settings, engine=test_engine)


@pytest.mark.asyncio
async def test_setup_application_webapp_url_fallback(test_engine, caplog):
    """Verifies REQ-NFR-03: setup_application logs notice and falls back when WEBAPP_URL is omitted."""
    no_webapp_settings = Settings(
        BOT_TOKEN="123456789:ABCdefGHIjklMNOpqrsTUVwxyz",
        DATABASE_URL="sqlite+aiosqlite:///:memory:",
        WEBAPP_URL=None,
        HOST="127.0.0.1",
        PORT=8000,
    )

    with patch("main.create_bot") as mock_create_bot:
        mock_bot = AsyncMock()
        mock_bot.session = AsyncMock()
        mock_create_bot.return_value = mock_bot

        with caplog.at_level("INFO"):
            components = await setup_application(
                settings=no_webapp_settings,
                engine=test_engine,
            )

        try:
            assert "WEBAPP_URL is not set" in caplog.text
            assert "http://127.0.0.1:8000" in caplog.text
            assert components.dp.workflow_data.get("webapp_url") is None
        finally:
            await shutdown_application(components)


@pytest.mark.asyncio
async def test_run_application_concurrent_execution(valid_settings, test_engine):
    """Verifies REQ-NFR-03: run_application runs server and bot polling concurrently without blocking."""
    mock_server = MagicMock()
    mock_server.serve = AsyncMock()

    mock_dp = MagicMock()
    mock_dp.start_polling = AsyncMock()
    mock_dp.stop_polling = AsyncMock()

    mock_bot = AsyncMock()
    mock_bot.session = AsyncMock()

    mock_scheduler = MagicMock()
    mock_scheduler.running = True

    components = ApplicationComponents(
        settings=valid_settings,
        engine=test_engine,
        sessionmaker=AsyncMock(),
        bot=mock_bot,
        dp=mock_dp,
        scheduler=mock_scheduler,
        app=MagicMock(),
        server=mock_server,
    )

    async def fake_serve():
        await asyncio.sleep(0.01)

    async def fake_poll(*args, **kwargs):
        await asyncio.sleep(0.01)

    mock_server.serve.side_effect = fake_serve
    mock_dp.start_polling.side_effect = fake_poll

    await run_application(components)

    mock_server.serve.assert_awaited_once()
    mock_dp.start_polling.assert_awaited_once_with(mock_bot, handle_signals=False)


@pytest.mark.asyncio
async def test_graceful_shutdown_lifecycle():
    """Verifies REQ-NFR-03: shutdown_application cleans up scheduler, polling, session, server, and engine."""
    mock_scheduler = MagicMock()
    mock_scheduler.running = True

    mock_dp = AsyncMock()
    mock_bot = AsyncMock()
    mock_bot.session = AsyncMock()

    mock_server = MagicMock()
    mock_server.should_exit = False

    mock_engine = AsyncMock()

    components = ApplicationComponents(
        settings=MagicMock(),
        engine=mock_engine,
        sessionmaker=AsyncMock(),
        bot=mock_bot,
        dp=mock_dp,
        scheduler=mock_scheduler,
        app=MagicMock(),
        server=mock_server,
    )

    await shutdown_application(components)

    # 1. Scheduler stopped cleanly with wait=False
    mock_scheduler.shutdown.assert_called_once_with(wait=False)

    # 2. Bot polling stopped
    mock_dp.stop_polling.assert_awaited_once()

    # 3. Bot HTTP session closed
    mock_bot.session.close.assert_awaited_once()

    # 4. Server exit flag signaled
    assert mock_server.should_exit is True

    # 5. Database engine disposed cleanly
    mock_engine.dispose.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_application_handles_cancellation(valid_settings, test_engine):
    """Verifies REQ-NFR-03: run_application safely handles task cancellation and runs shutdown."""
    mock_server = MagicMock()
    # Hang server until cancelled
    mock_server.serve = AsyncMock(side_effect=asyncio.CancelledError)

    mock_dp = AsyncMock()
    mock_dp.start_polling = AsyncMock(side_effect=asyncio.CancelledError)
    mock_dp.stop_polling = AsyncMock()

    mock_bot = AsyncMock()
    mock_bot.session = AsyncMock()

    mock_scheduler = MagicMock()
    mock_scheduler.running = True

    components = ApplicationComponents(
        settings=valid_settings,
        engine=test_engine,
        sessionmaker=AsyncMock(),
        bot=mock_bot,
        dp=mock_dp,
        scheduler=mock_scheduler,
        app=MagicMock(),
        server=mock_server,
    )

    # Should catch CancelledError and execute shutdown cleanly without raising
    await run_application(components)

    mock_scheduler.shutdown.assert_called_once_with(wait=False)
    assert mock_server.should_exit is True


@pytest.mark.asyncio
async def test_main_startup_failure_exit_code():
    """Verifies REQ-NFR-01: main returns exit code 1 when setup_application fails."""
    with patch("main.setup_application", side_effect=RuntimeError("Database failure")):
        exit_code = await main()
        assert exit_code == 1


@pytest.mark.asyncio
async def test_main_success_exit_code():
    """Verifies REQ-NFR-03: main returns exit code 0 on normal execution."""
    mock_components = MagicMock()
    with patch("main.setup_application", return_value=mock_components):
        with patch("main.run_application", return_value=None):
            exit_code = await main()
            assert exit_code == 0
