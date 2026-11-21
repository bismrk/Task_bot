"""FastAPI application factory and route registration."""

from pathlib import Path
from typing import Final

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.exceptions import HTTPException
from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

from src.api.auth import get_current_user
from src.api.deps import get_db_session
from src.api.routes import settings_router, tasks_router
from src.core.config import Settings, get_settings
from src.core.database import async_session_maker
from src.models.user import User
from src.schemas.user import TimezoneUpdate, UserRead
from src.services.user_service import update_user_timezone

DEFAULT_FRONTEND_DIST: Final[Path] = (
    Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
)


class SPAStaticFiles(StaticFiles):
    """Static file handler with SPA fallback for client-side routing."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        """Serve requested static file, or fallback to index.html for non-API client routes."""
        cleaned_path = path.lstrip("/")
        try:
            response = await super().get_response(path, scope)
            if response.status_code == 404 and not cleaned_path.startswith("api"):
                return await super().get_response("index.html", scope)
            return response
        except HTTPException as exc:
            if exc.status_code == 404 and not cleaned_path.startswith("api"):
                return await super().get_response("index.html", scope)
            raise


def create_app(
    settings: Settings | None = None,
    sessionmaker: async_sessionmaker[AsyncSession] | None = None,
    frontend_dist: Path | str | None = None,
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
    app.include_router(settings_router)

    @app.get("/health")
    async def health_check() -> dict[str, str]:
        """Public health check endpoint."""
        return {"status": "ok"}

    @app.get("/api/me", response_model=UserRead)
    async def get_me(current_user: User = Depends(get_current_user)) -> User:
        """Return the profile of the authenticated Telegram user."""
        return current_user

    @app.patch("/api/me/timezone", response_model=UserRead, tags=["settings"])
    async def update_me_timezone(
        payload: TimezoneUpdate,
        current_user: User = Depends(get_current_user),
        session: AsyncSession = Depends(get_db_session),
    ) -> User:
        """Update the timezone of the authenticated Telegram user (alias)."""
        updated_user = await update_user_timezone(
            session=session,
            telegram_id=current_user.telegram_id,
            timezone=payload.timezone,
        )
        return updated_user

    dist_path = (
        Path(frontend_dist)
        if frontend_dist is not None
        else DEFAULT_FRONTEND_DIST
    )
    if dist_path.is_dir():
        app.mount("/", SPAStaticFiles(directory=dist_path, html=True), name="frontend")

    return app


__all__ = ["DEFAULT_FRONTEND_DIST", "SPAStaticFiles", "create_app"]
