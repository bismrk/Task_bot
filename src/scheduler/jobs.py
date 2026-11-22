"""Timezone-aware background scheduler jobs and per-user triggers."""

from datetime import datetime, timedelta, timezone
import html
import logging
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.bot.handlers.rollover import send_midnight_rollover_dialogue
from src.bot.keyboards.deadline import get_deadline_keyboard
from src.bot.keyboards.start import get_start_keyboard
from src.bot.keyboards.tasks import get_evening_summary_keyboard
from src.models.task import Task, TaskPriority, TaskStatus
from src.models.user import User
from src.services.task_service import (
    ensure_recurring_tasks_for_date,
    get_productivity_analytics,
    get_tasks_for_date,
)
from src.services.user_service import get_user_local_time

logger = logging.getLogger(__name__)


def _normalize_utc(dt: datetime | None) -> datetime:
    """Normalize a datetime to timezone-aware UTC (treating None as utcnow and naive as UTC)."""
    if dt is None:
        return datetime.now(timezone.utc)
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _resolve_user_timezone(tz_name: str | None) -> ZoneInfo:
    """Resolve an IANA timezone name with safe fallback to Europe/Kyiv."""
    if tz_name:
        cleaned = tz_name.strip()
        if cleaned:
            try:
                return ZoneInfo(cleaned)
            except (ZoneInfoNotFoundError, KeyError, ValueError):
                logger.warning(
                    "Invalid timezone %r encountered; falling back to Europe/Kyiv",
                    tz_name,
                )
    return ZoneInfo("Europe/Kyiv")


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
    now_utc = _normalize_utc(now_dt)
    local_time = get_user_local_time(user, now_utc)

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

    # Update idempotency tracking and anchor periodic reminders to 09:00
    user.last_morning_push_date = today
    user.last_periodic_reminder_at = now_utc
    await session.commit()
    return True


async def process_user_periodic_reminder(
    bot: Bot,
    session: AsyncSession,
    user: User,
    webapp_url: str | None = None,
    now_dt: datetime | None = None,
) -> bool:
    """Process periodic uncompleted task reminder for a single user.

    Evaluates at the top of the user's local hour within the active window 08:00-22:59,
    skipping 09:00 (owned by process_user_morning_push). Sends an HTML-formatted list
    of uncompleted (`todo`) tasks for today via Telegram bot if at least one exists.

    Args:
        bot: aiogram Bot instance.
        session: Active SQLAlchemy async session.
        user: User record.
        webapp_url: Optional base URL for Telegram Mini App.
        now_dt: Optional reference datetime for simulation/testing.

    Returns:
        True if a periodic reminder was sent, False otherwise.
    """
    interval = user.reminder_interval_hours
    if interval is None or interval <= 0:
        return False

    now_utc = _normalize_utc(now_dt)
    local_time = get_user_local_time(user, now_utc)

    # Only evaluate at the top of the local hour within 08:00-22:59, skipping 09:00 and 22:00
    if local_time.minute != 0:
        return False
    if not (8 <= local_time.hour <= 22):
        return False
    if local_time.hour in (9, 22):
        return False

    # Exact deterministic trigger & idempotency rule
    if user.last_periodic_reminder_at is not None:
        last_sent_utc = _normalize_utc(user.last_periodic_reminder_at)
        if (now_utc - last_sent_utc) < timedelta(minutes=interval * 60 - 1):
            return False
    else:
        if interval <= 13:
            if (local_time.hour - 9) % interval != 0:
                return False
        else:
            if local_time.hour != 21:
                return False

    today = local_time.date()

    # 1. Populate recurring tasks for today before checking uncompleted tasks
    await ensure_recurring_tasks_for_date(
        session=session,
        user_id=user.telegram_id,
        target_date=today,
    )

    # 2. Query today's tasks and filter to uncompleted (todo)
    tasks = await get_tasks_for_date(
        session=session,
        user_id=user.telegram_id,
        target_date=today,
    )
    todo_tasks = [t for t in tasks if t.status == TaskStatus.todo]
    if not todo_tasks:
        return False

    # 3. Format HTML message complying with _docs/design-system.md
    lines = [
        "🔔 <b>Нагадування про завдання на сьогодні:</b>\n",
        f"У вас залишилось {len(todo_tasks)} невиконаних завдань на сьогодні:",
    ]
    user_tz = ZoneInfo(user.timezone)
    for task in todo_tasks:
        meta_parts: list[str] = []

        if task.priority == TaskPriority.high:
            meta_parts.append("⚠️ Високий")
        elif task.priority == TaskPriority.low:
            meta_parts.append("💤 Низький")
        else:
            meta_parts.append("⚡ Середній")

        if task.tag:
            clean_tag = html.escape(task.tag.lstrip("#"))
            meta_parts.append(f"🏷️ #{clean_tag}")

        if task.deadline_at:
            deadline_local = _normalize_utc(task.deadline_at).astimezone(user_tz)
            meta_parts.append(f"🕒 до {deadline_local.strftime('%H:%M')}")

        meta_str = " | ".join(meta_parts)
        escaped_title = html.escape(task.title)
        lines.append(f"• {escaped_title} — {meta_str}")

    text = "\n".join(lines)
    keyboard = get_start_keyboard(webapp_url=webapp_url)

    await bot.send_message(
        chat_id=user.telegram_id,
        text=text,
        reply_markup=keyboard,
        parse_mode="HTML",
    )

    user.last_periodic_reminder_at = now_utc
    await session.commit()
    return True


