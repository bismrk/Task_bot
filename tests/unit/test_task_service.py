"""Automated unit tests for task management CRUD service, rollover operations, and task schemas."""

from datetime import date, datetime, timedelta, timezone
import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.task import Task, TaskPriority, TaskStatus
from src.models.user import User
from src.schemas.task import (
    ExtractedTask,
    TaskCreate,
    TaskRead,
    TaskUpdate,
)
from src.services.task_service import (
    batch_rollover_tasks,
    create_task,
    create_tasks_batch,
    delete_task,
    get_overdue_tasks,
    get_task,
    get_tasks_for_date,
    rollover_task,
    toggle_task_status,
    update_task,
)


async def create_test_user(session: AsyncSession, telegram_id: int = 123456789) -> User:
    """Helper to persist a test user record for foreign key constraints."""
    user = User(telegram_id=telegram_id, timezone="Europe/Kyiv")
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


# ============================================================================
# create_task Tests
# ============================================================================


@pytest.mark.asyncio
async def test_create_task_with_task_create_persists_all_fields(db_session: AsyncSession) -> None:
    """Verifies REQ-TSK-01: create_task with TaskCreate persists fields, default status todo, and reminder flags."""
    user = await create_test_user(db_session, telegram_id=101)
    target = date(2026, 11, 20)
    deadline = datetime(2026, 11, 20, 18, 0, tzinfo=timezone.utc)

    task_data = TaskCreate(
        title="  Купити молоко та хліб  ",
        target_date=target,
        deadline_at=deadline,
        priority=TaskPriority.high,
        tag="#shopping",
        recurrence="daily",
    )

    task = await create_task(db_session, user_id=user.telegram_id, data=task_data)

    assert task.id is not None
    assert task.user_id == user.telegram_id
    assert task.title == "Купити молоко та хліб"
    assert task.target_date == target
    assert task.deadline_at is not None
    assert (
        task.deadline_at == deadline
        or task.deadline_at.replace(tzinfo=timezone.utc) == deadline
    )
    assert task.priority == TaskPriority.high
    assert task.tag == "shopping"
    assert task.recurrence == "daily"
    assert task.status == TaskStatus.todo
    assert task.reminder_sent_1h is False
    assert task.reminder_sent_10m is False
    assert task.created_at is not None

    # Check persistence in database
    stmt = select(Task).where(Task.id == task.id)
    persisted = (await db_session.execute(stmt)).scalar_one_or_none()
    assert persisted is not None
    assert persisted.title == "Купити молоко та хліб"
    assert persisted.status == TaskStatus.todo


@pytest.mark.asyncio
async def test_create_task_with_extracted_task_maps_fields_and_sets_recurrence_none(
    db_session: AsyncSession,
) -> None:
    """Verifies REQ-TSK-01: create_task with ExtractedTask maps attributes and sets recurrence=None."""
    user = await create_test_user(db_session, telegram_id=102)
    target = date(2026, 11, 21)
    deadline = datetime(2026, 11, 21, 14, 0, tzinfo=timezone.utc)

    extracted = ExtractedTask(
        title="Зробити звіт",
        target_date=target,
        deadline_at=deadline,
        priority=TaskPriority.low,
        tag="робота",
    )

    task = await create_task(db_session, user_id=user.telegram_id, data=extracted)

    assert task.id is not None
    assert task.user_id == user.telegram_id
    assert task.title == "Зробити звіт"
    assert task.target_date == target
    assert task.deadline_at is not None
    assert (
        task.deadline_at == deadline
        or task.deadline_at.replace(tzinfo=timezone.utc) == deadline
    )
    assert task.priority == TaskPriority.low
    assert task.tag == "робота"
    assert task.recurrence is None
    assert task.status == TaskStatus.todo
    assert task.reminder_sent_1h is False
    assert task.reminder_sent_10m is False


# ============================================================================
# create_tasks_batch Tests
# ============================================================================


