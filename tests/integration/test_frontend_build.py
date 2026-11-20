"""Integration tests for frontend build assets, static file serving, and SPA routing fallback."""

from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Final

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.api.app import DEFAULT_FRONTEND_DIST, create_app
from src.core.config import Settings
from src.core.database import configure_sqlite_pragmas
from src.models.base import Base
from tests.integration.test_api_auth import create_test_init_data

MOCK_INDEX_HTML: Final[str] = (
    "<!doctype html><html><head><title>Telegram Task Tracker</title></head>"
    "<body><div id='root'>Mock TMA Frontend</div></body></html>"
)
MOCK_CSS_CONTENT: Final[str] = ":root { --tg-theme-bg-color: #ffffff; }"


@pytest.fixture
async def test_env() -> AsyncGenerator[
    tuple[async_sessionmaker[AsyncSession], Settings], None
]:
    """Provide isolated in-memory SQLite database and test settings."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    configure_sqlite_pragmas(engine)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        bind=engine,
        expire_on_commit=False,
        class_=AsyncSession,
    )
    test_settings = Settings(
        BOT_TOKEN="123456789:TestBotTokenSecretKey123456789",
        DATABASE_URL="sqlite+aiosqlite:///:memory:",
    )

    yield session_factory, test_settings

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


def test_create_app_when_frontend_dist_missing(tmp_path: Path) -> None:
    """Verifies REQ-TMA-01: create_app() initializes cleanly when frontend/dist is missing."""
    nonexistent_dir = tmp_path / "does_not_exist"
    app = create_app(frontend_dist=nonexistent_dir)

    with TestClient(app) as client:
        res = client.get("/health")
        assert res.status_code == 200
        assert res.json() == {"status": "ok"}

        # Nonexistent route returns standard 404 when no static fallback is mounted
        res_404 = client.get("/nonexistent-page")
        assert res_404.status_code == 404


def test_static_file_mounting_and_spa_fallback_fixture(
    test_env: tuple[async_sessionmaker[AsyncSession], Settings],
    tmp_path: Path,
) -> None:
    """Verifies REQ-TMA-01: Static files and SPA fallback serve index.html for client routes."""
    session_factory, settings = test_env
    mock_dist = tmp_path / "dist"
    mock_dist.mkdir()
    (mock_dist / "index.html").write_text(MOCK_INDEX_HTML, encoding="utf-8")

    assets_dir = mock_dist / "assets"
    assets_dir.mkdir()
    (assets_dir / "index.css").write_text(MOCK_CSS_CONTENT, encoding="utf-8")

    app = create_app(
        settings=settings,
        sessionmaker=session_factory,
        frontend_dist=mock_dist,
    )

    with TestClient(app) as client:
        # Root path serves index.html
        res_root = client.get("/")
        assert res_root.status_code == 200
        assert "text/html" in res_root.headers.get("content-type", "")
        assert "Mock TMA Frontend" in res_root.text

        # Direct static asset request
        res_asset = client.get("/assets/index.css")
        assert res_asset.status_code == 200
        assert "--tg-theme-bg-color" in res_asset.text

        # SPA client navigation routes fallback to index.html
        res_today = client.get("/today")
        assert res_today.status_code == 200
        assert "text/html" in res_today.headers.get("content-type", "")
        assert "Mock TMA Frontend" in res_today.text

        res_calendar = client.get("/calendar")
        assert res_calendar.status_code == 200
        assert "Mock TMA Frontend" in res_calendar.text

        # Unknown /api/* route does NOT fallback to index.html (returns 404)
        res_api_unknown = client.get("/api/unknown_endpoint")
        assert res_api_unknown.status_code == 404
        assert "Mock TMA Frontend" not in res_api_unknown.text


def test_health_and_api_routes_take_precedence_over_static_mount(
    test_env: tuple[async_sessionmaker[AsyncSession], Settings],
    tmp_path: Path,
) -> None:
    """Verifies REQ-TMA-01, REQ-API-01: API routes (/health, /api/me, /docs) are not intercepted by static mount."""
    session_factory, settings = test_env
    mock_dist = tmp_path / "dist"
    mock_dist.mkdir()
    (mock_dist / "index.html").write_text(MOCK_INDEX_HTML, encoding="utf-8")

    app = create_app(
        settings=settings,
        sessionmaker=session_factory,
        frontend_dist=mock_dist,
    )

    with TestClient(app) as client:
        # System healthcheck remains 200
        res_health = client.get("/health")
        assert res_health.status_code == 200
        assert res_health.json() == {"status": "ok"}

        # Swagger docs remain accessible
        res_docs = client.get("/docs")
        assert res_docs.status_code == 200

        res_openapi = client.get("/openapi.json")
        assert res_openapi.status_code == 200

        # Unauthenticated /api/me returns 401 Unauthorized (not intercepted by static fallback)
        res_me_unauth = client.get("/api/me")
        assert res_me_unauth.status_code == 401
        assert res_me_unauth.json()["detail"] == "Missing or invalid authentication credentials"

        # Authenticated /api/me returns 200 with UserRead payload
        telegram_id = 987654321
        user_data = {"id": telegram_id, "first_name": "FrontendTester"}
        init_data = create_test_init_data(user_data, bot_token=settings.BOT_TOKEN)

        res_me_auth = client.get(
            "/api/me",
            headers={"Authorization": f"tma {init_data}"},
        )
        assert res_me_auth.status_code == 200
        data = res_me_auth.json()
        assert data["telegram_id"] == telegram_id
        assert data["timezone"] == "Europe/Kyiv"
        assert "created_at" in data


def test_production_frontend_dist_build_exists_and_serves_valid_html(
    test_env: tuple[async_sessionmaker[AsyncSession], Settings],
) -> None:
    """Verifies REQ-TMA-01: Built production frontend dist serves valid HTML and assets."""
    if not DEFAULT_FRONTEND_DIST.is_dir():
        pytest.skip("Production frontend build directory does not exist on disk")

    index_html = DEFAULT_FRONTEND_DIST / "index.html"
    assert index_html.is_file(), f"Missing index.html in {DEFAULT_FRONTEND_DIST}"

    index_content = index_html.read_text(encoding="utf-8")
    assert "Telegram Task Tracker" in index_content
    assert "telegram-web-app.js" in index_content

    session_factory, settings = test_env
    app = create_app(settings=settings, sessionmaker=session_factory)

    with TestClient(app) as client:
        # GET / serves production index.html
        res_root = client.get("/")
        assert res_root.status_code == 200
        assert "Telegram Task Tracker" in res_root.text

        # GET /today serves production index.html via SPA fallback
        res_today = client.get("/today")
        assert res_today.status_code == 200
        assert "Telegram Task Tracker" in res_today.text

        # GET /health remains functional
        res_health = client.get("/health")
        assert res_health.status_code == 200
        assert res_health.json() == {"status": "ok"}
