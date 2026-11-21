"""Integration tests for GET /api/tasks/analytics endpoint, streak calculation, and tenant isolation."""

from collections.abc import AsyncGenerator
from datetime import date, timedelta
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
from src.services.task_service import get_productivity_analytics
from src.services.user_service import get_user_local_time


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
async def analytics_test_ctx() -> AsyncGenerator[
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
async def test_analytics_new_user_empty(
    analytics_test_ctx: tuple[TestClient, async_sessionmaker[AsyncSession], Settings],
) -> None:
    """Verifies REQ-TMA-04, REQ-API-01: New user with 0 completed tasks returns streak 0 and empty stats."""
    client, session_factory, settings = analytics_test_ctx
    user_id = 100001

    async with session_factory() as session:
        user = User(telegram_id=user_id, timezone="Europe/Kyiv")
        session.add(user)
        await session.commit()

    init_data = create_test_init_data(
        {"id": user_id, "first_name": "NewUser"},
        bot_token=settings.BOT_TOKEN,
    )

    response = client.get(
        "/api/tasks/analytics",
        headers={"Authorization": f"tma {init_data}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["streak_current"] == 0
    assert data["streak_longest"] == 0
    assert data["total_tasks"] == 0
    assert data["completed_tasks"] == 0
    assert data["completion_rate"] == 0.0
    assert len(data["daily_trends"]) == 14
    assert data["tag_breakdown"] == []


@pytest.mark.asyncio
async def test_analytics_streak_calculation_scenarios(
    analytics_test_ctx: tuple[TestClient, async_sessionmaker[AsyncSession], Settings],
) -> None:
    """Verifies REQ-TMA-04: Test streak calculation logic across multiple historical scenarios."""
    _, session_factory, _ = analytics_test_ctx
    ref_date = date(2026, 11, 21)

    # Scenario 1: Consecutive ending today (ref_date, ref_date-1, ref_date-2) -> streak_current == 3
    async with session_factory() as session:
        u1 = User(telegram_id=1001, timezone="Europe/Kyiv")
        session.add(u1)
        session.add(Task(user_id=1001, title="T1", target_date=ref_date, status=TaskStatus.done))
        session.add(Task(user_id=1001, title="T2", target_date=ref_date - timedelta(days=1), status=TaskStatus.done))
        session.add(Task(user_id=1001, title="T3", target_date=ref_date - timedelta(days=2), status=TaskStatus.done))
        await session.commit()

        res1 = await get_productivity_analytics(session, user_id=1001, reference_date=ref_date)
        assert res1.streak_current == 3
        assert res1.streak_longest == 3

    # Scenario 2: Consecutive ending yesterday (ref_date-1, ref_date-2), 0 today -> streak_current == 2 (grace period)
    async with session_factory() as session:
        u2 = User(telegram_id=1002, timezone="Europe/Kyiv")
        session.add(u2)
        session.add(Task(user_id=1002, title="T1", target_date=ref_date - timedelta(days=1), status=TaskStatus.done))
        session.add(Task(user_id=1002, title="T2", target_date=ref_date - timedelta(days=2), status=TaskStatus.done))
        # Task today is still todo
        session.add(Task(user_id=1002, title="T3", target_date=ref_date, status=TaskStatus.todo))
        await session.commit()

        res2 = await get_productivity_analytics(session, user_id=1002, reference_date=ref_date)
        assert res2.streak_current == 2
        assert res2.streak_longest == 2

    # Scenario 3: Broken streak (completed 2 days ago, 0 yesterday, 0 today) -> streak_current == 0
    async with session_factory() as session:
        u3 = User(telegram_id=1003, timezone="Europe/Kyiv")
        session.add(u3)
        session.add(Task(user_id=1003, title="T1", target_date=ref_date - timedelta(days=2), status=TaskStatus.done))
        await session.commit()

        res3 = await get_productivity_analytics(session, user_id=1003, reference_date=ref_date)
        assert res3.streak_current == 0
        assert res3.streak_longest == 1

    # Scenario 4: Longest streak (5-day streak last week, 2-day gap, 2-day streak ending today)
    # 5-day streak: ref_date - 10, -9, -8, -7, -6
    # 2-day gap: ref_date - 5, -4
    # 2-day streak: ref_date - 1, ref_date
    async with session_factory() as session:
        u4 = User(telegram_id=1004, timezone="Europe/Kyiv")
        session.add(u4)
        for d in [10, 9, 8, 7, 6]:
            session.add(Task(user_id=1004, title=f"T-{d}", target_date=ref_date - timedelta(days=d), status=TaskStatus.done))
        session.add(Task(user_id=1004, title="T-1", target_date=ref_date - timedelta(days=1), status=TaskStatus.done))
        session.add(Task(user_id=1004, title="T-0", target_date=ref_date, status=TaskStatus.done))
        await session.commit()

        res4 = await get_productivity_analytics(session, user_id=1004, reference_date=ref_date)
        assert res4.streak_current == 2
        assert res4.streak_longest == 5


@pytest.mark.asyncio
async def test_analytics_daily_trends_continuity_and_accuracy(
    analytics_test_ctx: tuple[TestClient, async_sessionmaker[AsyncSession], Settings],
) -> None:
    """Verifies REQ-TMA-04: Daily trends include all days in window with accurate completion rates."""
    client, session_factory, settings = analytics_test_ctx
    user_id = 100005

    async with session_factory() as session:
        user = User(telegram_id=user_id, timezone="Europe/Kyiv")
        session.add(user)
        await session.commit()
        today = get_user_local_time(user).date()

        # Day today: 2 total, 2 completed -> 100.0%
        session.add(Task(user_id=user_id, title="A1", target_date=today, status=TaskStatus.done))
        session.add(Task(user_id=user_id, title="A2", target_date=today, status=TaskStatus.done))

        # Day today - 1: 3 total, 1 completed, 1 todo, 1 canceled -> 2 non-canceled, 1 completed -> 50.0%
        d1 = today - timedelta(days=1)
        session.add(Task(user_id=user_id, title="B1", target_date=d1, status=TaskStatus.done))
        session.add(Task(user_id=user_id, title="B2", target_date=d1, status=TaskStatus.todo))
        session.add(Task(user_id=user_id, title="B3", target_date=d1, status=TaskStatus.canceled))

        # Day today - 2: 0 tasks (zero-task day)
        # Day today - 3: 1 total, 0 completed -> 0.0%
        d3 = today - timedelta(days=3)
        session.add(Task(user_id=user_id, title="C1", target_date=d3, status=TaskStatus.todo))

        await session.commit()

    init_data = create_test_init_data(
        {"id": user_id, "first_name": "TrendUser"},
        bot_token=settings.BOT_TOKEN,
    )

    response = client.get(
        "/api/tasks/analytics?days=7",
        headers={"Authorization": f"tma {init_data}"},
    )

    assert response.status_code == 200
    data = response.json()
    trends = data["daily_trends"]
    assert len(trends) == 7

    start_date = today - timedelta(days=6)
    # Check continuous sequence
    for i, item in enumerate(trends):
        expected_date = start_date + timedelta(days=i)
        assert item["date"] == expected_date.isoformat()

    # Check today (last item)
    today_item = trends[-1]
    assert today_item["total_tasks"] == 2
    assert today_item["completed_tasks"] == 2
    assert today_item["completion_rate"] == 100.0

    # Check yesterday (second to last item)
    yesterday_item = trends[-2]
    assert yesterday_item["total_tasks"] == 2  # canceled excluded
    assert yesterday_item["completed_tasks"] == 1
    assert yesterday_item["completion_rate"] == 50.0

    # Check day - 2 (zero tasks)
    zero_item = trends[-3]
    assert zero_item["total_tasks"] == 0
    assert zero_item["completed_tasks"] == 0
    assert zero_item["completion_rate"] == 0.0

    # Check day - 3 (0 of 1)
    d3_item = trends[-4]
    assert d3_item["total_tasks"] == 1
    assert d3_item["completed_tasks"] == 0
    assert d3_item["completion_rate"] == 0.0

    # Summary metrics for 7-day window
    assert data["total_tasks"] == 5  # 2 + 2 + 0 + 1 = 5
    assert data["completed_tasks"] == 3  # 2 + 1 + 0 + 0 = 3
    assert data["completion_rate"] == 60.0  # round(3/5 * 100, 1) = 60.0


@pytest.mark.asyncio
async def test_analytics_tag_breakdown_and_canceled_exclusion(
    analytics_test_ctx: tuple[TestClient, async_sessionmaker[AsyncSession], Settings],
) -> None:
    """Verifies REQ-TMA-04: Tag breakdown groups untagged tasks under 'Без тегу' and excludes canceled tasks."""
    client, session_factory, settings = analytics_test_ctx
    user_id = 100006

    async with session_factory() as session:
        user = User(telegram_id=user_id, timezone="Europe/Kyiv")
        session.add(user)
        await session.commit()
        today = get_user_local_time(user).date()

        # Tag 'робота': 3 tasks (2 done, 1 todo)
        session.add(Task(user_id=user_id, title="R1", target_date=today, tag="робота", status=TaskStatus.done))
        session.add(Task(user_id=user_id, title="R2", target_date=today, tag="робота", status=TaskStatus.done))
        session.add(Task(user_id=user_id, title="R3", target_date=today, tag="робота", status=TaskStatus.todo))
        # Canceled task with tag 'робота' (must be excluded)
        session.add(Task(user_id=user_id, title="R4", target_date=today, tag="робота", status=TaskStatus.canceled))

        # Tag 'спорт': 2 tasks (1 done, 1 todo)
        session.add(Task(user_id=user_id, title="S1", target_date=today, tag="спорт", status=TaskStatus.done))
        session.add(Task(user_id=user_id, title="S2", target_date=today, tag="спорт", status=TaskStatus.todo))

        # No tag (None or empty): 1 task (1 done)
        session.add(Task(user_id=user_id, title="U1", target_date=today, tag=None, status=TaskStatus.done))
        session.add(Task(user_id=user_id, title="U2", target_date=today, tag="   ", status=TaskStatus.todo))

        await session.commit()

    init_data = create_test_init_data(
        {"id": user_id, "first_name": "TagUser"},
        bot_token=settings.BOT_TOKEN,
    )

    response = client.get(
        "/api/tasks/analytics?days=14",
        headers={"Authorization": f"tma {init_data}"},
    )

    assert response.status_code == 200
    data = response.json()
    breakdown = data["tag_breakdown"]

    # Total non-canceled tasks: 3 (робота) + 2 (спорт) + 2 (Без тегу) = 7
    assert data["total_tasks"] == 7

    # Breakdown ordered by count DESC, then tag ASC
    assert len(breakdown) == 3

    item0 = breakdown[0]
    assert item0["tag"] == "робота"
    assert item0["count"] == 3
    assert item0["completed_count"] == 2
    assert item0["percentage"] == round(3 / 7 * 100, 1)

    # Both 'Без тегу' and 'спорт' have count=2. 'Без тегу' comes before 'спорт' alphabetically
    tags = [b["tag"] for b in breakdown]
    assert "Без тегу" in tags
    assert "спорт" in tags

    untagged_item = next(b for b in breakdown if b["tag"] == "Без тегу")
    assert untagged_item["count"] == 2
    assert untagged_item["completed_count"] == 1
    assert untagged_item["percentage"] == round(2 / 7 * 100, 1)

    sport_item = next(b for b in breakdown if b["tag"] == "спорт")
    assert sport_item["count"] == 2
    assert sport_item["completed_count"] == 1
    assert sport_item["percentage"] == round(2 / 7 * 100, 1)


@pytest.mark.asyncio
async def test_analytics_days_query_validation(
    analytics_test_ctx: tuple[TestClient, async_sessionmaker[AsyncSession], Settings],
) -> None:
    """Verifies REQ-API-01, REQ-TMA-04: Validates days parameter (7 <= days <= 90) and rejects invalid values with 422."""
    client, session_factory, settings = analytics_test_ctx
    user_id = 100007

    async with session_factory() as session:
        user = User(telegram_id=user_id, timezone="Europe/Kyiv")
        session.add(user)
        await session.commit()

    init_data = create_test_init_data(
        {"id": user_id, "first_name": "ValidUser"},
        bot_token=settings.BOT_TOKEN,
    )

    # Valid boundaries
    for valid_days in [7, 14, 30, 90]:
        res = client.get(
            f"/api/tasks/analytics?days={valid_days}",
            headers={"Authorization": f"tma {init_data}"},
        )
        assert res.status_code == 200
        assert len(res.json()["daily_trends"]) == valid_days

    # Invalid: days < 7
    res_under = client.get(
        "/api/tasks/analytics?days=6",
        headers={"Authorization": f"tma {init_data}"},
    )
    assert res_under.status_code == 422

    # Invalid: days > 90
    res_over = client.get(
        "/api/tasks/analytics?days=91",
        headers={"Authorization": f"tma {init_data}"},
    )
    assert res_over.status_code == 422

    # Invalid: non-integer
    res_str = client.get(
        "/api/tasks/analytics?days=two_weeks",
        headers={"Authorization": f"tma {init_data}"},
    )
    assert res_str.status_code == 422


@pytest.mark.asyncio
async def test_analytics_strict_tenant_isolation(
    analytics_test_ctx: tuple[TestClient, async_sessionmaker[AsyncSession], Settings],
) -> None:
    """Verifies REQ-NFR-02: Tasks of User B are strictly isolated and never included in User A's analytics."""
    client, session_factory, settings = analytics_test_ctx
    user_a_id = 200001
    user_b_id = 200002

    async with session_factory() as session:
        user_a = User(telegram_id=user_a_id, timezone="Europe/Kyiv")
        user_b = User(telegram_id=user_b_id, timezone="Europe/Kyiv")
        session.add_all([user_a, user_b])
        await session.commit()
        today = get_user_local_time(user_a).date()

        # User A has 1 task (done)
        session.add(Task(user_id=user_a_id, title="User A Task", target_date=today, tag="alpha", status=TaskStatus.done))

        # User B has 10 tasks across multiple days (done) with different tag
        for i in range(5):
            d = today - timedelta(days=i)
            session.add(Task(user_id=user_b_id, title=f"User B Task {i}", target_date=d, tag="beta", status=TaskStatus.done))
        await session.commit()

    init_data_a = create_test_init_data(
        {"id": user_a_id, "first_name": "UserA"},
        bot_token=settings.BOT_TOKEN,
    )

    response_a = client.get(
        "/api/tasks/analytics?days=14",
        headers={"Authorization": f"tma {init_data_a}"},
    )

    assert response_a.status_code == 200
    data_a = response_a.json()
    assert data_a["total_tasks"] == 1
    assert data_a["completed_tasks"] == 1
    assert data_a["completion_rate"] == 100.0
    assert data_a["streak_current"] == 1
    assert data_a["streak_longest"] == 1
    assert len(data_a["tag_breakdown"]) == 1
    assert data_a["tag_breakdown"][0]["tag"] == "alpha"


@pytest.mark.asyncio
async def test_analytics_authentication_enforcement(
    analytics_test_ctx: tuple[TestClient, async_sessionmaker[AsyncSession], Settings],
) -> None:
    """Verifies REQ-API-01: Requests missing or invalid Authorization header return HTTP 401 Unauthorized."""
    client, _, settings = analytics_test_ctx

    # Missing header
    res_no_auth = client.get("/api/tasks/analytics")
    assert res_no_auth.status_code == 401

    # Invalid header prefix
    res_bad_prefix = client.get(
        "/api/tasks/analytics",
        headers={"Authorization": "Bearer some_jwt_token"},
    )
    assert res_bad_prefix.status_code == 401

    # Tampered signature
    tampered_init_data = create_test_init_data(
        {"id": 999999, "first_name": "Hacker"},
        bot_token="wrong_token_secret",
    )
    res_tampered = client.get(
        "/api/tasks/analytics",
        headers={"Authorization": f"tma {tampered_init_data}"},
    )
    assert res_tampered.status_code == 401