@pytest.mark.asyncio
async def test_create_tasks_batch_creates_multiple_tasks(db_session: AsyncSession) -> None:
    """Verifies REQ-TSK-01: create_tasks_batch persists multiple tasks in single transaction."""
    user = await create_test_user(db_session, telegram_id=103)
    target = date(2026, 11, 22)

    task_1 = TaskCreate(title="Task One", target_date=target, priority=TaskPriority.high)
    task_2 = ExtractedTask(title="Task Two", target_date=target, priority=TaskPriority.medium)

    created_tasks = await create_tasks_batch(db_session, user_id=user.telegram_id, tasks=[task_1, task_2])

    assert len(created_tasks) == 2
    assert created_tasks[0].title == "Task One"
    assert created_tasks[0].priority == TaskPriority.high
    assert created_tasks[1].title == "Task Two"
    assert created_tasks[1].priority == TaskPriority.medium
    assert created_tasks[1].recurrence is None

    stmt = select(Task).where(Task.user_id == user.telegram_id)
    persisted = list((await db_session.execute(stmt)).scalars().all())
    assert len(persisted) == 2


@pytest.mark.asyncio
async def test_create_tasks_batch_empty_list_returns_empty_list(db_session: AsyncSession) -> None:
    """Verifies REQ-TSK-01: create_tasks_batch with empty list returns [] without queries."""
    user = await create_test_user(db_session, telegram_id=104)
    result = await create_tasks_batch(db_session, user_id=user.telegram_id, tasks=[])
    assert result == []


# ============================================================================
# get_task Tests
# ============================================================================


@pytest.mark.asyncio
async def test_get_task_returns_task_for_owner(db_session: AsyncSession) -> None:
    """Verifies REQ-TSK-01 & REQ-NFR-02: get_task returns task if owned by user_id."""
    user = await create_test_user(db_session, telegram_id=105)
    created = await create_task(
        db_session,
        user_id=user.telegram_id,
        data=TaskCreate(title="My Task", target_date=date(2026, 11, 20)),
    )

    retrieved = await get_task(db_session, task_id=created.id, user_id=user.telegram_id)
    assert retrieved is not None
    assert retrieved.id == created.id
    assert retrieved.title == "My Task"


@pytest.mark.asyncio
async def test_get_task_enforces_tenant_isolation(db_session: AsyncSession) -> None:
    """Verifies REQ-NFR-02: get_task returns None when task belongs to another user."""
    user1 = await create_test_user(db_session, telegram_id=106)
    user2 = await create_test_user(db_session, telegram_id=107)

    task_user1 = await create_task(
        db_session,
        user_id=user1.telegram_id,
        data=TaskCreate(title="User 1 Task", target_date=date(2026, 11, 20)),
    )

    retrieved_by_user2 = await get_task(db_session, task_id=task_user1.id, user_id=user2.telegram_id)
    assert retrieved_by_user2 is None


@pytest.mark.asyncio
async def test_get_task_returns_none_for_non_existent_id(db_session: AsyncSession) -> None:
    """Verifies REQ-NFR-02: get_task returns None for non-existent task_id."""
    user = await create_test_user(db_session, telegram_id=108)
    retrieved = await get_task(db_session, task_id=999999, user_id=user.telegram_id)
    assert retrieved is None


# ============================================================================
# get_tasks_for_date Tests
# ============================================================================


@pytest.mark.asyncio
async def test_get_tasks_for_date_ordering_and_filtering(db_session: AsyncSession) -> None:
    """Verifies REQ-TSK-01 & REQ-NFR-02: get_tasks_for_date filters by date/user and orders todo by priority then done."""
    user1 = await create_test_user(db_session, telegram_id=109)
    user2 = await create_test_user(db_session, telegram_id=110)
    target = date(2026, 11, 20)
    other_date = date(2026, 11, 21)

    # User 1 tasks on target date
    t_todo_med = await create_task(
        db_session,
        user_id=user1.telegram_id,
        data=TaskCreate(title="Todo Medium", target_date=target, priority=TaskPriority.medium),
    )
    t_done_high = await create_task(
        db_session,
        user_id=user1.telegram_id,
        data=TaskCreate(title="Done High", target_date=target, priority=TaskPriority.high),
    )
    await toggle_task_status(db_session, t_done_high.id, user1.telegram_id, TaskStatus.done)

    t_todo_high = await create_task(
        db_session,
        user_id=user1.telegram_id,
        data=TaskCreate(title="Todo High", target_date=target, priority=TaskPriority.high),
    )
    t_todo_low = await create_task(
        db_session,
        user_id=user1.telegram_id,
        data=TaskCreate(title="Todo Low", target_date=target, priority=TaskPriority.low),
    )

    # User 1 task on different date
    await create_task(
        db_session,
        user_id=user1.telegram_id,
        data=TaskCreate(title="Other Date", target_date=other_date, priority=TaskPriority.high),
    )

    # User 2 task on target date
    await create_task(
        db_session,
        user_id=user2.telegram_id,
        data=TaskCreate(title="User 2 Target", target_date=target, priority=TaskPriority.high),
    )

    # Query User 1 tasks for target date
    tasks = await get_tasks_for_date(db_session, user_id=user1.telegram_id, target_date=target)

    # Should only return User 1 tasks on target date
    assert len(tasks) == 4
    # Expected order:
    # 1. Todo High (t_todo_high)
    # 2. Todo Medium (t_todo_med)
    # 3. Todo Low (t_todo_low)
    # 4. Done High (t_done_high)
    assert tasks[0].id == t_todo_high.id
    assert tasks[1].id == t_todo_med.id
    assert tasks[2].id == t_todo_low.id
    assert tasks[3].id == t_done_high.id


