"""Integration tests for FastAPI application and Telegram initData authentication."""

import hashlib
import hmac
import json
import time
import urllib.parse
from collections.abc import AsyncGenerator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.api.app import create_app
from src.core.config import Settings
from src.core.database import configure_sqlite_pragmas
from src.models.base import Base
from src.models.user import User


def create_test_init_data(
    user_data: dict[str, Any] | None = None,
    bot_token: str = "test_bot_token_secret",
    auth_date: int | None = None,
    include_auth_date: bool = True,
    **extra_params: Any,
) -> str:
    """Generate cryptographically valid signed Telegram initData query strings.

    Args:
        user_data: Dictionary representing Telegram user object (e.g. {'id': 12345}).
                   If None, 'user' parameter is omitted.
        bot_token: Telegram bot token secret key used for HMAC-SHA256 signature.
        auth_date: Optional integer Unix timestamp. If None and include_auth_date is True,
                   defaults to current timestamp.
        include_auth_date: Whether to include 'auth_date' parameter in the generated data.
        **extra_params: Arbitrary additional query parameters to sign and include.

    Returns:
        URL-encoded query string containing all parameters and the calculated 'hash'.
    """
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


@pytest.mark.asyncio
async def test_health_check_returns_ok_without_auth(api_context):
    """Verifies public GET /health returns HTTP 200 and {'status': 'ok'} without credentials."""
    client, _, _ = api_context
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_cors_preflight_and_response_headers(api_context):
    """Verifies CORS preflight and response headers include access-control-allow-origin."""
    client, _, _ = api_context
    origin = "https://webapp.telegram.org"

    # Preflight request
    preflight = client.options(
        "/health",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
        },
    )
    assert preflight.status_code == 200
    assert "access-control-allow-origin" in preflight.headers
    assert preflight.headers["access-control-allow-origin"] == origin

    # Normal GET with Origin header
    res = client.get("/health", headers={"Origin": origin})
    assert res.status_code == 200
    assert "access-control-allow-origin" in res.headers
    assert res.headers["access-control-allow-origin"] == origin


