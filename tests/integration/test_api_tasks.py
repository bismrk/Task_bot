"""Integration tests for Task REST API endpoints and tenant isolation."""

from collections.abc import AsyncGenerator
from datetime import date, datetime, timedelta, timezone
import hashlib
import hmac
import json
import time
from typing import Any
import urllib.parse

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.api.app import create_app
from src.core.config import Settings
from src.core.database import configure_sqlite_pragmas
from src.models.base import Base
from src.models.task import Task, TaskPriority, TaskStatus
from src.models.user import User
from src.services.task_service import create_task
from src.services.user_service import get_or_create_user, get_user_local_time


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
async def test_get_tasks_default_date_uses_user_timezone(api_context):
    """Verifies REQ-API-02: GET /api/tasks without date defaults to user's local date."""
    client, session_factory, settings = api_context
    user_id = 10001
    headers = get_auth_headers(user_id, settings.BOT_TOKEN)

    # Pre-create user with a specific timezone
    async with session_factory() as session:
        user, _ = await get_or_create_user(session, telegram_id=user_id, timezone="America/New_York")
        today_local = get_user_local_time(user).date()
        yesterday_local = today_local - timedelta(days=1)
        tomorrow_local = today_local + timedelta(days=1)

        task_today = Task(
            user_id=user_id,
            title="Today Task",
            target_date=today_local,
            priority=TaskPriority.medium,
            status=TaskStatus.todo,
            reminder_sent_1h=False,
            reminder_sent_10m=False,
        )
        task_yesterday = Task(
            user_id=user_id,
            title="Yesterday Task",
            target_date=yesterday_local,
            priority=TaskPriority.medium,
            status=TaskStatus.todo,
            reminder_sent_1h=False,
            reminder_sent_10m=False,
        )
        task_tomorrow = Task(
            user_id=user_id,
            title="Tomorrow Task",
            target_date=tomorrow_local,
            priority=TaskPriority.medium,
            status=TaskStatus.todo,
            reminder_sent_1h=False,
            reminder_sent_10m=False,
        )
        session.add_all([task_today, task_yesterday, task_tomorrow])
        await session.commit()

    # GET /api/tasks with no date parameter
    response = client.get("/api/tasks", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["title"] == "Today Task"
    assert data[0]["target_date"] == today_local.isoformat()


@pytest.mark.asyncio
async def test_get_tasks_specific_date_and_sorting(api_context):
    """Verifies REQ-API-02: GET /api/tasks?date=YYYY-MM-DD orders tasks by status (todo before done) and priority (high -> medium -> low)."""
    client, session_factory, settings = api_context
    user_id = 10002
    headers = get_auth_headers(user_id, settings.BOT_TOKEN)
    test_date = date(2026, 11, 20)

    async with session_factory() as session:
        await get_or_create_user(session, telegram_id=user_id)
        # Create tasks in mixed order
        t_done_low = Task(
            user_id=user_id,
            title="Done Low",
            target_date=test_date,
            priority=TaskPriority.low,
            status=TaskStatus.done,
            reminder_sent_1h=False,
            reminder_sent_10m=False,
        )
        t_done_high = Task(
            user_id=user_id,
            title="Done High",
            target_date=test_date,
            priority=TaskPriority.high,
            status=TaskStatus.done,
            reminder_sent_1h=False,
            reminder_sent_10m=False,
        )
        t_todo_low = Task(
            user_id=user_id,
            title="Todo Low",
            target_date=test_date,
            priority=TaskPriority.low,
            status=TaskStatus.todo,
            reminder_sent_1h=False,
            reminder_sent_10m=False,
        )
        t_todo_high_1 = Task(
            user_id=user_id,
            title="Todo High 1",
            target_date=test_date,
            priority=TaskPriority.high,
            status=TaskStatus.todo,
            reminder_sent_1h=False,
            reminder_sent_10m=False,
        )
        t_todo_med = Task(
            user_id=user_id,
            title="Todo Med",
            target_date=test_date,
            priority=TaskPriority.medium,
            status=TaskStatus.todo,
            reminder_sent_1h=False,
            reminder_sent_10m=False,
        )
        t_todo_high_2 = Task(
            user_id=user_id,
            title="Todo High 2",
            target_date=test_date,
            priority=TaskPriority.high,
            status=TaskStatus.todo,
            reminder_sent_1h=False,
            reminder_sent_10m=False,
        )
        session.add_all([
            t_done_low,
            t_done_high,
            t_todo_low,
            t_todo_high_1,
            t_todo_med,
            t_todo_high_2,
        ])
        await session.commit()

    response = client.get(f"/api/tasks?date={test_date.isoformat()}", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 6

    titles = [t["title"] for t in data]
    # Expected: Todo High 1, Todo High 2, Todo Med, Todo Low, Done High, Done Low
    assert titles == [
        "Todo High 1",
        "Todo High 2",
        "Todo Med",
        "Todo Low",
        "Done High",
        "Done Low",
    ]


@pytest.mark.asyncio
async def test_get_tasks_returns_empty_list_when_no_tasks(api_context):
    """Verifies REQ-API-02: GET /api/tasks returns [] with HTTP 200 when no tasks exist."""
    client, _, settings = api_context
    user_id = 10003
    headers = get_auth_headers(user_id, settings.BOT_TOKEN)

    response = client.get("/api/tasks?date=2099-01-01", headers=headers)
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_get_tasks_tenant_isolation(api_context):
    """Verifies REQ-NFR-02: GET /api/tasks strictly isolates tasks by authenticated user."""
    client, session_factory, settings = api_context
    user1_id = 10004
    user2_id = 20004
    test_date = date(2026, 11, 20)

    async with session_factory() as session:
        await get_or_create_user(session, telegram_id=user1_id)
        await get_or_create_user(session, telegram_id=user2_id)
        t1 = Task(
            user_id=user1_id,
            title="User 1 Task",
            target_date=test_date,
            priority=TaskPriority.high,
            status=TaskStatus.todo,
            reminder_sent_1h=False,
            reminder_sent_10m=False,
        )
        t2 = Task(
            user_id=user2_id,
            title="User 2 Task",
            target_date=test_date,
            priority=TaskPriority.high,
            status=TaskStatus.todo,
            reminder_sent_1h=False,
            reminder_sent_10m=False,
        )
        session.add_all([t1, t2])
        await session.commit()

    # User 1 GET
    headers1 = get_auth_headers(user1_id, settings.BOT_TOKEN)
    res1 = client.get(f"/api/tasks?date={test_date.isoformat()}", headers=headers1)
    assert res1.status_code == 200
    data1 = res1.json()
    assert len(data1) == 1
    assert data1[0]["title"] == "User 1 Task"

    # User 2 GET
    headers2 = get_auth_headers(user2_id, settings.BOT_TOKEN)
    res2 = client.get(f"/api/tasks?date={test_date.isoformat()}", headers=headers2)
    assert res2.status_code == 200
    data2 = res2.json()
    assert len(data2) == 1
    assert data2[0]["title"] == "User 2 Task"


@pytest.mark.asyncio
async def test_get_tasks_invalid_date_format_returns_422(api_context):
    """Verifies REQ-API-02: GET /api/tasks with invalid date format returns HTTP 422 Unprocessable Entity."""
    client, _, settings = api_context
    headers = get_auth_headers(10005, settings.BOT_TOKEN)

    response = client.get("/api/tasks?date=invalid-date-format", headers=headers)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_post_task_success(api_context):
    """Verifies REQ-TSK-01, REQ-API-02: POST /api/tasks persists task with status=todo, reminder flags False, and returns HTTP 201 Created and TaskRead."""
    client, session_factory, settings = api_context
    user_id = 10006
    headers = get_auth_headers(user_id, settings.BOT_TOKEN)

    payload = {
        "title": "Build Mini App backend",
        "target_date": "2026-11-20",
        "priority": "high",
        "tag": "#backend",
        "recurrence": "daily",
        "deadline_at": "2026-11-20T18:00:00Z",
    }

    response = client.post("/api/tasks", json=payload, headers=headers)
    assert response.status_code == 201
    data = response.json()

    assert data["title"] == "Build Mini App backend"
    assert data["target_date"] == "2026-11-20"
    assert data["priority"] == "high"
    assert data["tag"] == "backend"  # '#' is automatically stripped
    assert data["status"] == "todo"
    assert data["recurrence"] == "daily"
    assert data["reminder_sent_1h"] is False
    assert data["reminder_sent_10m"] is False
    assert data["user_id"] == user_id
    assert "id" in data
    assert "created_at" in data

    # Verify directly in DB
    task_id = data["id"]
    async with session_factory() as session:
        stmt = select(Task).where(Task.id == task_id)
        result = await session.execute(stmt)
        persisted = result.scalar_one_or_none()
        assert persisted is not None
        assert persisted.user_id == user_id
        assert persisted.status == TaskStatus.todo


@pytest.mark.asyncio
async def test_post_task_invalid_data_returns_422(api_context):
    """Verifies REQ-TSK-01, REQ-API-02: POST /api/tasks with invalid payload returns HTTP 422 without inserting records."""
    client, session_factory, settings = api_context
    user_id = 10007
    headers = get_auth_headers(user_id, settings.BOT_TOKEN)

    # Empty payload
    r1 = client.post("/api/tasks", json={}, headers=headers)
    assert r1.status_code == 422

    # Whitespace only title
    r2 = client.post(
        "/api/tasks",
        json={"title": "   ", "target_date": "2026-11-20"},
        headers=headers,
    )
    assert r2.status_code == 422

    # Missing target_date
    r3 = client.post("/api/tasks", json={"title": "Task title"}, headers=headers)
    assert r3.status_code == 422

    # Invalid date format
    r4 = client.post(
        "/api/tasks",
        json={"title": "Task title", "target_date": "20-11-2026"},
        headers=headers,
    )
    assert r4.status_code == 422

    # Verify no tasks were created in DB
    async with session_factory() as session:
        stmt = select(Task).where(Task.user_id == user_id)
        result = await session.execute(stmt)
        assert len(result.scalars().all()) == 0


@pytest.mark.asyncio
async def test_get_task_by_id_success(api_context):
    """Verifies REQ-API-02: GET /api/tasks/{task_id} returns task serialized as TaskRead with HTTP 200 OK."""
    client, session_factory, settings = api_context
    user_id = 10008
    headers = get_auth_headers(user_id, settings.BOT_TOKEN)

    async with session_factory() as session:
        await get_or_create_user(session, telegram_id=user_id)
        task = Task(
            user_id=user_id,
            title="Inspect task",
            target_date=date(2026, 11, 20),
            priority=TaskPriority.medium,
            status=TaskStatus.todo,
            reminder_sent_1h=False,
            reminder_sent_10m=False,
        )
        session.add(task)
        await session.commit()
        await session.refresh(task)
        task_id = task.id

    response = client.get(f"/api/tasks/{task_id}", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == task_id
    assert data["title"] == "Inspect task"
    assert data["user_id"] == user_id


@pytest.mark.asyncio
async def test_get_task_by_id_not_found(api_context):
    """Verifies REQ-API-02: GET /api/tasks/{task_id} for non-existent ID raises HTTP 404 Not Found."""
    client, _, settings = api_context
    headers = get_auth_headers(10009, settings.BOT_TOKEN)

    response = client.get("/api/tasks/999999", headers=headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "Task not found"


@pytest.mark.asyncio
async def test_get_task_by_id_tenant_isolation(api_context):
    """Verifies REQ-NFR-02: GET /api/tasks/{task_id} for another user's task raises HTTP 404 Not Found."""
    client, session_factory, settings = api_context
    owner_id = 10010
    attacker_id = 20010

    async with session_factory() as session:
        await get_or_create_user(session, telegram_id=owner_id)
        await get_or_create_user(session, telegram_id=attacker_id)
        task = Task(
            user_id=owner_id,
            title="Owner Secret Task",
            target_date=date(2026, 11, 20),
            priority=TaskPriority.high,
            status=TaskStatus.todo,
            reminder_sent_1h=False,
            reminder_sent_10m=False,
        )
        session.add(task)
        await session.commit()
        await session.refresh(task)
        task_id = task.id

    attacker_headers = get_auth_headers(attacker_id, settings.BOT_TOKEN)
    response = client.get(f"/api/tasks/{task_id}", headers=attacker_headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "Task not found"


@pytest.mark.asyncio
async def test_patch_task_by_id_success(api_context):
    """Verifies REQ-API-02: PATCH /api/tasks/{task_id} updates fields and returns HTTP 200 and updated TaskRead."""
    client, session_factory, settings = api_context
    user_id = 10011
    headers = get_auth_headers(user_id, settings.BOT_TOKEN)

    async with session_factory() as session:
        await get_or_create_user(session, telegram_id=user_id)
        task = Task(
            user_id=user_id,
            title="Original Title",
            target_date=date(2026, 11, 20),
            priority=TaskPriority.low,
            tag="work",
            status=TaskStatus.todo,
            reminder_sent_1h=False,
            reminder_sent_10m=False,
        )
        session.add(task)
        await session.commit()
        await session.refresh(task)
        task_id = task.id

    patch_payload = {
        "title": "Updated Title",
        "priority": "high",
        "tag": "#urgent",
    }
    response = client.patch(f"/api/tasks/{task_id}", json=patch_payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == task_id
    assert data["title"] == "Updated Title"
    assert data["priority"] == "high"
    assert data["tag"] == "urgent"


@pytest.mark.asyncio
async def test_patch_task_resets_reminder_flags_when_deadline_changes(api_context):
    """Verifies REQ-API-02: PATCH /api/tasks/{task_id} with new deadline_at resets reminder sent flags."""
    client, session_factory, settings = api_context
    user_id = 10012
    headers = get_auth_headers(user_id, settings.BOT_TOKEN)

    async with session_factory() as session:
        await get_or_create_user(session, telegram_id=user_id)
        task = Task(
            user_id=user_id,
            title="Task with reminders already sent",
            target_date=date(2026, 11, 20),
            priority=TaskPriority.medium,
            status=TaskStatus.todo,
            reminder_sent_1h=True,
            reminder_sent_10m=True,
        )
        session.add(task)
        await session.commit()
        await session.refresh(task)
        task_id = task.id

    new_deadline = "2026-11-20T20:00:00Z"
    patch_payload = {"deadline_at": new_deadline}
    response = client.patch(f"/api/tasks/{task_id}", json=patch_payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["reminder_sent_1h"] is False
    assert data["reminder_sent_10m"] is False

    # Check database persistence
    async with session_factory() as session:
        stmt = select(Task).where(Task.id == task_id)
        result = await session.execute(stmt)
        refreshed = result.scalar_one()
        assert refreshed.reminder_sent_1h is False
        assert refreshed.reminder_sent_10m is False


@pytest.mark.asyncio
async def test_patch_task_by_id_not_found(api_context):
    """Verifies REQ-API-02: PATCH /api/tasks/{task_id} for non-existent ID raises HTTP 404 Not Found."""
    client, _, settings = api_context
    headers = get_auth_headers(10013, settings.BOT_TOKEN)

    response = client.patch("/api/tasks/999999", json={"title": "New Title"}, headers=headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "Task not found"


@pytest.mark.asyncio
async def test_patch_task_by_id_tenant_isolation(api_context):
    """Verifies REQ-NFR-02: PATCH /api/tasks/{task_id} for another user's task raises HTTP 404 and does not mutate record."""
    client, session_factory, settings = api_context
    owner_id = 10014
    attacker_id = 20014

    async with session_factory() as session:
        await get_or_create_user(session, telegram_id=owner_id)
        await get_or_create_user(session, telegram_id=attacker_id)
        task = Task(
            user_id=owner_id,
            title="Owner Immutable Task",
            target_date=date(2026, 11, 20),
            priority=TaskPriority.medium,
            status=TaskStatus.todo,
            reminder_sent_1h=False,
            reminder_sent_10m=False,
        )
        session.add(task)
        await session.commit()
        await session.refresh(task)
        task_id = task.id

    attacker_headers = get_auth_headers(attacker_id, settings.BOT_TOKEN)
    response = client.patch(
        f"/api/tasks/{task_id}",
        json={"title": "Hacked Title"},
        headers=attacker_headers,
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Task not found"

    # Verify task title is untouched in DB
    async with session_factory() as session:
        stmt = select(Task).where(Task.id == task_id)
        result = await session.execute(stmt)
        db_task = result.scalar_one()
        assert db_task.title == "Owner Immutable Task"


@pytest.mark.asyncio
async def test_patch_task_by_id_validation_error(api_context):
    """Verifies REQ-API-02: PATCH /api/tasks/{task_id} with invalid fields returns HTTP 422 Unprocessable Entity."""
    client, session_factory, settings = api_context
    user_id = 10015
    headers = get_auth_headers(user_id, settings.BOT_TOKEN)

    async with session_factory() as session:
        await get_or_create_user(session, telegram_id=user_id)
        task = Task(
            user_id=user_id,
            title="Valid Task",
            target_date=date(2026, 11, 20),
            priority=TaskPriority.medium,
            status=TaskStatus.todo,
            reminder_sent_1h=False,
            reminder_sent_10m=False,
        )
        session.add(task)
        await session.commit()
        await session.refresh(task)
        task_id = task.id

    # Invalid empty title
    r1 = client.patch(f"/api/tasks/{task_id}", json={"title": "   "}, headers=headers)
    assert r1.status_code == 422

    # Invalid status enum
    r2 = client.patch(f"/api/tasks/{task_id}", json={"status": "invalid_status"}, headers=headers)
    assert r2.status_code == 422


@pytest.mark.asyncio
async def test_patch_task_toggle_status_cycle(api_context):
    """Verifies REQ-TSK-02: PATCH /api/tasks/{task_id}/toggle toggles status todo <-> done and returns HTTP 200."""
    client, session_factory, settings = api_context
    user_id = 10016
    headers = get_auth_headers(user_id, settings.BOT_TOKEN)

    async with session_factory() as session:
        await get_or_create_user(session, telegram_id=user_id)
        task = Task(
            user_id=user_id,
            title="Toggle Me",
            target_date=date(2026, 11, 20),
            priority=TaskPriority.medium,
            status=TaskStatus.todo,
            reminder_sent_1h=False,
            reminder_sent_10m=False,
        )
        session.add(task)
        await session.commit()
        await session.refresh(task)
        task_id = task.id

    # First toggle: todo -> done
    r1 = client.patch(f"/api/tasks/{task_id}/toggle", headers=headers)
    assert r1.status_code == 200
    assert r1.json()["status"] == "done"

    # Second toggle: done -> todo
    r2 = client.patch(f"/api/tasks/{task_id}/toggle", headers=headers)
    assert r2.status_code == 200
    assert r2.json()["status"] == "todo"


@pytest.mark.asyncio
async def test_patch_task_toggle_not_found_and_tenant_isolation(api_context):
    """Verifies REQ-TSK-02, REQ-NFR-02: PATCH /api/tasks/{task_id}/toggle raises HTTP 404 for non-existent or other user's task ID."""
    client, session_factory, settings = api_context
    owner_id = 10017
    attacker_id = 20017

    async with session_factory() as session:
        await get_or_create_user(session, telegram_id=owner_id)
        await get_or_create_user(session, telegram_id=attacker_id)
        task = Task(
            user_id=owner_id,
            title="Owner Task",
            target_date=date(2026, 11, 20),
            priority=TaskPriority.medium,
            status=TaskStatus.todo,
            reminder_sent_1h=False,
            reminder_sent_10m=False,
        )
        session.add(task)
        await session.commit()
        await session.refresh(task)
        task_id = task.id

    attacker_headers = get_auth_headers(attacker_id, settings.BOT_TOKEN)

    # Foreign task toggle
    r_foreign = client.patch(f"/api/tasks/{task_id}/toggle", headers=attacker_headers)
    assert r_foreign.status_code == 404
    assert r_foreign.json()["detail"] == "Task not found"

    # Non-existent task toggle
    r_nonexistent = client.patch("/api/tasks/999999/toggle", headers=attacker_headers)
    assert r_nonexistent.status_code == 404
    assert r_nonexistent.json()["detail"] == "Task not found"

    # Verify status unchanged in DB
    async with session_factory() as session:
        stmt = select(Task).where(Task.id == task_id)
        result = await session.execute(stmt)
        assert result.scalar_one().status == TaskStatus.todo


@pytest.mark.asyncio
async def test_delete_task_by_id_success(api_context):
    """Verifies REQ-API-02: DELETE /api/tasks/{task_id} removes task, returns HTTP 204 No Content, and subsequent GET returns 404."""
    client, session_factory, settings = api_context
    user_id = 10018
    headers = get_auth_headers(user_id, settings.BOT_TOKEN)

    async with session_factory() as session:
        await get_or_create_user(session, telegram_id=user_id)
        task = Task(
            user_id=user_id,
            title="Delete Me",
            target_date=date(2026, 11, 20),
            priority=TaskPriority.low,
            status=TaskStatus.todo,
            reminder_sent_1h=False,
            reminder_sent_10m=False,
        )
        session.add(task)
        await session.commit()
        await session.refresh(task)
        task_id = task.id

    # DELETE
    response = client.delete(f"/api/tasks/{task_id}", headers=headers)
    assert response.status_code == 204
    assert response.content == b""

    # Subsequent GET returns 404
    get_res = client.get(f"/api/tasks/{task_id}", headers=headers)
    assert get_res.status_code == 404

    # Subsequent DELETE returns 404
    del_res = client.delete(f"/api/tasks/{task_id}", headers=headers)
    assert del_res.status_code == 404


@pytest.mark.asyncio
async def test_delete_task_by_id_tenant_isolation(api_context):
    """Verifies REQ-NFR-02: DELETE /api/tasks/{task_id} for foreign task returns HTTP 404 and does not delete record."""
    client, session_factory, settings = api_context
    owner_id = 10019
    attacker_id = 20019

    async with session_factory() as session:
        await get_or_create_user(session, telegram_id=owner_id)
        await get_or_create_user(session, telegram_id=attacker_id)
        task = Task(
            user_id=owner_id,
            title="Owner Undeletable Task",
            target_date=date(2026, 11, 20),
            priority=TaskPriority.medium,
            status=TaskStatus.todo,
            reminder_sent_1h=False,
            reminder_sent_10m=False,
        )
        session.add(task)
        await session.commit()
        await session.refresh(task)
        task_id = task.id

    attacker_headers = get_auth_headers(attacker_id, settings.BOT_TOKEN)
    response = client.delete(f"/api/tasks/{task_id}", headers=attacker_headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "Task not found"

    # Verify task still exists in DB
    async with session_factory() as session:
        stmt = select(Task).where(Task.id == task_id)
        result = await session.execute(stmt)
        assert result.scalar_one_or_none() is not None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method,endpoint,payload",
    [
        ("GET", "/api/tasks", None),
        ("POST", "/api/tasks", {"title": "Test", "target_date": "2026-11-20"}),
        ("GET", "/api/tasks/1", None),
        ("PATCH", "/api/tasks/1", {"title": "New"}),
        ("PATCH", "/api/tasks/1/toggle", None),
        ("DELETE", "/api/tasks/1", None),
    ],
)
async def test_task_endpoints_require_authentication(api_context, method, endpoint, payload):
    """Verifies REQ-API-01: All task endpoints return HTTP 401 Unauthorized when credentials are missing or invalid."""
    client, _, settings = api_context

    # 1. Missing credentials entirely
    res_no_auth = client.request(method, endpoint, json=payload)
    assert res_no_auth.status_code == 401

    # 2. Tampered signature / invalid token
    tampered_init_data = create_test_init_data(
        user_data={"id": 12345},
        bot_token="wrong_bot_token",
    )
    res_bad_sig = client.request(
        method,
        endpoint,
        json=payload,
        headers={"Authorization": f"tma {tampered_init_data}"},
    )
    assert res_bad_sig.status_code == 401

    # 3. Expired auth_date (> 86400s)
    expired_init_data = create_test_init_data(
        user_data={"id": 12345},
        bot_token=settings.BOT_TOKEN,
        auth_date=int(time.time()) - 90000,
    )
    res_expired = client.request(
        method,
        endpoint,
        json=payload,
        headers={"Authorization": f"tma {expired_init_data}"},
    )
    assert res_expired.status_code == 401