@pytest.mark.asyncio
async def test_get_tasks_for_date_returns_empty_when_no_match(db_session: AsyncSession) -> None:
    """Verifies REQ-TSK-01: get_tasks_for_date returns empty list when no tasks match."""
    user = await create_test_user(db_session, telegram_id=111)
    tasks = await get_tasks_for_date(db_session, user_id=user.telegram_id, target_date=date(2026, 12, 1))
    assert tasks == []


# ============================================================================
# update_task Tests
# ============================================================================


@pytest.mark.asyncio
async def test_update_task_updates_fields(db_session: AsyncSession) -> None:
    """Verifies REQ-TSK-01: update_task updates only provided fields and commits."""
    user = await create_test_user(db_session, telegram_id=112)
    original_target = date(2026, 11, 20)
    task = await create_task(
        db_session,
        user_id=user.telegram_id,
        data=TaskCreate(title="Original Title", target_date=original_target, priority=TaskPriority.low),
    )

    updated = await update_task(
        db_session,
        task_id=task.id,
        user_id=user.telegram_id,
        data=TaskUpdate(title="Updated Title", priority=TaskPriority.high),
    )

    assert updated.id == task.id
    assert updated.title == "Updated Title"
    assert updated.priority == TaskPriority.high
    assert updated.target_date == original_target


@pytest.mark.asyncio
async def test_update_task_resets_reminder_flags_when_deadline_updated(db_session: AsyncSession) -> None:
    """Verifies REQ-TSK-01: update_task with deadline_at resets reminder_sent_1h and reminder_sent_10m."""
    user = await create_test_user(db_session, telegram_id=113)
    target = date(2026, 11, 20)
    task = await create_task(
        db_session,
        user_id=user.telegram_id,
        data=TaskCreate(title="Task With Reminder", target_date=target),
    )

    # Manually simulate reminders already sent
    task.reminder_sent_1h = True
    task.reminder_sent_10m = True
    await db_session.commit()

    # Update deadline_at
    new_deadline = datetime(2026, 11, 20, 20, 0, tzinfo=timezone.utc)
    updated = await update_task(
        db_session,
        task_id=task.id,
        user_id=user.telegram_id,
        data=TaskUpdate(deadline_at=new_deadline),
    )

    assert updated.deadline_at is not None
    assert (
        updated.deadline_at == new_deadline
        or updated.deadline_at.replace(tzinfo=timezone.utc) == new_deadline
    )
    assert updated.reminder_sent_1h is False
    assert updated.reminder_sent_10m is False


@pytest.mark.asyncio
async def test_update_task_preserves_reminder_flags_when_deadline_not_updated(
    db_session: AsyncSession,
) -> None:
    """Verifies REQ-TSK-01: update_task without deadline_at leaves reminder flags unchanged."""
    user = await create_test_user(db_session, telegram_id=114)
    target = date(2026, 11, 20)
    task = await create_task(
        db_session,
        user_id=user.telegram_id,
        data=TaskCreate(title="Task Reminder Preserved", target_date=target),
    )

    task.reminder_sent_1h = True
    task.reminder_sent_10m = True
    await db_session.commit()

    updated = await update_task(
        db_session,
        task_id=task.id,
        user_id=user.telegram_id,
        data=TaskUpdate(title="Just New Title"),
    )

    assert updated.title == "Just New Title"
    assert updated.reminder_sent_1h is True
    assert updated.reminder_sent_10m is True


