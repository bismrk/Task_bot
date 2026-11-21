"""Task management API routes for Telegram Mini App."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import get_current_user
from src.api.deps import get_db_session
from src.models.task import TaskStatus
from src.models.user import User
from src.schemas.task import (
    AnalyticsResponse,
    CalendarDaySummary,
    TaskCreate,
    TaskRead,
    TaskUpdate,
)
from src.services.task_service import (
    create_task,
    delete_task,
    ensure_recurring_tasks_for_date,
    get_calendar_summary,
    get_productivity_analytics,
    get_task,
    get_tasks_for_date,
    toggle_task_status,
    update_task,
)
from src.services.user_service import get_user_local_time

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.get("", response_model=list[TaskRead])
async def list_tasks(
    date: date | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[TaskRead]:
    """Retrieve tasks for a specific date or today in user local time."""
    target_date = date if date is not None else get_user_local_time(current_user).date()
    await ensure_recurring_tasks_for_date(
        session=session,
        user_id=current_user.telegram_id,
        target_date=target_date,
    )
    tasks = await get_tasks_for_date(
        session=session,
        user_id=current_user.telegram_id,
        target_date=target_date,
    )
    return tasks


@router.post("", status_code=status.HTTP_201_CREATED, response_model=TaskRead)
async def create_new_task(
    payload: TaskCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> TaskRead:
    """Create a new task owned by the authenticated user."""
    task = await create_task(
        session=session,
        user_id=current_user.telegram_id,
        data=payload,
    )
    return task


@router.get("/calendar-summary", response_model=list[CalendarDaySummary])
async def get_monthly_calendar_summary(
    year: int = Query(..., ge=1900, le=2100),
    month: int = Query(..., ge=1, le=12),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[CalendarDaySummary]:
    """Retrieve monthly calendar summary of task counts and statuses for the user."""
    summaries = await get_calendar_summary(
        session=session,
        user_id=current_user.telegram_id,
        year=year,
        month=month,
    )
    return summaries


@router.get("/analytics", response_model=AnalyticsResponse)
async def get_analytics(
    days: int = Query(default=14, ge=7, le=90),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> AnalyticsResponse:
    """Retrieve productivity analytics, streaks, and trends for the user."""
    analytics = await get_productivity_analytics(
        session=session,
        user_id=current_user.telegram_id,
        days=days,
    )
    return analytics


@router.get("/{task_id}", response_model=TaskRead)
async def get_task_by_id(
    task_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> TaskRead:
    """Retrieve a single task by ID enforcing tenant isolation."""
    task = await get_task(
        session=session,
        task_id=task_id,
        user_id=current_user.telegram_id,
    )
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )
    return task


@router.patch("/{task_id}", response_model=TaskRead)
async def update_task_by_id(
    task_id: int,
    payload: TaskUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> TaskRead:
    """Partially update a task enforcing tenant isolation."""
    try:
        updated_task = await update_task(
            session=session,
            task_id=task_id,
            user_id=current_user.telegram_id,
            data=payload,
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )
    return updated_task


@router.patch("/{task_id}/toggle", response_model=TaskRead)
async def toggle_task_by_id(
    task_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> TaskRead:
    """Toggle task status between todo and done."""
    task = await get_task(
        session=session,
        task_id=task_id,
        user_id=current_user.telegram_id,
    )
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    target_status = (
        TaskStatus.done if task.status == TaskStatus.todo else TaskStatus.todo
    )
    updated_task = await toggle_task_status(
        session=session,
        task_id=task_id,
        user_id=current_user.telegram_id,
        new_status=target_status,
    )
    return updated_task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task_by_id(
    task_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    """Delete a task enforcing tenant isolation."""
    deleted = await delete_task(
        session=session,
        task_id=task_id,
        user_id=current_user.telegram_id,
    )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = ["router"]
