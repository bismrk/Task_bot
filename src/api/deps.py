"""Database session dependencies for FastAPI."""

from collections.abc import AsyncGenerator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import async_session_maker


async def get_db_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """Provide an asynchronous database session.

    Retrieves sessionmaker from request.app.state.sessionmaker (or defaults to
    src.core.database.async_session_maker), yields an AsyncSession, commits on
    success, rolls back on exception, and closes the session upon exit.
    """
    sessionmaker = (
        getattr(request.app.state, "sessionmaker", None) or async_session_maker
    )
    async with sessionmaker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


__all__ = ["get_db_session"]