@pytest.mark.asyncio
async def test_update_task_foreign_user_raises_value_error_and_preserves_record(
    db_session: AsyncSession,
) -> None:
    """Verifies REQ-NFR-02: update_task for another user raises ValueError and does not modify database."""
    user1 = await create_test_user(db_session, telegram_id=115)
    user2 = await create_test_user(db_session, telegram_id=116)

    task = await create_task(
        db_session,
        user_id=user1.telegram_id,
        data=TaskCreate(title="User 1 Protected", target_date=date(2026, 11, 20)),
    )

    with pytest.raises(ValueError, match="Task not found or access denied"):
        await update_task(
            db_session,
            task_id=task.id,
            user_id=user2.telegram_id,
            data=TaskUpdate(title="Malicious Update"),
        )

    # Check record is unmodified
    persisted = await get_task(db_session, task_id=task.id, user_id=user1.telegram_id)
    assert persisted is not None
    assert persisted.title == "User 1 Protected"


@pytest.mark.asyncio
async def test_update_task_non_existent_raises_value_error(db_session: AsyncSession) -> None:
    """Verifies REQ-TSK-01: update_task for non-existent task raises ValueError."""
    user = await create_test_user(db_session, telegram_id=117)
    with pytest.raises(ValueError, match="Task not found or access denied"):
        await update_task(
            db_session,
            task_id=999999,
            user_id=user.telegram_id,
            data=TaskUpdate(title="Non-existent"),
        )


# ============================================================================
# toggle_task_status Tests
# ============================================================================


@pytest.mark.asyncio
async def test_toggle_task_status_transitions(db_session: AsyncSession) -> None:
    """Verifies REQ-TSK-02: toggle_task_status transitions status to done, canceled, and back to todo."""
    user = await create_test_user(db_session, telegram_id=118)
    task = await create_task(
        db_session,
        user_id=user.telegram_id,
        data=TaskCreate(title="Toggle Me", target_date=date(2026, 11, 20)),
    )
    assert task.status == TaskStatus.todo

    done_task = await toggle_task_status(db_session, task.id, user.telegram_id, TaskStatus.done)
    assert done_task.status == TaskStatus.done

    canceled_task = await toggle_task_status(db_session, task.id, user.telegram_id, TaskStatus.canceled)
    assert canceled_task.status == TaskStatus.canceled

    todo_task = await toggle_task_status(db_session, task.id, user.telegram_id, TaskStatus.todo)
    assert todo_task.status == TaskStatus.todo


@pytest.mark.asyncio
async def test_toggle_task_status_foreign_user_raises_value_error(db_session: AsyncSession) -> None:
    """Verifies REQ-TSK-02 & REQ-NFR-02: toggle_task_status for another user raises ValueError and leaves status unchanged."""
    user1 = await create_test_user(db_session, telegram_id=119)
    user2 = await create_test_user(db_session, telegram_id=120)

    task = await create_task(
        db_session,
        user_id=user1.telegram_id,
        data=TaskCreate(title="User 1 Task", target_date=date(2026, 11, 20)),
    )

    with pytest.raises(ValueError, match="Task not found or access denied"):
        await toggle_task_status(db_session, task.id, user2.telegram_id, TaskStatus.done)

    # Check status is still todo
    persisted = await get_task(db_session, task.id, user1.telegram_id)
    assert persisted is not None
    assert persisted.status == TaskStatus.todo


@pytest.mark.asyncio
async def test_toggle_task_status_non_existent_raises_value_error(db_session: AsyncSession) -> None:
    """Verifies REQ-TSK-02: toggle_task_status for non-existent task raises ValueError."""
    user = await create_test_user(db_session, telegram_id=121)
    with pytest.raises(ValueError, match="Task not found or access denied"):
        await toggle_task_status(db_session, 999999, user.telegram_id, TaskStatus.done)


# ============================================================================
# delete_task Tests
# ============================================================================


