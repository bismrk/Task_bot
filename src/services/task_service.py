"""Task management CRUD service and task rollover operations."""

from datetime import date, datetime
import re

from sqlalchemy import case, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.task import Task, TaskPriority, TaskStatus
from src.schemas.task import ExtractedTask, TaskCreate, TaskUpdate


async def create_task(
    session: AsyncSession,
    user_id: int,
    data: TaskCreate | ExtractedTask,
) -> Task:
    """Persist a new task for user with default status todo and un-sent reminders.

    Args:
        session: Active SQLAlchemy async session.
        user_id: Telegram user ID owning the task.
        data: Task creation data from user or AI extraction.

    Returns:
        The newly created and committed Task record.
    """
    recurrence = getattr(data, "recurrence", None)
    task = Task(
        user_id=user_id,
        title=data.title,
        target_date=data.target_date,
        deadline_at=data.deadline_at,
        priority=data.priority,
        tag=data.tag,
        recurrence=recurrence,
        status=TaskStatus.todo,
        reminder_sent_1h=False,
        reminder_sent_10m=False,
    )
    session.add(task)
    await session.commit()
    await session.refresh(task)
    return task


async def create_tasks_batch(
    session: AsyncSession,
    user_id: int,
    tasks: list[TaskCreate | ExtractedTask],
) -> list[Task]:
    """Create and persist multiple tasks in a single database transaction.

    Args:
        session: Active SQLAlchemy async session.
        user_id: Telegram user ID owning the tasks.
        tasks: List of task creation schemas.

    Returns:
        List of newly created and committed Task records.
    """
    if not tasks:
        return []

    created_tasks: list[Task] = []
    for item in tasks:
        recurrence = getattr(item, "recurrence", None)
        task = Task(
            user_id=user_id,
            title=item.title,
            target_date=item.target_date,
            deadline_at=item.deadline_at,
            priority=item.priority,
            tag=item.tag,
            recurrence=recurrence,
            status=TaskStatus.todo,
            reminder_sent_1h=False,
            reminder_sent_10m=False,
        )
        created_tasks.append(task)

    session.add_all(created_tasks)
    await session.commit()
    for task in created_tasks:
        await session.refresh(task)
    return created_tasks


