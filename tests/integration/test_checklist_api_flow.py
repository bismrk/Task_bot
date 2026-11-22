"""Integration tests for Mini App Today Checklist API flow and recurring tasks lifecycle.

Verifies end-to-end task operations, optimistic UI contract endpoints, recurring task
generation on date progression, and strict tenant isolation.
"""

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
async def test_checklist_complete_api_lifecycle(api_context):
    """Verifies REQ-TMA-01, REQ-API-02, REQ-TSK-01, REQ-TSK-02: Full checklist CRUD and toggle lifecycle.

    Tests:
    1. Initial empty checklist retrieval returns empty list [].
    2. Task creation with priority, tag, deadline, and recurrence.
    3. Status toggle from todo to done.
    4. Status toggle from done back to todo.
    5. Partial task update.
    6. Task deletion and verification of empty checklist.
    """
    client, session_factory, settings = api_context
    user_id = 99901
    headers = get_auth_headers(user_id, settings.BOT_TOKEN)
    target_date = "2026-11-21"

    # Step 1: Initial empty list retrieval
    response = client.get(f"/api/tasks?date={target_date}", headers=headers)
    assert response.status_code == 200
    assert response.json() == []

    # Step 2: Task creation with priority, tag, deadline, and recurrence
    deadline_iso = "2026-11-21T18:00:00Z"
    create_payload = {
        "title": "Prepare Mini App presentation",
        "target_date": target_date,
        "priority": "high",
        "tag": "work",
        "deadline_at": deadline_iso,
        "recurrence": "daily",
    }
    create_resp = client.post("/api/tasks", json=create_payload, headers=headers)
    assert create_resp.status_code == 201
    task_data = create_resp.json()
    task_id = task_data["id"]
    assert task_data["title"] == "Prepare Mini App presentation"
    assert task_data["status"] == "todo"
    assert task_data["priority"] == "high"
    assert task_data["tag"] == "work"
    assert task_data["recurrence"] == "daily"
    assert task_data["target_date"] == target_date
    assert task_data["user_id"] == user_id

    # Step 3: Status toggle to 'done' (REQ-TMA-01, REQ-TSK-02)
    toggle_resp1 = client.patch(f"/api/tasks/{task_id}/toggle", headers=headers)
    assert toggle_resp1.status_code == 200
    assert toggle_resp1.json()["status"] == "done"

    # Verify state via GET
    get_resp1 = client.get(f"/api/tasks?date={target_date}", headers=headers)
    assert get_resp1.status_code == 200
    tasks1 = get_resp1.json()
    assert len(tasks1) == 1
    assert tasks1[0]["status"] == "done"

    # Step 4: Status toggle back to 'todo'
    toggle_resp2 = client.patch(f"/api/tasks/{task_id}/toggle", headers=headers)
    assert toggle_resp2.status_code == 200
    assert toggle_resp2.json()["status"] == "todo"

    # Step 5: Task update (e.g. changing title and priority)
    update_payload = {"title": "Updated Presentation Title", "priority": "medium"}
    update_resp = client.patch(f"/api/tasks/{task_id}", json=update_payload, headers=headers)
    assert update_resp.status_code == 200
    assert update_resp.json()["title"] == "Updated Presentation Title"
    assert update_resp.json()["priority"] == "medium"

    # Step 6: Task deletion (REQ-API-02)
    delete_resp = client.delete(f"/api/tasks/{task_id}", headers=headers)
    assert delete_resp.status_code == 204

    # Verify checklist is empty again
    final_get_resp = client.get(f"/api/tasks?date={target_date}", headers=headers)
    assert final_get_resp.status_code == 200
    assert final_get_resp.json() == []