@pytest.mark.asyncio
async def test_delete_task_deletes_record_and_returns_true(db_session: AsyncSession) -> None:
    """Verifies REQ-TSK-01 & REQ-NFR-02: delete_task removes record owned by user and returns True."""
    user = await create_test_user(db_session, telegram_id=122)
    task = await create_task(
        db_session,
        user_id=user.telegram_id,
        data=TaskCreate(title="To Delete", target_date=date(2026, 11, 20)),
    )

    success = await delete_task(db_session, task.id, user.telegram_id)
    assert success is True

    # Check it is gone
    retrieved = await get_task(db_session, task.id, user.telegram_id)
    assert retrieved is None


@pytest.mark.asyncio
async def test_delete_task_foreign_user_returns_false_and_preserves_record(
    db_session: AsyncSession,
) -> None:
    """Verifies REQ-NFR-02: delete_task for another user returns False and preserves database record."""
    user1 = await create_test_user(db_session, telegram_id=123)
    user2 = await create_test_user(db_session, telegram_id=124)

    task = await create_task(
        db_session,
        user_id=user1.telegram_id,
        data=TaskCreate(title="User 1 Safe", target_date=date(2026, 11, 20)),
    )

    success = await delete_task(db_session, task.id, user2.telegram_id)
    assert success is False

    # Check it is still present in User 1's tasks
    persisted = await get_task(db_session, task.id, user1.telegram_id)
    assert persisted is not None


@pytest.mark.asyncio
async def test_delete_task_non_existent_returns_false(db_session: AsyncSession) -> None:
    """Verifies REQ-TSK-01: delete_task for non-existent task returns False."""
    user = await create_test_user(db_session, telegram_id=125)
    success = await delete_task(db_session, 999999, user.telegram_id)
    assert success is False


# ============================================================================
# get_overdue_tasks Tests
# ============================================================================


@pytest.mark.asyncio
async def test_get_overdue_tasks_returns_only_uncompleted_and_orders_correctly(
    db_session: AsyncSession,
) -> None:
    """Verifies REQ-SCH-01 & REQ-NFR-02: get_overdue_tasks returns uncompleted tasks with target_date < before_date."""
    user1 = await create_test_user(db_session, telegram_id=126)
    user2 = await create_test_user(db_session, telegram_id=127)
    today = date(2026, 11, 20)
    day_minus_2 = today - timedelta(days=2)
    day_minus_1 = today - timedelta(days=1)

    # User 1 overdue tasks (todo)
    overdue_1 = await create_task(
        db_session,
        user_id=user1.telegram_id,
        data=TaskCreate(title="Older Overdue High", target_date=day_minus_2, priority=TaskPriority.high),
    )
    overdue_2 = await create_task(
        db_session,
        user_id=user1.telegram_id,
        data=TaskCreate(title="Older Overdue Low", target_date=day_minus_2, priority=TaskPriority.low),
    )
    overdue_3 = await create_task(
        db_session,
        user_id=user1.telegram_id,
        data=TaskCreate(title="Recent Overdue High", target_date=day_minus_1, priority=TaskPriority.high),
    )

    # User 1 completed task on past date (must NOT be returned)
    completed_past = await create_task(
        db_session,
        user_id=user1.telegram_id,
        data=TaskCreate(title="Completed Past", target_date=day_minus_2),
    )
    await toggle_task_status(db_session, completed_past.id, user1.telegram_id, TaskStatus.done)

    # User 1 today task (must NOT be returned since target_date == today, not < today)
    await create_task(
        db_session,
        user_id=user1.telegram_id,
        data=TaskCreate(title="Today Task", target_date=today),
    )

    # User 2 overdue task (must NOT be returned due to tenant isolation)
    await create_task(
        db_session,
        user_id=user2.telegram_id,
        data=TaskCreate(title="User 2 Overdue", target_date=day_minus_2),
    )

    # Fetch overdue tasks for User 1 before today
    overdue_list = await get_overdue_tasks(db_session, user_id=user1.telegram_id, before_date=today)

    assert len(overdue_list) == 3
    # Ordered by target_date ASC, then priority (high -> medium -> low), then created_at
    assert overdue_list[0].id == overdue_1.id
    assert overdue_list[1].id == overdue_2.id
    assert overdue_list[2].id == overdue_3.id


