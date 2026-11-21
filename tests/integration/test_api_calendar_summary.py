"""Integration tests for GET /api/tasks/calendar-summary endpoint and tenant isolation."""

from collections.abc import AsyncGenerator
from datetime import date
import hashlib
import hmac
import json
import time
from typing import Any
import urllib.parse

from fastapi.testclient import TestClient
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.api.app import create_app
from src.core.config import Settings
from src.core.database import configure_sqlite_pragmas
from src.models.base import Base
from src.models.task import Task, TaskPriority, TaskStatus
from src.models.user import User


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
async def calendar_test_ctx() -> AsyncGenerator[
    tuple[TestClient, async_sessionmaker[AsyncSession], Settings], None
]:
    """Provide isolated in-memory SQLite database and configured TestClient."""
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
async def test_calendar_summary_empty_month(
    calendar_test_ctx: tuple[TestClient, async_sessionmaker[AsyncSession], Settings],
) -> None:
    """Verifies REQ-TMA-03, REQ-API-01: When no tasks exist in requested month, returns empty list []."""
    client, session_factory, settings = calendar_test_ctx
    user_id = 111111

    # Ensure user exists in database
    async with session_factory() as session:
        user = User(telegram_id=user_id, timezone="Europe/Kyiv")
        session.add(user)
        await session.commit()

    init_data = create_test_init_data(
        {"id": user_id, "first_name": "TestUser"},
        bot_token=settings.BOT_TOKEN,
    )

    response = client.get(
        "/api/tasks/calendar-summary?year=2026&month=11",
        headers={"Authorization": f"tma {init_data}"},
    )

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_calendar_summary_statuses_and_aggregation(
    calendar_test_ctx: tuple[TestClient, async_sessionmaker[AsyncSession], Settings],
) -> None:
    """Verifies REQ-TMA-03: Returns daily summaries with accurate counts and statuses (all_done, partial, todo_only)."""
    client, session_factory, settings = calendar_test_ctx
    user_id = 222222

    async with session_factory() as session:
        user = User(telegram_id=user_id, timezone="Europe/Kyiv")
        session.add(user)

        # Day 1: 2 tasks, 2 done -> all_done
        d1 = date(2026, 11, 5)
        t1 = Task(user_id=user_id, title="T1", target_date=d1, status=TaskStatus.done)
        t2 = Task(user_id=user_id, title="T2", target_date=d1, status=TaskStatus.done)

        # Day 2: 3 tasks, 1 done, 2 todo -> partial
        d2 = date(2026, 11, 10)
        t3 = Task(user_id=user_id, title="T3", target_date=d2, status=TaskStatus.done)
        t4 = Task(user_id=user_id, title="T4", target_date=d2, status=TaskStatus.todo)
        t5 = Task(user_id=user_id, title="T5", target_date=d2, status=TaskStatus.todo)

        # Day 3: 2 tasks, 0 done, 2 todo -> todo_only
        d3 = date(2026, 11, 20)
        t6 = Task(user_id=user_id, title="T6", target_date=d3, status=TaskStatus.todo)
        t7 = Task(user_id=user_id, title="T7", target_date=d3, status=TaskStatus.todo)

        # Day 4: 1 done task + 1 canceled task -> total should be 1, completed 1 -> all_done (canceled excluded)
        d4 = date(2026, 11, 25)
        t8 = Task(user_id=user_id, title="T8", target_date=d4, status=TaskStatus.done)
        t9 = Task(user_id=user_id, title="T9", target_date=d4, status=TaskStatus.canceled)

        session.add_all([t1, t2, t3, t4, t5, t6, t7, t8, t9])
        await session.commit()

    init_data = create_test_init_data(
        {"id": user_id, "first_name": "TestUser"},
        bot_token=settings.BOT_TOKEN,
    )

    response = client.get(
        "/api/tasks/calendar-summary?year=2026&month=11",
        headers={"Authorization": f"tma {init_data}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 4

    # Day 5 (all_done)
    assert data[0]["date"] == "2026-11-05"
    assert data[0]["total_tasks"] == 2
    assert data[0]["completed_tasks"] == 2
    assert data[0]["status"] == "all_done"

    # Day 10 (partial)
    assert data[1]["date"] == "2026-11-10"
    assert data[1]["total_tasks"] == 3
    assert data[1]["completed_tasks"] == 1
    assert data[1]["status"] == "partial"

    # Day 20 (todo_only)
    assert data[2]["date"] == "2026-11-20"
    assert data[2]["total_tasks"] == 2
    assert data[2]["completed_tasks"] == 0
    assert data[2]["status"] == "todo_only"

    # Day 25 (canceled excluded -> 1 total, 1 completed -> all_done)
    assert data[3]["date"] == "2026-11-25"
    assert data[3]["total_tasks"] == 1
    assert data[3]["completed_tasks"] == 1
    assert data[3]["status"] == "all_done"


@pytest.mark.asyncio
async def test_calendar_summary_strict_tenant_isolation(
    calendar_test_ctx: tuple[TestClient, async_sessionmaker[AsyncSession], Settings],
) -> None:
    """Verifies REQ-NFR-02: User A never receives User B's tasks in monthly summary."""
    client, session_factory, settings = calendar_test_ctx
    user_a = 100001
    user_b = 200002

    async with session_factory() as session:
        session.add_all([
            User(telegram_id=user_a, timezone="Europe/Kyiv"),
            User(telegram_id=user_b, timezone="Europe/Kyiv"),
        ])

        target_date = date(2026, 11, 15)
        # User A task
        session.add(Task(user_id=user_a, title="User A Task", target_date=target_date, status=TaskStatus.done))
        # User B tasks
        session.add(Task(user_id=user_b, title="User B Task 1", target_date=target_date, status=TaskStatus.todo))
        session.add(Task(user_id=user_b, title="User B Task 2", target_date=target_date, status=TaskStatus.todo))

        await session.commit()

    # Query as User A
    init_data_a = create_test_init_data({"id": user_a, "first_name": "UserA"}, bot_token=settings.BOT_TOKEN)
    res_a = client.get(
        "/api/tasks/calendar-summary?year=2026&month=11",
        headers={"Authorization": f"tma {init_data_a}"},
    )
    assert res_a.status_code == 200
    data_a = res_a.json()
    assert len(data_a) == 1
    assert data_a[0]["total_tasks"] == 1
    assert data_a[0]["completed_tasks"] == 1
    assert data_a[0]["status"] == "all_done"

    # Query as User B
    init_data_b = create_test_init_data({"id": user_b, "first_name": "UserB"}, bot_token=settings.BOT_TOKEN)
    res_b = client.get(
        "/api/tasks/calendar-summary?year=2026&month=11",
        headers={"Authorization": f"tma {init_data_b}"},
    )
    assert res_b.status_code == 200
    data_b = res_b.json()
    assert len(data_b) == 1
    assert data_b[0]["total_tasks"] == 2
    assert data_b[0]["completed_tasks"] == 0
    assert data_b[0]["status"] == "todo_only"


@pytest.mark.asyncio
async def test_calendar_summary_month_boundaries_excluded(
    calendar_test_ctx: tuple[TestClient, async_sessionmaker[AsyncSession], Settings],
) -> None:
    """Verifies REQ-TMA-03: Tasks in adjacent months (prev/next) are strictly excluded."""
    client, session_factory, settings = calendar_test_ctx
    user_id = 333333

    async with session_factory() as session:
        user = User(telegram_id=user_id, timezone="Europe/Kyiv")
        session.add(user)

        # Last day of October 2026 (boundary before)
        session.add(Task(user_id=user_id, title="Oct Task", target_date=date(2026, 10, 31), status=TaskStatus.done))
        # First day of November 2026 (in month)
        session.add(Task(user_id=user_id, title="Nov Task 1", target_date=date(2026, 11, 1), status=TaskStatus.done))
        # Last day of November 2026 (in month)
        session.add(Task(user_id=user_id, title="Nov Task 30", target_date=date(2026, 11, 30), status=TaskStatus.todo))
        # First day of December 2026 (boundary after)
        session.add(Task(user_id=user_id, title="Dec Task", target_date=date(2026, 12, 1), status=TaskStatus.done))

        await session.commit()

    init_data = create_test_init_data({"id": user_id, "first_name": "User333"}, bot_token=settings.BOT_TOKEN)
    response = client.get(
        "/api/tasks/calendar-summary?year=2026&month=11",
        headers={"Authorization": f"tma {init_data}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    dates = [item["date"] for item in data]
    assert dates == ["2026-11-01", "2026-11-30"]


@pytest.mark.asyncio
async def test_calendar_summary_leap_year_february(
    calendar_test_ctx: tuple[TestClient, async_sessionmaker[AsyncSession], Settings],
) -> None:
    """Verifies REQ-TMA-03: Correctly accounts for leap year February 29th."""
    client, session_factory, settings = calendar_test_ctx
    user_id = 444444

    async with session_factory() as session:
        user = User(telegram_id=user_id, timezone="Europe/Kyiv")
        session.add(user)

        # Leap year 2024: Feb 29
        session.add(Task(user_id=user_id, title="Leap Day Task", target_date=date(2024, 2, 29), status=TaskStatus.done))
        # Mar 1
        session.add(Task(user_id=user_id, title="Mar 1 Task", target_date=date(2024, 3, 1), status=TaskStatus.done))

        await session.commit()

    init_data = create_test_init_data({"id": user_id, "first_name": "User444"}, bot_token=settings.BOT_TOKEN)
    response = client.get(
        "/api/tasks/calendar-summary?year=2024&month=2",
        headers={"Authorization": f"tma {init_data}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["date"] == "2024-02-29"
    assert data[0]["total_tasks"] == 1
    assert data[0]["completed_tasks"] == 1
    assert data[0]["status"] == "all_done"


@pytest.mark.asyncio
async def test_calendar_summary_invalid_query_parameters(
    calendar_test_ctx: tuple[TestClient, async_sessionmaker[AsyncSession], Settings],
) -> None:
    """Verifies REQ-TMA-03, REQ-API-01: Invalid query params return HTTP 422 Unprocessable Entity."""
    client, _, settings = calendar_test_ctx
    init_data = create_test_init_data({"id": 555555, "first_name": "User555"}, bot_token=settings.BOT_TOKEN)
    headers = {"Authorization": f"tma {init_data}"}

    # month = 0
    res = client.get("/api/tasks/calendar-summary?year=2026&month=0", headers=headers)
    assert res.status_code == 422

    # month = 13
    res = client.get("/api/tasks/calendar-summary?year=2026&month=13", headers=headers)
    assert res.status_code == 422

    # year = 1899
    res = client.get("/api/tasks/calendar-summary?year=1899&month=11", headers=headers)
    assert res.status_code == 422

    # year = 2101
    res = client.get("/api/tasks/calendar-summary?year=2101&month=11", headers=headers)
    assert res.status_code == 422

    # Missing parameters
    res = client.get("/api/tasks/calendar-summary", headers=headers)
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_calendar_summary_unauthorized_requests(
    calendar_test_ctx: tuple[TestClient, async_sessionmaker[AsyncSession], Settings],
) -> None:
    """Verifies REQ-API-01: Requests without valid Authorization header return HTTP 401 Unauthorized."""
    client, _, _ = calendar_test_ctx

    # No Authorization header
    res_no_auth = client.get("/api/tasks/calendar-summary?year=2026&month=11")
    assert res_no_auth.status_code == 401

    # Invalid Authorization scheme
    res_bad_scheme = client.get(
        "/api/tasks/calendar-summary?year=2026&month=11",
        headers={"Authorization": "Bearer some_invalid_token"},
    )
    assert res_bad_scheme.status_code == 401

    # Invalid HMAC signature
    res_bad_hash = client.get(
        "/api/tasks/calendar-summary?year=2026&month=11",
        headers={"Authorization": "tma user=%7B%22id%22%3A123%7D&auth_date=1700000000&hash=invalid_hash"},
    )
    assert res_bad_hash.status_code == 401


@pytest.mark.asyncio
async def test_calendar_summary_not_shadowed_by_task_id_route(
    calendar_test_ctx: tuple[TestClient, async_sessionmaker[AsyncSession], Settings],
) -> None:
    """Verifies REQ-TMA-03: /calendar-summary is not routed into /{task_id} as a path parameter."""
    client, _, settings = calendar_test_ctx
    init_data = create_test_init_data({"id": 777777, "first_name": "User777"}, bot_token=settings.BOT_TOKEN)
    headers = {"Authorization": f"tma {init_data}"}

    # Should not produce 422 (integer validation error on task_id)
    res = client.get("/api/tasks/calendar-summary?year=2026&month=11", headers=headers)
    assert res.status_code == 200
