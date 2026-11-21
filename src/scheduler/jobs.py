"""Timezone-aware background scheduler jobs and per-user triggers."""

from datetime import datetime
import logging
from zoneinfo import ZoneInfo

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.bot.handlers.rollover import send_midnight_rollover_dialogue
from src.bot.keyboards.start import get_start_keyboard
from src.models.task import TaskPriority, TaskStatus
from src.models.user import User
from src.services.task_service import (
    ensure_recurring_tasks_for_date,
    get_tasks_for_date,
)
from src.services.user_service import get_user_local_time

logger = logging.getLogger(__name__)


async def process_user_midnight_rollover(
    bot: Bot,
    session: AsyncSession,
    user: User,
    now_dt: datetime | None = None,
) -> bool:
    """Process midnight rollover review dialogue for a single user (REQ-SCH-01).

    Computes user local time and triggers review if local time is 00:00.
    Ensures idempotency via user.last_midnight_review_date (REQ-NFR-03).

    Args:
        bot: aiogram Bot instance.
        session: Active SQLAlchemy async session.
        user: User record.
        now_dt: Optional reference datetime for simulation/testing.

    Returns:
        True if the review dialogue was triggered, False otherwise.
    """
    local_time = get_user_local_time(user, now_dt)

    # Check if local time is in 00:00 window
    if not (local_time.hour == 0 and local_time.minute == 0):
        return False

    # Idempotency check (REQ-SCH-01, REQ-NFR-03)
    if user.last_midnight_review_date == local_time.date():
        return False

    # Trigger rollover dialogue (REQ-SCH-01)
    await send_midnight_rollover_dialogue(
        bot=bot,
        session=session,
        user=user,
        reference_date=local_time.date(),
    )

    # Update idempotency tracking and commit transaction
    user.last_midnight_review_date = local_time.date()
    await session.commit()
    return True


async def process_user_morning_push(
    bot: Bot,
    session: AsyncSession,
    user: User,
    webapp_url: str | None = None,
    now_dt: datetime | None = None,
) -> bool:
    """Process 09:00 morning digest push for a single user (REQ-SCH-02).

    Computes user local time, ensures recurring tasks exist for today (REQ-TMA-02),
    retrieves tasks for today, formats the morning digest or friendly message,
    and sends the push notification with [🚀 Відкрити план] button.
    Ensures restart-resilient idempotency via user.last_morning_push_date (REQ-NFR-03).

    Args:
        bot: aiogram Bot instance.
        session: Active SQLAlchemy async session.
        user: User record.
        webapp_url: Optional base URL for Telegram Mini App.
        now_dt: Optional reference datetime for simulation/testing.

    Returns:
        True if the morning push was triggered, False otherwise.
    """
    local_time = get_user_local_time(user, now_dt)

    # Check if local time is in 09:00 window
    if not (local_time.hour == 9 and local_time.minute == 0):
        return False

    # Idempotency check (REQ-SCH-02, REQ-NFR-03)
    if user.last_morning_push_date == local_time.date():
        return False

    today = local_time.date()

    # 1. Populate recurring tasks for today before digest creation (REQ-TMA-02)
    await ensure_recurring_tasks_for_date(
        session=session,
        user_id=user.telegram_id,
        target_date=today,
    )

    # 2. Query tasks for today
    tasks = await get_tasks_for_date(
        session=session,
        user_id=user.telegram_id,
        target_date=today,
    )
    todo_tasks = [t for t in tasks if t.status == TaskStatus.todo]

    # 3. Prepare keyboard with [🚀 Відкрити план] button (REQ-SCH-02)
    keyboard = get_start_keyboard(webapp_url=webapp_url)

    # 4. Format message complying with _docs/design-system.md
    if todo_tasks:
        formatted_date = today.strftime("%d.%m.%Y")
        lines = [
            f"📋 <b>План на сьогодні ({formatted_date}):</b>\n",
            f"У вас {len(todo_tasks)} запланованих завдань на сьогодні:",
        ]
        user_tz = ZoneInfo(user.timezone)
        for task in todo_tasks:
            meta_parts: list[str] = []

            # Priority badge
            if task.priority == TaskPriority.high:
                meta_parts.append("⚠️ Високий")
            elif task.priority == TaskPriority.low:
                meta_parts.append("💤 Низький")
            else:
                meta_parts.append("⚡ Середній")

            # Category tag
            if task.tag:
                clean_tag = task.tag.lstrip("#")
                meta_parts.append(f"🏷️ #{clean_tag}")

            # Formatted deadline
            if task.deadline_at:
                deadline_local = (
                    task.deadline_at.astimezone(user_tz)
                    if task.deadline_at.tzinfo
                    else task.deadline_at
                )
                meta_parts.append(f"🕒 до {deadline_local.strftime('%H:%M')}")

            meta_str = " | ".join(meta_parts)
            lines.append(f"• {task.title} — {meta_str}")

        text = "\n".join(lines)
    else:
        text = (
            "☀️ <b>Доброго ранку!</b>\n\n"
            "На сьогодні у вас немає запланованих завдань.\n"
            "Відпочиньте або надиктуйте нові плани на день 🚀"
        )

    await bot.send_message(
        chat_id=user.telegram_id,
        text=text,
        reply_markup=keyboard,
        parse_mode="HTML",
    )

    # Update idempotency tracking and commit transaction
    user.last_morning_push_date = today
    await session.commit()
    return True