@pytest.mark.asyncio
async def test_get_overdue_tasks_returns_empty_when_none(db_session: AsyncSession) -> None:
    """Verifies REQ-SCH-01: get_overdue_tasks returns [] when no overdue tasks exist."""
    user = await create_test_user(db_session, telegram_id=128)
    overdue = await get_overdue_tasks(db_session, user_id=user.telegram_id, before_date=date(2026, 11, 20))
    assert overdue == []


# ============================================================================
# rollover_task Tests
# ============================================================================


@pytest.mark.asyncio
async def test_rollover_task_updates_target_date(db_session: AsyncSession) -> None:
    """Verifies REQ-SCH-01: rollover_task updates target_date to new date and commits."""
    user = await create_test_user(db_session, telegram_id=129)
    old_date = date(2026, 11, 19)
    new_date = date(2026, 11, 20)

    task = await create_task(
        db_session,
        user_id=user.telegram_id,
        data=TaskCreate(title="Rollover Me", target_date=old_date),
    )

    rolled = await rollover_task(db_session, task.id, user.telegram_id, new_date)
    assert rolled.id == task.id
    assert rolled.target_date == new_date

    # Verify directly from database
    persisted = await get_task(db_session, task.id, user.telegram_id)
    assert persisted is not None
    assert persisted.target_date == new_date


@pytest.mark.asyncio
async def test_rollover_task_foreign_user_raises_value_error(db_session: AsyncSession) -> None:
    """Verifies REQ-SCH-01 & REQ-NFR-02: rollover_task for another user raises ValueError."""
    user1 = await create_test_user(db_session, telegram_id=130)
    user2 = await create_test_user(db_session, telegram_id=131)

    task = await create_task(
        db_session,
        user_id=user1.telegram_id,
        data=TaskCreate(title="User 1 Task", target_date=date(2026, 11, 19)),
    )

    with pytest.raises(ValueError, match="Task not found or access denied"):
        await rollover_task(db_session, task.id, user2.telegram_id, date(2026, 11, 20))

    persisted = await get_task(db_session, task.id, user1.telegram_id)
    assert persisted is not None
    assert persisted.target_date == date(2026, 11, 19)


@pytest.mark.asyncio
async def test_rollover_task_non_existent_raises_value_error(db_session: AsyncSession) -> None:
    """Verifies REQ-SCH-01: rollover_task for non-existent task raises ValueError."""
    user = await create_test_user(db_session, telegram_id=132)
    with pytest.raises(ValueError, match="Task not found or access denied"):
        await rollover_task(db_session, 999999, user.telegram_id, date(2026, 11, 20))


# ============================================================================
# batch_rollover_tasks Tests
# ============================================================================


@pytest.mark.asyncio
async def test_batch_rollover_tasks_updates_all_and_ignores_foreign(db_session: AsyncSession) -> None:
    """Verifies REQ-SCH-01 & REQ-NFR-02: batch_rollover_tasks updates owner tasks and ignores foreign tasks."""
    user1 = await create_test_user(db_session, telegram_id=133)
    user2 = await create_test_user(db_session, telegram_id=134)
    old_date = date(2026, 11, 19)
    new_date = date(2026, 11, 20)

    t1 = await create_task(
        db_session,
        user_id=user1.telegram_id,
        data=TaskCreate(title="User 1 T1", target_date=old_date),
    )
    t2 = await create_task(
        db_session,
        user_id=user1.telegram_id,
        data=TaskCreate(title="User 1 T2", target_date=old_date),
    )
    t_foreign = await create_task(
        db_session,
        user_id=user2.telegram_id,
        data=TaskCreate(title="User 2 T3", target_date=old_date),
    )

    # Roll over t1, t2, foreign task, and a non-existent task ID
    updated_tasks = await batch_rollover_tasks(
        db_session,
        task_ids=[t1.id, t2.id, t_foreign.id, 999999],
        user_id=user1.telegram_id,
        new_date=new_date,
    )

    # Only User 1's tasks should be returned and updated
    assert len(updated_tasks) == 2
    updated_ids = {t.id for t in updated_tasks}
    assert updated_ids == {t1.id, t2.id}
    for t in updated_tasks:
        assert t.target_date == new_date

    # Foreign task must remain unchanged
    persisted_foreign = await get_task(db_session, t_foreign.id, user2.telegram_id)
    assert persisted_foreign is not None
    assert persisted_foreign.target_date == old_date


