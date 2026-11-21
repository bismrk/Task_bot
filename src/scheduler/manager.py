"""APScheduler background service manager for timezone-aware jobs."""

import logging

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.scheduler.jobs import run_deadline_checks, run_timezone_checks

logger = logging.getLogger(__name__)


def create_scheduler() -> AsyncIOScheduler:
    """Create and return an AsyncIOScheduler configured with UTC timezone."""
    return AsyncIOScheduler(timezone="UTC")


def setup_scheduler(
    scheduler: AsyncIOScheduler,
    bot: Bot,
    sessionmaker: async_sessionmaker[AsyncSession],
    webapp_url: str | None = None,
) -> AsyncIOScheduler:
    """Register timezone checks periodic job on the scheduler (REQ-SCH-01, REQ-SCH-02).

    Configures a minute-by-minute cron job (at second=0) with id 'timezone_checks',
    name 'Timezone-Aware Background Checks', max_instances=1, and coalesce=True.
    """
    scheduler.add_job(
        run_timezone_checks,
        trigger=CronTrigger(second=0, timezone="UTC"),
        args=[bot, sessionmaker, webapp_url],
        id="timezone_checks",
        name="Timezone-Aware Background Checks",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        run_deadline_checks,
        trigger=CronTrigger(second=30, timezone="UTC"),
        args=[bot, sessionmaker],
        id="deadline_checks",
        name="Deadline Proximity Checks",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    return scheduler


def start_scheduler(scheduler: AsyncIOScheduler) -> None:
    """Start the scheduler if it is not already running."""
    if not scheduler.running:
        scheduler.start()
        logger.info("AsyncIOScheduler started successfully.")


def stop_scheduler(scheduler: AsyncIOScheduler, wait: bool = False) -> None:
    """Stop the scheduler cleanly if it is running."""
    if scheduler.running:
        scheduler.shutdown(wait=wait)
        logger.info("AsyncIOScheduler shut down cleanly.")
