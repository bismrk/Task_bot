"""Settings and user preferences API routes."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import get_current_user
from src.api.deps import get_db_session
from src.models.user import User
from src.schemas.user import TimezoneUpdate, UserRead
from src.services.user_service import update_user_timezone

router = APIRouter(prefix="/api/settings", tags=["settings"])
settings_router = router


@router.patch("/timezone", response_model=UserRead)
async def update_timezone(
    payload: TimezoneUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> User:
    """Update timezone preference for the authenticated Telegram user."""
    updated_user = await update_user_timezone(
        session=session,
        telegram_id=current_user.telegram_id,
        timezone=payload.timezone,
    )
    return updated_user


__all__ = ["router", "settings_router", "update_timezone"]
