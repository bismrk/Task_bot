"""Deadline reminder callback handlers."""

from datetime import datetime, timedelta, timezone
import html
import logging
from zoneinfo import ZoneInfo

from aiogram import Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.keyboards.deadline import DeadlineCallback, get_deadline_keyboard
from src.models.task import TaskStatus
from src.models.user import User
from src.services.task_service import get_task

logger = logging.getLogger(__name__)

router = Router(name="deadline")
deadline_router = router


@router.callback_query(DeadlineCallback.filter())
async def deadline_callback_handler(
    callback_query: CallbackQuery,
    callback_data: DeadlineCallback,
    session: AsyncSession,
) -> None:
    """Handle deadline notification callback queries (done and snooze).

    Verifies REQ-SCH-03, REQ-NFR-02, REQ-TSK-02:
    - Rejects unauthorized users with alert (REQ-NFR-02).
    - Checks task existence; alerts and removes keyboard if missing.
    - If action == 'done':
      - If already done, alerts user and removes keyboard.
      - Marks task as TaskStatus.done, commits.
      - Edits message to show strikethrough title and completion confirmation.
      - Removes inline keyboard.
      - Answers callback query with '✅ Виконано!'.
    - If action == 'snooze':
      - If already done, alerts user and removes keyboard.
      - Extends task.deadline_at by callback_data.minutes.
      - If deadline extends into next date, updates task.target_date.
      - Resets task.reminder_sent_10m = False.
      - If new deadline > 60m away from current time, also resets task.reminder_sent_1h = False.
      - Commits transaction.
      - Edits message text and updates keyboard.
      - Answers callback query with '⏰ Відкладено на {minutes} хв'.
    """
    if callback_query.from_user is None:
        return

    # Tenant security check (REQ-NFR-02)
    if callback_query.from_user.id != callback_data.user_id:
        await callback_query.answer(
            "⚠️ Ви не можете керувати завданнями іншого користувача.",
            show_alert=True,
        )
        return

    task = await get_task(
        session=session,
        task_id=callback_data.task_id,
        user_id=callback_data.user_id,
    )

    if task is None:
        await callback_query.answer(
            "⚠️ Завдання не знайдено або вже видалено.",
            show_alert=True,
        )
        if callback_query.message and isinstance(callback_query.message, Message):
            try:
                await callback_query.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass
        return

    if task.status == TaskStatus.done:
        await callback_query.answer(
            "⚠️ Завдання вже виконано.",
            show_alert=True,
        )
        if callback_query.message and isinstance(callback_query.message, Message):
            try:
                await callback_query.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass
        return

    if callback_data.action == "done":
        task.status = TaskStatus.done
        await session.commit()

        if callback_query.message and isinstance(callback_query.message, Message):
            escaped_title = html.escape(task.title)
            new_text = f"<s>{escaped_title}</s>\n\n✅ <b>Завдання виконано!</b>"
            try:
                await callback_query.message.edit_text(
                    text=new_text,
                    reply_markup=None,
                    parse_mode="HTML",
                )
            except Exception:
                pass

        await callback_query.answer("✅ Виконано!")
        return

    if callback_data.action == "snooze":
        now_utc = datetime.now(timezone.utc)
        snooze_mins = callback_data.minutes if callback_data.minutes > 0 else 15

        base_dt = task.deadline_at if task.deadline_at is not None else now_utc
        if base_dt.tzinfo is None:
            base_dt = base_dt.replace(tzinfo=timezone.utc)
        else:
            base_dt = base_dt.astimezone(timezone.utc)

        new_deadline = base_dt + timedelta(minutes=snooze_mins)
        task.deadline_at = new_deadline

        user = await session.get(User, task.user_id)
        user_tz = ZoneInfo(user.timezone) if user and user.timezone else ZoneInfo("Europe/Kyiv")
        deadline_local = new_deadline.astimezone(user_tz)

        if deadline_local.date() > task.target_date:
            task.target_date = deadline_local.date()
        elif new_deadline.date() > task.target_date:
            task.target_date = new_deadline.date()

        # Reset reminder flags
        task.reminder_sent_10m = False
        remaining_sec = (new_deadline - now_utc).total_seconds()
        if remaining_sec > 3600:
            task.reminder_sent_1h = False

        await session.commit()

        new_time_str = deadline_local.strftime("%H:%M")
        escaped_title = html.escape(task.title)
        new_text = (
            f"⏰ <b>Дедлайн відкладено на +{snooze_mins} хв!</b>\n\n"
            f"• <b>{escaped_title}</b> — новий дедлайн: 🕒 {new_time_str}"
        )
        new_kb = get_deadline_keyboard(
            task_id=task.id,
            user_id=task.user_id,
            snooze_minutes=snooze_mins,
        )

        if callback_query.message and isinstance(callback_query.message, Message):
            try:
                await callback_query.message.edit_text(
                    text=new_text,
                    reply_markup=new_kb,
                    parse_mode="HTML",
                )
            except Exception:
                pass

        await callback_query.answer(f"⏰ Відкладено на {snooze_mins} хв")
        return

    await callback_query.answer()
