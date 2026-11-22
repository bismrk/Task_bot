"""Integration tests for user settings REST API endpoints and tenant isolation."""

from collections.abc import AsyncGenerator
import json
import time
from typing import Any
import urllib.parse
import hashlib
import hmac

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.api.app import create_app
from src.core.config import Settings
from src.core.database import configure_sqlite_pragmas
from src.models.base import Base
from src.models.user import User
from src.services.user_service import get_or_create_user


def create_test_init_data(
    user_data: dict[str, Any] | None = None,
    bot_token: str = "test_bot_token_secret",
    auth_date: int | None = None,
    include_auth_date: bool = True,
    **extra_params: Any,
) -> str:
    """Generate cryptographically valid signed Telegram initData query strings."""
    params: dict[str, str] = {}

    if include_auth_date:
        if auth_date is not None:
            params["auth_date"] = str(auth_date)
        else:
            params["auth_date"] = str(int(time.time()))

    if user_data is not None:
        params["user"] = json.dumps(user_data, separators=(",", ":"))

    for k, v in extra_params.items():
        if isinstance(v, (dict, list)):
            params[k] = json.dumps(v, separators=(",", ":"))
        else:
            params[k] = str(v)

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))
    secret_key = hmac.new(
        key=b"WebAppData",
        msg=bot_token.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()
    computed_hash = hmac.new(
        key=secret_key,
        msg=data_check_string.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()

    params["hash"] = computed_hash
    return urllib.parse.urlencode(params)


@pytest.fixture
async def api_context() -> AsyncGenerator[
    tuple[TestClient, async_sessionmaker[AsyncSession], Settings], None
]:
    """Provide isolated in-memory SQLite database, configured FastAPI TestClient, and Settings."""
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
        BOT_TOKEN="123456789:ABCDefGhIJklMnOpQrStUvWxYz",
        DATABASE_URL="sqlite+aiosqlite:///:memory:",
    )
    app = create_app(settings=test_settings, sessionmaker=session_factory)

    with TestClient(app) as client:
        yield client, session_factory, test_settings

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


def get_auth_headers(
    user_id: int,
    bot_token: str,
    first_name: str = "TestUser",
) -> dict[str, str]:
    """Helper to generate Authorization header for a given telegram_id."""
    init_data = create_test_init_data(
        user_data={"id": user_id, "first_name": first_name},
        bot_token=bot_token,
    )
    return {"Authorization": f"tma {init_data}"}


@pytest.mark.asyncio
async def test_update_timezone_success(api_context) -> None:
    """Verifies REQ-USR-02: PATCH /api/settings/timezone successfully updates user timezone and returns UserRead."""
    client, session_factory, settings = api_context
    telegram_id = 10001
    headers = get_auth_headers(telegram_id, settings.BOT_TOKEN)

    async with session_factory() as session:
        await get_or_create_user(session, telegram_id=telegram_id, timezone="Europe/Kyiv")

    response = client.patch(
        "/api/settings/timezone",
        headers=headers,
        json={"timezone": "Europe/Warsaw"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["telegram_id"] == telegram_id
    assert data["timezone"] == "Europe/Warsaw"
    assert "created_at" in data

    # Verify persisted in database
    async with session_factory() as session:
        user = (
            await session.execute(select(User).where(User.telegram_id == telegram_id))
        ).scalar_one()
        assert user.timezone == "Europe/Warsaw"


@pytest.mark.asyncio
async def test_update_timezone_me_alias_route(api_context) -> None:
    """Verifies REQ-USR-02: Alias PATCH /api/me/timezone updates user timezone and returns UserRead."""
    client, session_factory, settings = api_context
    telegram_id = 10002
    headers = get_auth_headers(telegram_id, settings.BOT_TOKEN)

    async with session_factory() as session:
        await get_or_create_user(session, telegram_id=telegram_id, timezone="Europe/Kyiv")

    response = client.patch(
        "/api/me/timezone",
        headers=headers,
        json={"timezone": "America/New_York"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["telegram_id"] == telegram_id
    assert data["timezone"] == "America/New_York"

    # Verify persisted in database
    async with session_factory() as session:
        user = (
            await session.execute(select(User).where(User.telegram_id == telegram_id))
        ).scalar_one()
        assert user.timezone == "America/New_York"


@pytest.mark.asyncio
async def test_update_timezone_invalid_iana_rejected(api_context) -> None:
    """Verifies REQ-USR-02: Invalid IANA timezone is rejected with 422 leaving DB unchanged."""
    client, session_factory, settings = api_context
    telegram_id = 10003
    headers = get_auth_headers(telegram_id, settings.BOT_TOKEN)

    async with session_factory() as session:
        await get_or_create_user(session, telegram_id=telegram_id, timezone="Europe/Kyiv")

    # Invalid timezone identifier
    response = client.patch(
        "/api/settings/timezone",
        headers=headers,
        json={"timezone": "Mars/Olympus"},
    )
    assert response.status_code == 422

    # Empty timezone
    response_empty = client.patch(
        "/api/settings/timezone",
        headers=headers,
        json={"timezone": ""},
    )
    assert response_empty.status_code == 422

    # Verify DB record remained unchanged
    async with session_factory() as session:
        user = (
            await session.execute(select(User).where(User.telegram_id == telegram_id))
        ).scalar_one()
        assert user.timezone == "Europe/Kyiv"


@pytest.mark.asyncio
async def test_update_timezone_unauthenticated_rejected(api_context) -> None:
    """Verifies REQ-API-01: Requests without Authorization or invalid HMAC return 401 Unauthorized."""
    client, session_factory, settings = api_context

    # No authorization header
    res_no_auth = client.patch(
        "/api/settings/timezone",
        json={"timezone": "Europe/London"},
    )
    assert res_no_auth.status_code == 401

    # Forged HMAC / wrong bot token
    fake_init_data = create_test_init_data(
        user_data={"id": 99999},
        bot_token="wrong_bot_token",
    )
    res_forged = client.patch(
        "/api/settings/timezone",
        headers={"Authorization": f"tma {fake_init_data}"},
        json={"timezone": "Europe/London"},
    )
    assert res_forged.status_code == 401


@pytest.mark.asyncio
async def test_update_timezone_tenant_isolation(api_context) -> None:
    """Verifies REQ-NFR-02: User A cannot modify User B's timezone settings."""
    client, session_factory, settings = api_context
    user_a_id = 20001
    user_b_id = 20002

    async with session_factory() as session:
        await get_or_create_user(session, telegram_id=user_a_id, timezone="Europe/Kyiv")
        await get_or_create_user(session, telegram_id=user_b_id, timezone="Asia/Tokyo")

    headers_a = get_auth_headers(user_a_id, settings.BOT_TOKEN)

    # User A updates their timezone to America/Chicago
    response = client.patch(
        "/api/settings/timezone",
        headers=headers_a,
        json={"timezone": "America/Chicago"},
    )
    assert response.status_code == 200
    assert response.json()["timezone"] == "America/Chicago"

    # Verify User B's timezone remains untouched
    async with session_factory() as session:
        user_b = (
            await session.execute(select(User).where(User.telegram_id == user_b_id))
        ).scalar_one()
        assert user_b.timezone == "Asia/Tokyo"


# ============================================================================
# Periodic Reminder Settings API Tests (Issue #24)
# ============================================================================


@pytest.mark.asyncio
async def test_user_endpoints_return_reminder_interval_hours(api_context) -> None:
    """Verifies Issue #24: GET /api/me, PATCH /api/settings/timezone, PATCH /api/me/timezone include reminder_interval_hours."""
    client, session_factory, settings = api_context
    telegram_id = 30001
    headers = get_auth_headers(telegram_id, settings.BOT_TOKEN)

    async with session_factory() as session:
        await get_or_create_user(session, telegram_id=telegram_id, timezone="Europe/Kyiv")

    res_me = client.get("/api/me", headers=headers)
    assert res_me.status_code == 200
    assert res_me.json()["reminder_interval_hours"] == 4

    res_tz = client.patch(
        "/api/settings/timezone",
        headers=headers,
        json={"timezone": "Europe/Warsaw"},
    )
    assert res_tz.status_code == 200
    assert res_tz.json()["reminder_interval_hours"] == 4

    res_me_tz = client.patch(
        "/api/me/timezone",
        headers=headers,
        json={"timezone": "UTC"},
    )
    assert res_me_tz.status_code == 200
    assert res_me_tz.json()["reminder_interval_hours"] == 4


@pytest.mark.asyncio
async def test_update_reminders_success_and_disable(api_context) -> None:
    """Verifies Issue #24: PATCH /api/settings/reminders updates interval (1..24) and disables (null)."""
    client, session_factory, settings = api_context
    telegram_id = 30002
    headers = get_auth_headers(telegram_id, settings.BOT_TOKEN)

    async with session_factory() as session:
        await get_or_create_user(session, telegram_id=telegram_id, timezone="Europe/Kyiv")

    # Set to 2 hours
    res_2h = client.patch(
        "/api/settings/reminders",
        headers=headers,
        json={"reminder_interval_hours": 2},
    )
    assert res_2h.status_code == 200
    assert res_2h.json()["reminder_interval_hours"] == 2

    # Set to upper bound 24 hours
    res_24h = client.patch(
        "/api/settings/reminders",
        headers=headers,
        json={"reminder_interval_hours": 24},
    )
    assert res_24h.status_code == 200
    assert res_24h.json()["reminder_interval_hours"] == 24

    # Disable (null)
    res_null = client.patch(
        "/api/settings/reminders",
        headers=headers,
        json={"reminder_interval_hours": None},
    )
    assert res_null.status_code == 200
    assert res_null.json()["reminder_interval_hours"] is None

    async with session_factory() as session:
        user = (
            await session.execute(select(User).where(User.telegram_id == telegram_id))
        ).scalar_one()
        assert user.reminder_interval_hours is None

    # Confirm GET /api/me reflects NULL
    res_me = client.get("/api/me", headers=headers)
    assert res_me.status_code == 200
    assert res_me.json()["reminder_interval_hours"] is None

    # Re-enable to lower bound 1 hour
    res_1h = client.patch(
        "/api/settings/reminders",
        headers=headers,
        json={"reminder_interval_hours": 1},
    )
    assert res_1h.status_code == 200
    assert res_1h.json()["reminder_interval_hours"] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"reminder_interval_hours": 0},
        {"reminder_interval_hours": -1},
        {"reminder_interval_hours": 25},
        {"reminder_interval_hours": True},
        {"reminder_interval_hours": False},
        {"reminder_interval_hours": 2.5},
        {"reminder_interval_hours": 4.0},
        {"reminder_interval_hours": "4"},
        {"reminder_interval_hours": "abc"},
    ],
)
async def test_update_reminders_invalid_payloads_return_422(api_context, payload) -> None:
    """Verifies Issue #24: Invalid reminder interval payloads return HTTP 422 and keep DB unchanged."""
    client, session_factory, settings = api_context
    telegram_id = 30003
    headers = get_auth_headers(telegram_id, settings.BOT_TOKEN)

    async with session_factory() as session:
        await get_or_create_user(session, telegram_id=telegram_id, timezone="Europe/Kyiv")

    res = client.patch("/api/settings/reminders", headers=headers, json=payload)
    assert res.status_code == 422

    async with session_factory() as session:
        user = (
            await session.execute(select(User).where(User.telegram_id == telegram_id))
        ).scalar_one()
        assert user.reminder_interval_hours == 4


@pytest.mark.asyncio
async def test_update_reminders_unauthenticated_rejected(api_context) -> None:
    """Verifies Issue #24: PATCH /api/settings/reminders returns 401 when auth is missing or forged."""
    client, _session_factory, _settings = api_context

    res_no_auth = client.patch(
        "/api/settings/reminders",
        json={"reminder_interval_hours": 2},
    )
    assert res_no_auth.status_code == 401

    fake_init_data = create_test_init_data(
        user_data={"id": 99999},
        bot_token="wrong_bot_token",
    )
    res_forged = client.patch(
        "/api/settings/reminders",
        headers={"Authorization": f"tma {fake_init_data}"},
        json={"reminder_interval_hours": 2},
    )
    assert res_forged.status_code == 401


@pytest.mark.asyncio
async def test_update_reminders_tenant_isolation(api_context) -> None:
    """Verifies Issue #24: User A updating reminder interval cannot alter User B's setting."""
    client, session_factory, settings = api_context
    user_a_id = 30011
    user_b_id = 30012

    async with session_factory() as session:
        await get_or_create_user(session, telegram_id=user_a_id, timezone="Europe/Kyiv")
        await get_or_create_user(session, telegram_id=user_b_id, timezone="Europe/Kyiv")

    headers_a = get_auth_headers(user_a_id, settings.BOT_TOKEN)
    res = client.patch(
        "/api/settings/reminders",
        headers=headers_a,
        json={"reminder_interval_hours": None},
    )
    assert res.status_code == 200
    assert res.json()["reminder_interval_hours"] is None

    async with session_factory() as session:
        user_a = (
            await session.execute(select(User).where(User.telegram_id == user_a_id))
        ).scalar_one()
        user_b = (
            await session.execute(select(User).where(User.telegram_id == user_b_id))
        ).scalar_one()
        assert user_a.reminder_interval_hours is None
        assert user_b.reminder_interval_hours == 4