async def process_user_evening_summary(
    bot: Bot,
    session: AsyncSession,
    user: User,
    webapp_url: str | None = None,
    now_dt: datetime | None = None,
) -> bool:
    """Process 22:00 end-of-day productivity analytics summary for a single user.

    Triggers only when the user's local time is 22:00 (independent of reminder_interval_hours),
    enforces per-day idempotency via user.last_evening_summary_date, computes daily completion
    metrics, 10-segment progress bar, current streak, and top tags, and sends an HTML message
    with [📝 План на завтра] and [🚀 Відкрити план] inline buttons.

    Args:
        bot: aiogram Bot instance.
        session: Active SQLAlchemy async session.
        user: User record.
        webapp_url: Optional base URL for Telegram Mini App.
        now_dt: Optional reference datetime for simulation/testing.

    Returns:
        True if the evening summary was sent, False otherwise.
    """
    now_utc = _normalize_utc(now_dt)
    local_time = get_user_local_time(user, now_utc)

    # Check if local time is in 22:00 window
    if not (local_time.hour == 22 and local_time.minute == 0):
        return False

    today = local_time.date()

    # Idempotency check per local calendar day
    if user.last_evening_summary_date == today:
        return False

    # 1. Query today's tasks and count only non-canceled tasks (done + todo)
    tasks = await get_tasks_for_date(
        session=session,
        user_id=user.telegram_id,
        target_date=today,
    )
    active_tasks = [t for t in tasks if t.status in (TaskStatus.done, TaskStatus.todo)]
    total_today = len(active_tasks)
    done_today = sum(1 for t in active_tasks if t.status == TaskStatus.done)
    remaining_today = sum(1 for t in active_tasks if t.status == TaskStatus.todo)

    # 2. Compute current streak via productivity analytics
    analytics = await get_productivity_analytics(
        session=session,
        user_id=user.telegram_id,
        days=14,
        reference_date=today,
    )
    streak_current = analytics.streak_current

    # 3. Format HTML message adhering to _docs/design-system.md
    formatted_date = today.strftime("%d.%m.%Y")
    if total_today > 0:
        completion_pct = round((done_today / total_today) * 100)
        filled_segments = max(0, min(10, round((done_today / total_today) * 10)))
        progress_bar = "🟩" * filled_segments + "⬜" * (10 - filled_segments)

        lines = [
            f"🌙 <b>Підсумки дня ({formatted_date})</b>\n",
            f"✅ Виконано: <b>{done_today}/{total_today}</b> ({completion_pct}%)",
            progress_bar,
        ]
        if remaining_today > 0:
            lines.append(f"⏳ Залишилось невиконаних: <b>{remaining_today}</b>")
        else:
            lines.append("🎉 <b>Чудова робота! Усі завдання на сьогодні виконано!</b>")

        lines.append(f"🔥 Стрік: {streak_current} дн.")

        # Top 3 tags from today's non-canceled tagged tasks
        tag_counts: dict[str, int] = {}
        for task in active_tasks:
            if task.tag:
                cleaned_tag = task.tag.strip().lstrip("#").strip()
                if cleaned_tag:
                    tag_counts[cleaned_tag] = tag_counts.get(cleaned_tag, 0) + 1
        top_tags = sorted(tag_counts.items(), key=lambda item: (-item[1], item[0]))[:3]
        if top_tags:
            tags_str = ", ".join(
                f"#{html.escape(tag)} ({count})" for tag, count in top_tags
            )
            lines.append(f"🏷️ Теги дня: {tags_str}")

        lines.append(
            "\n📝 <b>Сплануймо завтра?</b> Натисніть «План на завтра» нижче "
            "або надішліть голосове чи текстове повідомлення, щоб спланувати завтра."
        )
        text = "\n".join(lines)
    else:
        lines = [
            f"🌙 <b>Підсумки дня ({formatted_date})</b>\n",
            "Сьогодні не було запланованих завдань.",
        ]
        if streak_current > 0:
            lines.append(f"🔥 Стрік: {streak_current} дн.")
        lines.append(
            "\n📝 <b>Сплануймо завтра?</b> Натисніть «План на завтра» нижче "
            "або надішліть голосове чи текстове повідомлення, щоб спланувати завтра."
        )
        text = "\n".join(lines)

    keyboard = get_evening_summary_keyboard(
        user_id=user.telegram_id,
        webapp_url=webapp_url,
    )

    await bot.send_message(
        chat_id=user.telegram_id,
        text=text,
        reply_markup=keyboard,
        parse_mode="HTML",
    )

    user.last_evening_summary_date = today
    user.last_periodic_reminder_at = now_utc
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
    Handles TelegramForbiddenError (blocked bot) by marking the trigger date/timestamp
    to avoid repeated retries in the same window and continuing cleanly.
    Rolls back on unexpected exceptions and records error counts.

    Args:
        bot: aiogram Bot instance.
        sessionmaker: SQLAlchemy async sessionmaker factory.
        webapp_url: Optional base URL for Telegram Mini App.
        reference_time: Optional reference datetime for simulation/testing.

    Returns:
        dict[str, int]: {
            "midnight_triggered": int,
            "morning_triggered": int,
            "periodic_triggered": int,
            "evening_triggered": int,
            "errors": int,
        }
    """
    stats = {
        "midnight_triggered": 0,
        "morning_triggered": 0,
        "periodic_triggered": 0,
        "evening_triggered": 0,
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

                periodic_triggered = await process_user_periodic_reminder(
                    bot=bot,
                    session=session,
                    user=user,
                    webapp_url=webapp_url,
                    now_dt=reference_time,
                )
                if periodic_triggered:
                    stats["periodic_triggered"] += 1

                evening_triggered = await process_user_evening_summary(
                    bot=bot,
                    session=session,
                    user=user,
                    webapp_url=webapp_url,
                    now_dt=reference_time,
                )
                if evening_triggered:
                    stats["evening_triggered"] += 1

            except TelegramForbiddenError as e:
                logger.warning("User %s has blocked the bot: %s", user.telegram_id, e)
                try:
                    now_utc = _normalize_utc(reference_time)
                    local_time = get_user_local_time(user, now_utc)
                    if local_time.hour == 0 and local_time.minute == 0:
                        user.last_midnight_review_date = local_time.date()
                    elif local_time.hour == 9 and local_time.minute == 0:
                        user.last_morning_push_date = local_time.date()
                        user.last_periodic_reminder_at = now_utc
                    elif local_time.hour == 22 and local_time.minute == 0:
                        user.last_evening_summary_date = local_time.date()
                        user.last_periodic_reminder_at = now_utc
                    elif 8 <= local_time.hour <= 22 and local_time.minute == 0:
                        user.last_periodic_reminder_at = now_utc
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
                        now_utc = _normalize_utc(reference_time)
                        local_time = get_user_local_time(user, now_utc)
                        if local_time.hour == 0 and local_time.minute == 0:
                            user.last_midnight_review_date = local_time.date()
                        elif local_time.hour == 9 and local_time.minute == 0:
                            user.last_morning_push_date = local_time.date()
                            user.last_periodic_reminder_at = now_utc
                        elif local_time.hour == 22 and local_time.minute == 0:
                            user.last_evening_summary_date = local_time.date()
                            user.last_periodic_reminder_at = now_utc
                        elif 8 <= local_time.hour <= 22 and local_time.minute == 0:
                            user.last_periodic_reminder_at = now_utc
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


async def run_deadline_checks(
    bot: Bot,
    sessionmaker: async_sessionmaker[AsyncSession],
    now_dt: datetime | None = None,
) -> dict[str, int]:
    """Monitor upcoming deadlines and dispatch -1h and -10m reminders (REQ-SCH-03).

    Opens an async database session using sessionmaker(), queries all tasks where
    status == TaskStatus.todo and deadline_at is not None.
    Computes delta_sec between deadline_at and now_dt (normalized to UTC).
    Sends notifications with inline action buttons [✅ Виконано] and [⏰ +15 хв].
    Provides per-task exception isolation (REQ-NFR-02) and restart-resilient
    idempotency tracking (REQ-NFR-03).

    Args:
        bot: aiogram Bot instance.
        sessionmaker: SQLAlchemy async sessionmaker factory.
        now_dt: Optional reference datetime for simulation/testing (defaults to UTC now).

    Returns:
        dict[str, int]: {"reminders_1h_sent": count1h, "reminders_10m_sent": count10m, "errors": err_count}
    """
    stats = {
        "reminders_1h_sent": 0,
        "reminders_10m_sent": 0,
        "errors": 0,
    }

    if now_dt is None:
        now_utc = datetime.now(timezone.utc)
    elif now_dt.tzinfo is None:
        now_utc = now_dt.replace(tzinfo=timezone.utc)
    else:
        now_utc = now_dt.astimezone(timezone.utc)

    async with sessionmaker() as session:
        stmt = select(Task.id).where(
            Task.status == TaskStatus.todo,
            Task.deadline_at.isnot(None),
        )
        result = await session.execute(stmt)
        task_ids = list(result.scalars().all())

        for task_id in task_ids:
            task = await session.get(Task, task_id)
            if task is None or task.status != TaskStatus.todo or task.deadline_at is None:
                continue

            try:
                deadline_dt = task.deadline_at
                if deadline_dt.tzinfo is None:
                    deadline_utc = deadline_dt.replace(tzinfo=timezone.utc)
                else:
                    deadline_utc = deadline_dt.astimezone(timezone.utc)

                delta_sec = (deadline_utc - now_utc).total_seconds()

                # Past deadline: ignore
                if delta_sec <= 0:
                    continue

                # 10-minute proximity check (-10m)
                if 0 < delta_sec <= 600:
                    if not task.reminder_sent_10m:
                        user = await session.get(User, task.user_id)
                        user_tz = _resolve_user_timezone(user.timezone if user else None)
                        deadline_local = deadline_utc.astimezone(user_tz)
                        time_str = deadline_local.strftime("%H:%M")

                        meta_parts: list[str] = []
                        if task.priority == TaskPriority.high:
                            meta_parts.append("⚠️ Високий")
                        elif task.priority == TaskPriority.low:
                            meta_parts.append("💤 Низький")
                        else:
                            meta_parts.append("⚡ Середній")

                        if task.tag:
                            clean_tag = task.tag.lstrip("#")
                            meta_parts.append(f"🏷️ #{clean_tag}")

                        meta_parts.append(f"🕒 до {time_str}")
                        meta_str = " | ".join(meta_parts)

                        escaped_title = html.escape(task.title)
                        text = (
                            "🚨 <b>Увага! Дедлайн через 10 хвилин!</b>\n\n"
                            "Час завершувати завдання:\n"
                            f"• <b>{escaped_title}</b> — {meta_str}"
                        )
                        keyboard = get_deadline_keyboard(
                            task_id=task.id,
                            user_id=task.user_id,
                            snooze_minutes=15,
                        )

                        await bot.send_message(
                            chat_id=task.user_id,
                            text=text,
                            reply_markup=keyboard,
                            parse_mode="HTML",
                        )

                        task.reminder_sent_10m = True
                        task.reminder_sent_1h = True
                        await session.commit()
                        stats["reminders_10m_sent"] += 1

                # 1-hour proximity check (-1h)
                elif 600 < delta_sec <= 3600:
                    if not task.reminder_sent_1h:
                        user = await session.get(User, task.user_id)
                        user_tz = _resolve_user_timezone(user.timezone if user else None)
                        deadline_local = deadline_utc.astimezone(user_tz)
                        time_str = deadline_local.strftime("%H:%M")

                        meta_parts: list[str] = []
                        if task.priority == TaskPriority.high:
                            meta_parts.append("⚠️ Високий")
                        elif task.priority == TaskPriority.low:
                            meta_parts.append("💤 Низький")
                        else:
                            meta_parts.append("⚡ Середній")

                        if task.tag:
                            clean_tag = task.tag.lstrip("#")
                            meta_parts.append(f"🏷️ #{clean_tag}")

                        meta_parts.append(f"🕒 до {time_str}")
                        meta_str = " | ".join(meta_parts)

                        escaped_title = html.escape(task.title)
                        text = (
                            "⏳ <b>Нагадування про дедлайн!</b>\n\n"
                            "Залишилася 1 година до завершення:\n"
                            f"• <b>{escaped_title}</b> — {meta_str}"
                        )
                        keyboard = get_deadline_keyboard(
                            task_id=task.id,
                            user_id=task.user_id,
                            snooze_minutes=15,
                        )

                        await bot.send_message(
                            chat_id=task.user_id,
                            text=text,
                            reply_markup=keyboard,
                            parse_mode="HTML",
                        )

                        task.reminder_sent_1h = True
                        await session.commit()
                        stats["reminders_1h_sent"] += 1

            except TelegramForbiddenError as e:
                logger.warning("User %s has blocked the bot: %s", task.user_id, e)
                try:
                    task.reminder_sent_1h = True
                    task.reminder_sent_10m = True
                    await session.commit()
                except Exception:
                    await session.rollback()
            except TelegramAPIError as e:
                err_msg = str(e).lower()
                if "blocked" in err_msg or "forbidden" in err_msg or "deactivated" in err_msg:
                    logger.warning(
                        "User %s has blocked or deactivated the bot: %s",
                        task.user_id,
                        e,
                    )
                    try:
                        task.reminder_sent_1h = True
                        task.reminder_sent_10m = True
                        await session.commit()
                    except Exception:
                        await session.rollback()
                else:
                    logger.exception(
                        "Telegram API error dispatching deadline reminder for task %s (user %s): %s",
                        task.id,
                        task.user_id,
                        e,
                    )
                    await session.rollback()
                    stats["errors"] += 1
            except Exception:
                logger.exception(
                    "Unexpected error dispatching deadline reminder for task %s (user %s)",
                    task.id,
                    task.user_id,
                )
                await session.rollback()
                stats["errors"] += 1

    return stats
