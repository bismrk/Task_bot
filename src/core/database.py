"""Asynchronous SQLAlchemy database engine and session configuration."""

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy import event, text
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker as _async_sessionmaker,
    create_async_engine,
)

from src.models.base import Base

DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///tasks.db")


def configure_sqlite_pragmas(target_engine: AsyncEngine | Engine) -> None:
    """Register PRAGMA connection event listener on the given SQLite engine.

    Executes:
    - PRAGMA foreign_keys=ON (enforces referential integrity)
    - PRAGMA busy_timeout=5000 (wait up to 5s on locked database)
    - PRAGMA journal_mode=WAL (write-ahead logging for high concurrency)
    """
    sync_engine = getattr(target_engine, "sync_engine", target_engine)

    @event.listens_for(sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()


def create_db_engine(url: str | None = None, **kwargs) -> AsyncEngine:
    """Create an AsyncEngine configured for SQLite with PRAGMAs registered."""
    db_url = url or DATABASE_URL
    eng = create_async_engine(db_url, **kwargs)
    configure_sqlite_pragmas(eng)
    return eng


engine: AsyncEngine = create_db_engine(DATABASE_URL)

async_session_maker: _async_sessionmaker[AsyncSession] = _async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession,
)
# Aliases for compatibility
async_session_factory = async_session_maker
AsyncSessionFactory = async_session_maker
async_sessionmaker = async_session_maker


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide an AsyncSession transaction context manager for database operations."""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db(engine: AsyncEngine | None = None) -> None:
    """Create all database tables in metadata and run idempotent SQLite column migrations."""
    target_engine = engine if engine is not None else globals()["engine"]
    async with target_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        result = await conn.execute(text("PRAGMA table_info(users)"))
        existing_columns = {row[1] for row in result.fetchall()}

        if "reminder_interval_hours" not in existing_columns:
            await conn.execute(
                text(
                    "ALTER TABLE users ADD COLUMN reminder_interval_hours INTEGER DEFAULT 4"
                )
            )
        if "last_periodic_reminder_at" not in existing_columns:
            await conn.execute(
                text(
                    "ALTER TABLE users ADD COLUMN last_periodic_reminder_at DATETIME"
                )
            )
        if "last_evening_summary_date" not in existing_columns:
            await conn.execute(
                text(
                    "ALTER TABLE users ADD COLUMN last_evening_summary_date DATE"
                )
            )
