"""API routes package."""

from src.api.routes.settings import router as settings_router, settings_router as _settings_router
from src.api.routes.tasks import router as tasks_router

__all__ = ["settings_router", "tasks_router"]