@pytest.mark.asyncio
async def test_recurring_task_auto_generation_on_new_date(api_context):
    """Verifies REQ-TMA-02, REQ-API-02: Automatic generation of recurring tasks on new day.

    Tests:
    1. User has a 'daily' recurring task and a 'weekdays:[0,1,2,3,4]' recurring task on Monday (2026-11-23).
    2. Calling GET /api/tasks?date=2026-11-24 (Tuesday) auto-creates both tasks with status=todo.
    3. Repeating GET /api/tasks?date=2026-11-24 is idempotent (does not duplicate tasks).
    4. Calling GET /api/tasks?date=2026-11-28 (Saturday) auto-creates only the 'daily' task, skipping the weekdays task.
    """
    client, session_factory, settings = api_context
    user_id = 99902
    headers = get_auth_headers(user_id, settings.BOT_TOKEN)

    # Monday: 2026-11-23 (weekday 0)
    monday_str = "2026-11-23"
    tuesday_str = "2026-11-24"  # weekday 1
    saturday_str = "2026-11-28"  # weekday 5

    # 1. Create recurring daily task with deadline
    daily_payload = {
        "title": "Daily Morning Workout",
        "target_date": monday_str,
        "priority": "high",
        "tag": "fitness",
        "deadline_at": "2026-11-23T07:30:00Z",
        "recurrence": "daily",
    }
    resp1 = client.post("/api/tasks", json=daily_payload, headers=headers)
    assert resp1.status_code == 201

    # Create weekdays task
    weekdays_payload = {
        "title": "Daily Standup Meeting",
        "target_date": monday_str,
        "priority": "medium",
        "tag": "work",
        "recurrence": "weekdays:[0,1,2,3,4]",
    }
    resp2 = client.post("/api/tasks", json=weekdays_payload, headers=headers)
    assert resp2.status_code == 201

    # Mark Monday's workout as done
    workout_monday_id = resp1.json()["id"]
    client.patch(f"/api/tasks/{workout_monday_id}/toggle", headers=headers)

    # 2. Advance to Tuesday (2026-11-24, weekday 1)
    tuesday_resp = client.get(f"/api/tasks?date={tuesday_str}", headers=headers)
    assert tuesday_resp.status_code == 200
    tuesday_tasks = tuesday_resp.json()

    # Both daily and weekdays tasks should be generated on Tuesday
    assert len(tuesday_tasks) == 2
    titles = {t["title"] for t in tuesday_tasks}
    assert "Daily Morning Workout" in titles
    assert "Daily Standup Meeting" in titles

    # Verify both are new instances with status=todo on tuesday_str
    for t in tuesday_tasks:
        assert t["target_date"] == tuesday_str
        assert t["status"] == "todo"
        if t["title"] == "Daily Morning Workout":
            assert t["priority"] == "high"
            assert t["tag"] == "fitness"
            assert t["recurrence"] == "daily"
            # Deadline should be shifted to Tuesday at 07:30 UTC
            assert "2026-11-24T07:30:00" in t["deadline_at"]
        elif t["title"] == "Daily Standup Meeting":
            assert t["priority"] == "medium"
            assert t["tag"] == "work"
            assert t["recurrence"] == "weekdays:[0,1,2,3,4]"

    # 3. Call Tuesday again - must be idempotent (no duplicates created)
    tuesday_resp2 = client.get(f"/api/tasks?date={tuesday_str}", headers=headers)
    assert tuesday_resp2.status_code == 200
    assert len(tuesday_resp2.json()) == 2

    # 4. Check Saturday (2026-11-28, weekday 5)
    saturday_resp = client.get(f"/api/tasks?date={saturday_str}", headers=headers)
    assert saturday_resp.status_code == 200
    saturday_tasks = saturday_resp.json()

    # Only 'daily' task should be created; 'weekdays' task should be skipped on weekend
    assert len(saturday_tasks) == 1
    assert saturday_tasks[0]["title"] == "Daily Morning Workout"
    assert saturday_tasks[0]["target_date"] == saturday_str
    assert saturday_tasks[0]["status"] == "todo"