async def get_task(
    session: AsyncSession,
    task_id: int,
    user_id: int,
) -> Task | None:
    """Retrieve a task database record by task_id and user_id.

    Args:
        session: Active SQLAlchemy async session.
        task_id: ID of the task to retrieve.
        user_id: Telegram user ID for tenant isolation.

    Returns:
        The Task record if found and owned by user_id, or None.
    """
    stmt = select(Task).where(Task.id == task_id, Task.user_id == user_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_tasks_for_date(
    session: AsyncSession,
    user_id: int,
    target_date: date,
) -> list[Task]:
    """Retrieve tasks for a specific date, ordered by status, priority, and creation time.

    Todo tasks are returned first (high -> medium -> low priority), followed by done tasks,
    then ordered by created_at / id.

    Args:
        session: Active SQLAlchemy async session.
        user_id: Telegram user ID for tenant isolation.
        target_date: Date to filter tasks by.

    Returns:
        List of matching Task records.
    """
    status_order = case(
        (Task.status == TaskStatus.todo, 0),
        (Task.status == TaskStatus.done, 1),
        else_=2,
    )
    priority_order = case(
        (Task.priority == TaskPriority.high, 0),
        (Task.priority == TaskPriority.medium, 1),
        (Task.priority == TaskPriority.low, 2),
        else_=3,
    )
    stmt = (
        select(Task)
        .where(Task.user_id == user_id, Task.target_date == target_date)
        .order_by(status_order, priority_order, Task.created_at.asc(), Task.id.asc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def update_task(
    session: AsyncSession,
    task_id: int,
    user_id: int,
    data: TaskUpdate,
) -> Task:
    """Update only provided fields of a task, enforcing tenant isolation.

    If deadline_at is provided, reminder sent flags are reset to False.

    Args:
        session: Active SQLAlchemy async session.
        task_id: ID of the task to update.
        user_id: Telegram user ID for tenant isolation.
        data: TaskUpdate schema containing fields to update.

    Returns:
        The updated and committed Task record.

    Raises:
        ValueError: If the task does not exist or belongs to another user.
    """
    task = await get_task(session, task_id, user_id)
    if task is None:
        raise ValueError("Task not found or access denied")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(task, field, value)

    if "deadline_at" in update_data:
        task.reminder_sent_1h = False
        task.reminder_sent_10m = False

    await session.commit()
    await session.refresh(task)
    return task


async def toggle_task_status(
    session: AsyncSession,
    task_id: int,
    user_id: int,
    new_status: TaskStatus,
) -> Task:
    """Update task status, enforcing tenant isolation.

    Args:
        session: Active SQLAlchemy async session.
        task_id: ID of the task.
        user_id: Telegram user ID for tenant isolation.
        new_status: New TaskStatus to set.

    Returns:
        The updated Task record.

    Raises:
        ValueError: If the task does not exist or belongs to another user.
    """
    task = await get_task(session, task_id, user_id)
    if task is None:
        raise ValueError("Task not found or access denied")

    task.status = new_status
    await session.commit()
    await session.refresh(task)
    return task


async def delete_task(
    session: AsyncSession,
    task_id: int,
    user_id: int,
) -> bool:
    """Delete a task owned by user_id, enforcing tenant isolation.

    Args:
        session: Active SQLAlchemy async session.
        task_id: ID of the task to delete.
        user_id: Telegram user ID for tenant isolation.

    Returns:
        True if the task was found and deleted, False otherwise.
    """
    task = await get_task(session, task_id, user_id)
    if task is None:
        return False

    await session.delete(task)
    await session.commit()
    return True


async def get_overdue_tasks(
    session: AsyncSession,
    user_id: int,
    before_date: date,
) -> list[Task]:
    """Retrieve uncompleted tasks with target_date < before_date for user.

    Ordered by target_date ASC, priority (high -> medium -> low), and creation time.

    Args:
        session: Active SQLAlchemy async session.
        user_id: Telegram user ID for tenant isolation.
        before_date: Date threshold to find overdue tasks before.

    Returns:
        List of overdue Task records.
    """
    priority_order = case(
        (Task.priority == TaskPriority.high, 0),
        (Task.priority == TaskPriority.medium, 1),
        (Task.priority == TaskPriority.low, 2),
        else_=3,
    )
    stmt = (
        select(Task)
        .where(
            Task.user_id == user_id,
            Task.status == TaskStatus.todo,
            Task.target_date < before_date,
        )
        .order_by(Task.target_date.asc(), priority_order, Task.created_at.asc(), Task.id.asc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def rollover_task(
    session: AsyncSession,
    task_id: int,
    user_id: int,
    new_date: date,
) -> Task:
    """Update task target_date to new_date, enforcing tenant isolation.

    Args:
        session: Active SQLAlchemy async session.
        task_id: ID of the task to rollover.
        user_id: Telegram user ID for tenant isolation.
        new_date: New target date.

    Returns:
        The updated Task record.

    Raises:
        ValueError: If the task does not exist or belongs to another user.
    """
    task = await get_task(session, task_id, user_id)
    if task is None:
        raise ValueError("Task not found or access denied")

    task.target_date = new_date
    await session.commit()
    await session.refresh(task)
    return task


async def batch_rollover_tasks(
    session: AsyncSession,
    task_ids: list[int],
    user_id: int,
    new_date: date,
) -> list[Task]:
    """Update target_date for all tasks in task_ids owned by user_id.

    Args:
        session: Active SQLAlchemy async session.
        task_ids: List of task IDs to rollover.
        user_id: Telegram user ID for tenant isolation.
        new_date: New target date.

    Returns:
        List of updated Task records owned by user_id.
    """
    if not task_ids:
        return []

    stmt = select(Task).where(Task.id.in_(task_ids), Task.user_id == user_id).order_by(Task.id.asc())
    result = await session.execute(stmt)
    tasks = list(result.scalars().all())
    if not tasks:
        return []

    for task in tasks:
        task.target_date = new_date

    await session.commit()
    for task in tasks:
        await session.refresh(task)
    return tasks


def is_recurrence_active_on_date(recurrence: str | None, target_date: date) -> bool:
    """Check whether a recurrence rule applies to the specified target_date.

    Supports:
        - 'daily': every calendar day.
        - 'weekdays:[...]': specific weekday indices (0=Mon, ..., 6=Sun), e.g. [0,1,2,3,4].
        - 'weekdays': Monday through Friday (0..4).
    """
    if not recurrence:
        return False
    rec = recurrence.strip().lower()
    if rec == "daily":
        return True
    if rec.startswith("weekdays:"):
        match = re.search(r"weekdays:\[([0-9,\s]*)\]", rec)
        if match:
            day_strs = match.group(1).split(",")
            days = [int(s.strip()) for s in day_strs if s.strip().isdigit()]
            return target_date.weekday() in days
        days = [int(s.strip()) for s in rec.replace("weekdays:", "").split(",") if s.strip().isdigit()]
        if days:
            return target_date.weekday() in days
    if rec == "weekdays":
        return target_date.weekday() in (0, 1, 2, 3, 4)
    return False


async def ensure_recurring_tasks_for_date(
    session: AsyncSession,
    user_id: int,
    target_date: date,
) -> list[Task]:
    """Ensure recurring task instances exist for target_date (REQ-TMA-02).

    Queries recurring tasks owned by user_id with target_date < target_date.
    For each recurring task matching the target_date rule, checks if an instance
    with the same title and recurrence already exists for target_date under user_id.
    If no instance exists, creates a new task instance for target_date with status=todo,
    copying title, priority, tag, recurrence, and relative deadline_at (adjusted to target_date),
    with reminder_sent_1h=False and reminder_sent_10m=False.

    Args:
        session: Active SQLAlchemy async session.
        user_id: Telegram user ID for tenant isolation.
        target_date: Target date to populate recurring tasks for.

    Returns:
        List of newly created Task instances for target_date.
    """
    # 1. Fetch existing tasks for target_date to avoid duplicates
    existing_stmt = select(Task).where(
        Task.user_id == user_id,
        Task.target_date == target_date,
    )
    existing_result = await session.execute(existing_stmt)
    existing_tasks = list(existing_result.scalars().all())
    existing_rules = {(t.title, t.recurrence) for t in existing_tasks if t.recurrence is not None}

    # 2. Query recurring tasks where target_date < target_date
    query_stmt = (
        select(Task)
        .where(
            Task.user_id == user_id,
            Task.recurrence.isnot(None),
            Task.target_date < target_date,
        )
        .order_by(Task.target_date.asc(), Task.id.asc())
    )
    result = await session.execute(query_stmt)
    past_recurring_tasks = list(result.scalars().all())

    newly_created: list[Task] = []
    for past_task in past_recurring_tasks:
        if not past_task.recurrence:
            continue

        if not is_recurrence_active_on_date(past_task.recurrence, target_date):
            continue

        rule_key = (past_task.title, past_task.recurrence)
        if rule_key in existing_rules:
            continue

        # Adjust deadline_at relative to target_date if present
        new_deadline_at = None
        if past_task.deadline_at is not None:
            day_offset = past_task.deadline_at.date() - past_task.target_date
            new_deadline_date = target_date + day_offset
            new_deadline_at = datetime.combine(new_deadline_date, past_task.deadline_at.timetz())

        new_task = Task(
            user_id=user_id,
            title=past_task.title,
            target_date=target_date,
            deadline_at=new_deadline_at,
            priority=past_task.priority,
            tag=past_task.tag,
            recurrence=past_task.recurrence,
            status=TaskStatus.todo,
            reminder_sent_1h=False,
            reminder_sent_10m=False,
        )
        newly_created.append(new_task)
        existing_rules.add(rule_key)

    if newly_created:
        session.add_all(newly_created)
        await session.commit()
        for t in newly_created:
            await session.refresh(t)

    return newly_created

