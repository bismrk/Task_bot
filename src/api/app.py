"""FastAPI application factory and route registration."""

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.api.auth import get_current_user
from src.api.routes import tasks_router
from src.core.config import Settings, get_settings
from src.core.database import async_session_maker
from src.models.user import User
from src.schemas.user import UserRead


def create_app(
    settings: Settings | None = None,
    sessionmaker: async_sessionmaker[AsyncSession] | None = None,
) -> FastAPI:
    """Create and configure a FastAPI application instance."""
    resolved_settings = settings if settings is not None else get_settings()
    resolved_sessionmaker = (
        sessionmaker if sessionmaker is not None else async_session_maker
    )

    app = FastAPI(
        title="Telegram Task Tracker Bot API",
        debug=resolved_settings.DEBUG,
    )

    app.state.settings = resolved_settings
    app.state.sessionmaker = resolved_sessionmaker

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(tasks_router)

    @app.get("/health")
    async def health_check() -> dict[str, str]:
        """Public health check endpoint."""
        return {"status": "ok"}

    @app.get("/api/me", response_model=UserRead)
    async def get_me(current_user: User = Depends(get_current_user)) -> User:
        """Return the profile of the authenticated Telegram user."""
        return current_user

    return app


__all__ = ["create_app"]