@pytest.mark.asyncio
async def test_get_me_valid_init_data_tma_header(api_context):
    """Verifies REQ-API-01: GET /api/me with Authorization: tma <initData> returns 200 and UserRead."""
    client, _, settings = api_context
    telegram_id = 987654321
    user_data = {"id": telegram_id, "first_name": "TestUser", "username": "test_user"}
    init_data = create_test_init_data(user_data, bot_token=settings.BOT_TOKEN)

    response = client.get(
        "/api/me",
        headers={"Authorization": f"tma {init_data}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["telegram_id"] == telegram_id
    assert data["timezone"] == "Europe/Kyiv"
    assert "created_at" in data


@pytest.mark.asyncio
async def test_get_me_valid_init_data_bearer_header(api_context):
    """Verifies REQ-API-01: GET /api/me with Authorization: Bearer <initData> returns 200."""
    client, _, settings = api_context
    telegram_id = 1122334455
    user_data = {"id": telegram_id, "first_name": "BearerUser"}
    init_data = create_test_init_data(user_data, bot_token=settings.BOT_TOKEN)

    response = client.get(
        "/api/me",
        headers={"Authorization": f"Bearer {init_data}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["telegram_id"] == telegram_id


@pytest.mark.asyncio
async def test_get_me_valid_init_data_case_insensitive_header(api_context):
    """Verifies REQ-API-01: Header scheme matches case-insensitively (e.g. TMA, bearer)."""
    client, _, settings = api_context
    telegram_id = 77889900
    user_data = {"id": telegram_id}
    init_data = create_test_init_data(user_data, bot_token=settings.BOT_TOKEN)

    response = client.get(
        "/api/me",
        headers={"Authorization": f"TMA {init_data}"},
    )
    assert response.status_code == 200
    assert response.json()["telegram_id"] == telegram_id


@pytest.mark.asyncio
async def test_get_me_valid_init_data_x_telegram_init_data_header(api_context):
    """Verifies REQ-API-01: GET /api/me with X-Telegram-Init-Data header returns 200."""
    client, _, settings = api_context
    telegram_id = 5544332211
    user_data = {"id": telegram_id, "first_name": "CustomHeaderUser"}
    init_data = create_test_init_data(user_data, bot_token=settings.BOT_TOKEN)

    response = client.get(
        "/api/me",
        headers={"X-Telegram-Init-Data": init_data},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["telegram_id"] == telegram_id


@pytest.mark.asyncio
async def test_get_me_tampered_init_data_returns_unauthorized(api_context):
    """Verifies REQ-API-01: GET /api/me with tampered parameter returns 401 Unauthorized."""
    client, _, settings = api_context
    user_data = {"id": 12345}
    init_data = create_test_init_data(user_data, bot_token=settings.BOT_TOKEN)

    # Tamper with query string parameter while keeping original hash
    tampered_data = init_data.replace("12345", "99999")
    response = client.get(
        "/api/me",
        headers={"Authorization": f"tma {tampered_data}"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid Telegram initData signature"


@pytest.mark.asyncio
async def test_get_me_invalid_bot_token_signature_returns_unauthorized(api_context):
    """Verifies REQ-API-01: GET /api/me with signature signed by wrong bot token returns 401."""
    client, _, _ = api_context
    user_data = {"id": 12345}
    init_data = create_test_init_data(user_data, bot_token="invalid_bot_token_secret")

    response = client.get(
        "/api/me",
        headers={"Authorization": f"tma {init_data}"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid Telegram initData signature"


@pytest.mark.asyncio
async def test_get_me_expired_auth_date_returns_unauthorized(api_context):
    """Verifies REQ-API-01: GET /api/me with expired auth_date (> 86400s) returns 401."""
    client, _, settings = api_context
    expired_auth_date = int(time.time()) - 90000  # older than 86400s
    user_data = {"id": 12345}
    init_data = create_test_init_data(
        user_data,
        bot_token=settings.BOT_TOKEN,
        auth_date=expired_auth_date,
    )

    response = client.get(
        "/api/me",
        headers={"Authorization": f"tma {init_data}"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Telegram initData has expired"


@pytest.mark.asyncio
async def test_get_me_future_auth_date_returns_unauthorized(api_context):
    """Verifies REQ-API-01: GET /api/me with future auth_date (> 60s) returns 401."""
    client, _, settings = api_context
    future_auth_date = int(time.time()) + 120  # more than 60s in the future
    user_data = {"id": 12345}
    init_data = create_test_init_data(
        user_data,
        bot_token=settings.BOT_TOKEN,
        auth_date=future_auth_date,
    )

    response = client.get(
        "/api/me",
        headers={"Authorization": f"tma {init_data}"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Telegram initData auth_date is in the future"


@pytest.mark.asyncio
async def test_get_me_missing_hash_returns_unauthorized(api_context):
    """Verifies REQ-API-01: GET /api/me with missing hash returns 401 Unauthorized."""
    client, _, settings = api_context
    user_data = {"id": 12345}
    init_data = create_test_init_data(user_data, bot_token=settings.BOT_TOKEN)

    # Strip the hash parameter
    pairs = [p for p in init_data.split("&") if not p.startswith("hash=")]
    no_hash_data = "&".join(pairs)

    response = client.get(
        "/api/me",
        headers={"Authorization": f"tma {no_hash_data}"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Missing hash in initData"


@pytest.mark.asyncio
async def test_get_me_missing_auth_date_returns_unauthorized(api_context):
    """Verifies REQ-API-01: GET /api/me with missing auth_date returns 401 Unauthorized."""
    client, _, settings = api_context
    user_data = {"id": 12345}
    no_auth_date_data = create_test_init_data(
        user_data,
        bot_token=settings.BOT_TOKEN,
        include_auth_date=False,
    )

    response = client.get(
        "/api/me",
        headers={"Authorization": f"tma {no_auth_date_data}"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Missing or invalid auth_date in initData"


@pytest.mark.asyncio
async def test_get_me_missing_user_parameter_returns_unauthorized(api_context):
    """Verifies REQ-API-01: GET /api/me with missing user parameter returns 401 Unauthorized."""
    client, _, settings = api_context
    # Generate validly signed initData without user parameter
    no_user_data = create_test_init_data(
        user_data=None,
        bot_token=settings.BOT_TOKEN,
    )

    response = client.get(
        "/api/me",
        headers={"Authorization": f"tma {no_user_data}"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Missing or invalid user object in initData"


@pytest.mark.asyncio
async def test_get_me_invalid_user_json_returns_unauthorized(api_context):
    """Verifies REQ-API-01: GET /api/me with malformed user JSON returns 401 Unauthorized."""
    client, _, settings = api_context
    # Manually construct initData with invalid json in user field
    auth_date = str(int(time.time()))
    user_str = "not_valid_json"
    params = {"auth_date": auth_date, "user": user_str}
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))
    secret_key = hmac.new(b"WebAppData", settings.BOT_TOKEN.encode("utf-8"), hashlib.sha256).digest()
    params["hash"] = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()
    query_str = urllib.parse.urlencode(params)

    response = client.get(
        "/api/me",
        headers={"Authorization": f"tma {query_str}"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Missing or invalid user object in initData"


@pytest.mark.asyncio
async def test_get_me_user_without_id_returns_unauthorized(api_context):
    """Verifies REQ-API-01: GET /api/me with user object missing 'id' returns 401 Unauthorized."""
    client, _, settings = api_context
    user_without_id = {"first_name": "NoId"}
    init_data = create_test_init_data(user_without_id, bot_token=settings.BOT_TOKEN)

    response = client.get(
        "/api/me",
        headers={"Authorization": f"tma {init_data}"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Missing or invalid user object in initData"


@pytest.mark.asyncio
async def test_get_me_missing_auth_headers_returns_unauthorized(api_context):
    """Verifies REQ-API-01: GET /api/me with no authorization headers returns 401 Unauthorized."""
    client, _, _ = api_context
    response = client.get("/api/me")
    assert response.status_code == 401
    assert response.json()["detail"] == "Missing or invalid authentication credentials"


@pytest.mark.asyncio
async def test_get_me_malformed_header_scheme_returns_unauthorized(api_context):
    """Verifies REQ-API-01: GET /api/me with unrecognized scheme returns 401 Unauthorized."""
    client, _, _ = api_context
    # Basic scheme
    res1 = client.get("/api/me", headers={"Authorization": "Basic 12345"})
    assert res1.status_code == 401
    assert res1.json()["detail"] == "Missing or invalid authentication credentials"

    # Empty Authorization header
    res2 = client.get("/api/me", headers={"Authorization": ""})
    assert res2.status_code == 401
    assert res2.json()["detail"] == "Missing or invalid authentication credentials"

    # Scheme without data
    res3 = client.get("/api/me", headers={"Authorization": "tma"})
    assert res3.status_code == 401
    assert res3.json()["detail"] == "Missing or invalid authentication credentials"

    # Empty X-Telegram-Init-Data header
    res4 = client.get("/api/me", headers={"X-Telegram-Init-Data": "   "})
    assert res4.status_code == 401
    assert res4.json()["detail"] == "Missing or invalid authentication credentials"


@pytest.mark.asyncio
async def test_get_current_user_provisions_new_user(api_context):
    """Verifies REQ-USR-01: get_current_user provisions new user in database with Europe/Kyiv."""
    client, session_factory, settings = api_context
    telegram_id = 9988776655
    user_data = {"id": telegram_id, "first_name": "NewUser"}
    init_data = create_test_init_data(user_data, bot_token=settings.BOT_TOKEN)

    # Verify user does not exist in DB prior to request
    async with session_factory() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        assert result.scalar_one_or_none() is None

    # Call endpoint
    response = client.get("/api/me", headers={"Authorization": f"tma {init_data}"})
    assert response.status_code == 200
    assert response.json()["telegram_id"] == telegram_id
    assert response.json()["timezone"] == "Europe/Kyiv"

    # Verify user record was provisioned and persisted in DB
    async with session_factory() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user_in_db = result.scalar_one_or_none()
        assert user_in_db is not None
        assert user_in_db.telegram_id == telegram_id
        assert user_in_db.timezone == "Europe/Kyiv"


@pytest.mark.asyncio
async def test_get_current_user_returns_existing_user_idempotently(api_context):
    """Verifies REQ-USR-01, REQ-NFR-02: get_current_user preserves existing user and custom timezone."""
    client, session_factory, settings = api_context
    telegram_id = 3344556677
    custom_tz = "America/New_York"

    # Pre-seed user with custom timezone
    async with session_factory() as session:
        existing_user = User(telegram_id=telegram_id, timezone=custom_tz)
        session.add(existing_user)
        await session.commit()

    # Authenticate via Mini App
    user_data = {"id": telegram_id, "first_name": "ExistingUser"}
    init_data = create_test_init_data(user_data, bot_token=settings.BOT_TOKEN)

    response = client.get("/api/me", headers={"Authorization": f"tma {init_data}"})
    assert response.status_code == 200
    data = response.json()
    assert data["telegram_id"] == telegram_id
    assert data["timezone"] == custom_tz

    # Verify no duplicate user and timezone was not reset
    async with session_factory() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        all_users = result.scalars().all()
        assert len(all_users) == 1
        assert all_users[0].timezone == custom_tz