async def run_timezone_checks(
    bot: Bot,
    sessionmaker: async_sessionmaker[AsyncSession],
    webapp_url: str | None = None,
    reference_time: datetime | None = None,
) -> dict[str, int]:
    """Run timezone-aware background checks across all registered users.

    Opens an async database session using sessionmaker(), queries all registered users,
    and iterates over each user with per-user exception isolation (REQ-NFR-02).
    Handles TelegramForbiddenError (blocked bot) by marking the trigger date to avoid
    repeated retries in the same minute and continuing cleanly.
    Rolls back on unexpected exceptions and records error counts.

    Args:
        bot: aiogram Bot instance.
        sessionmaker: SQLAlchemy async sessionmaker factory.
        webapp_url: Optional base URL for Telegram Mini App.
        reference_time: Optional reference datetime for simulation/testing.

    Returns:
        dict[str, int]: {"midnight_triggered": int, "morning_triggered": int, "errors": int}
    """
    stats = {
        "midnight_triggered": 0,
        "morning_triggered": 0,
        "errors": 0,
    }

    async with sessionmaker() as session:
        stmt = select(User)
        result = await session.execute(stmt)
        users = list(result.scalars().all())
        user_ids = [u.telegram_id for u in users]

        for uid in user_ids:
            user = await session.get(User, uid)
            if user is None:
                continue

            try:
                midnight_triggered = await process_user_midnight_rollover(
                    bot=bot,
                    session=session,
                    user=user,
                    now_dt=reference_time,
                )
                if midnight_triggered:
                    stats["midnight_triggered"] += 1

                morning_triggered = await process_user_morning_push(
                    bot=bot,
                    session=session,
                    user=user,
                    webapp_url=webapp_url,
                    now_dt=reference_time,
                )
                if morning_triggered:
                    stats["morning_triggered"] += 1

            except TelegramForbiddenError as e:
                logger.warning("User %s has blocked the bot: %s", user.telegram_id, e)
                try:
                    local_time = get_user_local_time(user, reference_time)
                    if local_time.hour == 0 and local_time.minute == 0:
                        user.last_midnight_review_date = local_time.date()
                    elif local_time.hour == 9 and local_time.minute == 0:
                        user.last_morning_push_date = local_time.date()
                    await session.commit()
                except Exception:
                    await session.rollback()
                    session.expunge_all()
            except TelegramAPIError as e:
                err_msg = str(e).lower()
                if "blocked" in err_msg or "forbidden" in err_msg or "deactivated" in err_msg:
                    logger.warning(
                        "User %s has blocked or deactivated the bot: %s",
                        user.telegram_id,
                        e,
                    )
                    try:
                        local_time = get_user_local_time(user, reference_time)
                        if local_time.hour == 0 and local_time.minute == 0:
                            user.last_midnight_review_date = local_time.date()
                        elif local_time.hour == 9 and local_time.minute == 0:
                            user.last_morning_push_date = local_time.date()
                        await session.commit()
                    except Exception:
                        await session.rollback()
                        session.expunge_all()
                else:
                    logger.exception(
                        "Telegram API error processing timezone checks for user %s: %s",
                        user.telegram_id,
                        e,
                    )
                    await session.rollback()
                    session.expunge_all()
                    stats["errors"] += 1
            except Exception:
                logger.exception(
                    "Unexpected error processing timezone checks for user %s",
                    user.telegram_id,
                )
                await session.rollback()
                session.expunge_all()
                stats["errors"] += 1

    return stats