@pytest.mark.asyncio
async def test_batch_rollover_tasks_empty_list_returns_empty_list(db_session: AsyncSession) -> None:
    """Verifies REQ-SCH-01: batch_rollover_tasks with empty list returns [] without queries."""
    user = await create_test_user(db_session, telegram_id=135)
    result = await batch_rollover_tasks(
        db_session,
        task_ids=[],
        user_id=user.telegram_id,
        new_date=date(2026, 11, 20),
    )
    assert result == []


# ============================================================================
# Pydantic Schemas Tests
# ============================================================================


def test_task_create_schema_validation_and_defaults() -> None:
    """Verifies REQ-TSK-01: TaskCreate validation, defaults, whitespace stripping, and tag normalization."""
    # Defaults
    t = TaskCreate(title="  Clean Desk  ", target_date=date(2026, 11, 20))
    assert t.title == "Clean Desk"
    assert t.priority == TaskPriority.medium
    assert t.tag is None
    assert t.deadline_at is None
    assert t.recurrence is None

    # Tag stripping #
    t_tag = TaskCreate(title="Task", target_date=date(2026, 11, 20), tag="#work  ")
    assert t_tag.tag == "work"

    # Priority string conversion
    t_prio = TaskCreate(title="Task", target_date=date(2026, 11, 20), priority="терміново")  # type: ignore[arg-type]
    assert t_prio.priority == TaskPriority.high

    # Timezone-aware deadline_at is accepted
    tz_aware = datetime(2026, 11, 20, 15, 0, tzinfo=timezone.utc)
    t_deadline = TaskCreate(title="Task", target_date=date(2026, 11, 20), deadline_at=tz_aware)
    assert t_deadline.deadline_at == tz_aware

    # Naive deadline_at raises ValidationError
    with pytest.raises(ValidationError, match="deadline_at must be timezone-aware"):
        TaskCreate(title="Task", target_date=date(2026, 11, 20), deadline_at=datetime(2026, 11, 20, 15, 0))

    # Empty title raises ValidationError
    with pytest.raises(ValidationError):
        TaskCreate(title="   ", target_date=date(2026, 11, 20))


def test_task_update_schema_validation() -> None:
    """Verifies REQ-TSK-01: TaskUpdate supports partial updates, validates title, tag, and deadline_at."""
    # Empty update
    u = TaskUpdate()
    assert u.model_dump(exclude_unset=True) == {}

    # Partial title
    u_title = TaskUpdate(title="  New Title  ")
    assert u_title.title == "New Title"

    # Tag normalization
    u_tag = TaskUpdate(tag="#urgent")
    assert u_tag.tag == "urgent"

    # Status conversion
    u_status = TaskUpdate(status="done")  # type: ignore[arg-type]
    assert u_status.status == TaskStatus.done

    # Naive deadline_at raises ValidationError
    with pytest.raises(ValidationError, match="deadline_at must be timezone-aware"):
        TaskUpdate(deadline_at=datetime(2026, 11, 20, 10, 0))

    # Empty string title raises ValidationError
    with pytest.raises(ValidationError):
        TaskUpdate(title="  ")


def test_task_read_schema_from_attributes() -> None:
    """Verifies REQ-TSK-01: TaskRead validates, serializes, and supports from_attributes from ORM Task."""
    now = datetime.now(timezone.utc)
    orm_task = Task(
        id=42,
        user_id=123456789,
        title="Test Task",
        status=TaskStatus.todo,
        priority=TaskPriority.high,
        tag="study",
        target_date=date(2026, 11, 20),
        deadline_at=now,
        recurrence="weekly",
        reminder_sent_1h=False,
        reminder_sent_10m=False,
        created_at=now,
    )

    read_model = TaskRead.model_validate(orm_task)
    assert read_model.id == 42
    assert read_model.user_id == 123456789
    assert read_model.title == "Test Task"
    assert read_model.status == TaskStatus.todo
    assert read_model.priority == TaskPriority.high
    assert read_model.tag == "study"
    assert read_model.target_date == date(2026, 11, 20)
    assert read_model.deadline_at == now
    assert read_model.recurrence == "weekly"
    assert read_model.reminder_sent_1h is False
    assert read_model.reminder_sent_10m is False
    assert read_model.created_at == now