@pytest.mark.asyncio
async def test_checklist_tenant_isolation(api_context):
    """Verifies REQ-NFR-02, REQ-API-02, REQ-TSK-02: Tenant isolation across task checklist operations.

    Tests:
    1. User A creates a task.
    2. User B cannot toggle User A's task (returns 404).
    3. User B cannot update User A's task (returns 404).
    4. User B cannot delete User A's task (returns 404).
    5. User A's task remains untouched in the database.
    """
    client, session_factory, settings = api_context
    user_a_id = 99911
    user_b_id = 99922
    headers_a = get_auth_headers(user_a_id, settings.BOT_TOKEN, first_name="Alice")
    headers_b = get_auth_headers(user_b_id, settings.BOT_TOKEN, first_name="Bob")

    # User A creates a task
    create_resp = client.post(
        "/api/tasks",
        json={"title": "Confidential Task A", "target_date": "2026-11-21", "priority": "high"},
        headers=headers_a,
    )
    assert create_resp.status_code == 201
    task_a_id = create_resp.json()["id"]

    # User B attempts to toggle User A's task -> 404
    toggle_resp = client.patch(f"/api/tasks/{task_a_id}/toggle", headers=headers_b)
    assert toggle_resp.status_code == 404
    assert toggle_resp.json()["detail"] == "Task not found"

    # User B attempts to update User A's task -> 404
    update_resp = client.patch(f"/api/tasks/{task_a_id}", json={"title": "Hacked"}, headers=headers_b)
    assert update_resp.status_code == 404
    assert update_resp.json()["detail"] == "Task not found"

    # User B attempts to delete User A's task -> 404
    delete_resp = client.delete(f"/api/tasks/{task_a_id}", headers=headers_b)
    assert delete_resp.status_code == 404
    assert delete_resp.json()["detail"] == "Task not found"

    # Verify User A's task is unmodified
    task_a_resp = client.get(f"/api/tasks/{task_a_id}", headers=headers_a)
    assert task_a_resp.status_code == 200
    data = task_a_resp.json()
    assert data["title"] == "Confidential Task A"
    assert data["status"] == "todo"
    assert data["user_id"] == user_a_id


@pytest.mark.asyncio
async def test_custom_recurrence_api_lifecycle_and_validation(api_context):
    """Verifies Issue #20: Custom recurrence API flow and validation.

    Tests:
    1. Validation rejects malformed/empty recurrence strings with 422.
    2. Valid custom recurrence is normalized on POST /api/tasks.
    3. Matching days auto-spawn recurring tasks via GET /api/tasks?date=...
    4. Non-matching days do not spawn recurring tasks.
    """
    client, session_factory, settings = api_context
    user_id = 99903
    headers = get_auth_headers(user_id, settings.BOT_TOKEN)

    monday_str = "2026-11-23"  # weekday 0
    tuesday_str = "2026-11-24"  # weekday 1 (matching)
    wednesday_str = "2026-11-25"  # weekday 2 (non-matching)
    thursday_str = "2026-11-26"  # weekday 3 (matching)

    # 1. Validation rejection: invalid digits (e.g. 7), empty day list, invalid strings
    for bad_rec in ["weekdays:[7]", "weekdays:[]", "monthly", "invalid"]:
        resp = client.post(
            "/api/tasks",
            json={
                "title": "Invalid Task",
                "target_date": monday_str,
                "recurrence": bad_rec,
            },
            headers=headers,
        )
        assert resp.status_code == 422

    # 2. Valid custom recurrence with normalization on creation
    create_resp = client.post(
        "/api/tasks",
        json={
            "title": "Custom Recurring Meeting",
            "target_date": monday_str,
            "priority": "high",
            "recurrence": "weekdays:[6, 1, 3]",
        },
        headers=headers,
    )
    assert create_resp.status_code == 201
    assert create_resp.json()["recurrence"] == "weekdays:[1,3,6]"

    # 3. GET on Tuesday (weekday 1 - matches [1,3,6]) -> spawns task
    tue_resp = client.get(f"/api/tasks?date={tuesday_str}", headers=headers)
    assert tue_resp.status_code == 200
    tue_tasks = tue_resp.json()
    assert len(tue_tasks) == 1
    assert tue_tasks[0]["title"] == "Custom Recurring Meeting"
    assert tue_tasks[0]["target_date"] == tuesday_str
    assert tue_tasks[0]["recurrence"] == "weekdays:[1,3,6]"
    assert tue_tasks[0]["status"] == "todo"

    # 4. GET on Wednesday (weekday 2 - non-matching) -> returns 0 tasks
    wed_resp = client.get(f"/api/tasks?date={wednesday_str}", headers=headers)
    assert wed_resp.status_code == 200
    assert wed_resp.json() == []

    # 5. GET on Thursday (weekday 3 - matches [1,3,6]) -> spawns task
    thu_resp = client.get(f"/api/tasks?date={thursday_str}", headers=headers)
    assert thu_resp.status_code == 200
    thu_tasks = thu_resp.json()
    assert len(thu_tasks) == 1
    assert thu_tasks[0]["title"] == "Custom Recurring Meeting"
    assert thu_tasks[0]["target_date"] == thursday_str
