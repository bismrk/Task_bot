"""Midnight rollover dialogue and callback handlers."""

from datetime import date
import logging

from aiogram import Bot, Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.keyboards.rollover import (
    RolloverCallback,
    get_batch_rollover_keyboard,
    get_task_rollover_keyboard,
)
from src.models.task import Task, TaskPriority, TaskStatus
from src.models.user import User
from src.services.task_service import (
    batch_rollover_tasks,
    get_overdue_tasks,
    get_task,
    rollover_task,
    toggle_task_status,
)
from src.services.user_service import get_user, get_user_local_time

logger = logging.getLogger(__name__)

router = Router(name="rollover")
rollover_router = router

FOLLOW_UP_PROMPT_TEXT = "✨ Всі хвости розібрано! Надиктуйте або напишіть план на сьогодні 🚀"
TENANT_SECURITY_ALERT = "⚠️ Ви не можете керувати завданнями іншого користувача."
TASK_ALREADY_PROCESSED_ALERT = "⚠️ Завдання вже опрацьовано або не знайдено."
ALL_PROCESSED_TEXT = "✨ Всі хвости вже опрацьовано!"


def format_overdue_task_item(task: Task) -> str:
    """Format an overdue task into an HTML string with semantic emojis.

    Adheres to _docs/design-system.md:
    Items: • [Назва задачі] — ⚠️ Високий | 🏷️ #робота | 📅 {task.target_date}
    """
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

    # Original target date
    if task.target_date:
        meta_parts.append(f"📅 {task.target_date}")

    meta_str = " | ".join(meta_parts)
    return f"• <b>{task.title}</b> — {meta_str}"


async def send_midnight_rollover_dialogue(
    bot: Bot,
    session: AsyncSession,
    user: User,
    reference_date: date | None = None,
) -> list[Message]:
    """Trigger the midnight rollover review dialogue for a user (REQ-SCH-01).

    - Computes local_today: uses reference_date if provided, else user local time.
    - Queries uncompleted overdue tasks (target_date < local_today).
    - If none exist, sends single congratulatory message with no keyboard and returns [sent_message].
    - If overdue tasks exist:
      - Sends overview batch control message with get_batch_rollover_keyboard.
      - Sends each overdue task as an individual message with get_task_rollover_keyboard.
      - Returns list of all sent Message objects in order sent.
    """
    if reference_date is not None:
        local_today = reference_date
    else:
        local_today = get_user_local_time(user).date()

    overdue_tasks = await get_overdue_tasks(
        session=session,
        user_id=user.telegram_id,
        before_date=local_today,
    )

    if not overdue_tasks:
        congrats_text = (
            "✨ <b>Всі вчорашні завдання виконано!</b> Чудова робота.\n\n"
            "Надиктуйте або напишіть план на сьогодні 🚀"
        )
        msg = await bot.send_message(
            chat_id=user.telegram_id,
            text=congrats_text,
        )
        return [msg]

    sent_messages: list[Message] = []
    count = len(overdue_tasks)
    overview_text = (
        f"📋 <b>Невиконані завдання за вчора (\"хвости\"):</b>\n"
        f"У вас залишилося {count} невиконаних завдань."
    )
    overview_msg = await bot.send_message(
        chat_id=user.telegram_id,
        text=overview_text,
        reply_markup=get_batch_rollover_keyboard(user_id=user.telegram_id),
    )
    sent_messages.append(overview_msg)

    for task in overdue_tasks:
        task_text = format_overdue_task_item(task)
        task_msg = await bot.send_message(
            chat_id=user.telegram_id,
            text=task_text,
            reply_markup=get_task_rollover_keyboard(
                task_id=task.id,
                user_id=user.telegram_id,
            ),
        )
        sent_messages.append(task_msg)

    return sent_messages


@router.callback_query(RolloverCallback.filter())
async def handle_rollover_callback(
    callback_query: CallbackQuery,
    callback_data: RolloverCallback,
    bot: Bot,
    session: AsyncSession,
) -> None:
    """Handle rollover actions (postpone, close, postpone_all, close_all).

    Verifies REQ-SCH-01, REQ-TSK-01, REQ-TSK-02, REQ-NFR-02:
    - Enforces tenant isolation (rejects callback if from_user.id != callback_data.user_id).
    - Resolves user timezone and local today date.
    - Handles single task postponement to today and status cancellation.
    - Handles batch postponement and batch status cancellation.
    - Dynamically updates message text, removes reply markup, and answers callback query.
    - Sends follow-up prompt to plan today once all overdue tasks are cleared.
    """
    if callback_query.from_user is None or not isinstance(callback_query.message, Message):
        return

    # Tenant Security Check (REQ-NFR-02)
    if callback_query.from_user.id != callback_data.user_id:
        await callback_query.answer(
            TENANT_SECURITY_ALERT,
            show_alert=True,
        )
        return

    user = await get_user(session, callback_query.from_user.id)
    if user is not None:
        local_today = get_user_local_time(user).date()
    else:
        dummy_user = User(telegram_id=callback_query.from_user.id, timezone="Europe/Kyiv")
        local_today = get_user_local_time(dummy_user).date()

    if callback_data.action == "postpone":
        if callback_data.task_id is None:
            await callback_query.answer(TASK_ALREADY_PROCESSED_ALERT, show_alert=True)
            await callback_query.message.edit_reply_markup(reply_markup=None)
            return

        task = await get_task(session, callback_data.task_id, callback_query.from_user.id)
        if task is None or task.status != TaskStatus.todo or task.target_date >= local_today:
            await callback_query.answer(TASK_ALREADY_PROCESSED_ALERT, show_alert=True)
            await callback_query.message.edit_reply_markup(reply_markup=None)
            return

        try:
            updated_task = await rollover_task(
                session=session,
                task_id=callback_data.task_id,
                user_id=callback_query.from_user.id,
                new_date=local_today,
            )
        except ValueError:
            await callback_query.answer(TASK_ALREADY_PROCESSED_ALERT, show_alert=True)
            await callback_query.message.edit_reply_markup(reply_markup=None)
            return

        await callback_query.message.edit_text(
            text=f"⏩ Завдання «{updated_task.title}» перенесено на сьогодні!",
            reply_markup=None,
        )
        await callback_query.answer("Перенесено на сьогодні!")

        remaining_overdue = await get_overdue_tasks(
            session=session,
            user_id=callback_query.from_user.id,
            before_date=local_today,
        )
        if len(remaining_overdue) == 0:
            await bot.send_message(
                chat_id=callback_query.from_user.id,
                text=FOLLOW_UP_PROMPT_TEXT,
            )
        return

    if callback_data.action == "close":
        if callback_data.task_id is None:
            await callback_query.answer(TASK_ALREADY_PROCESSED_ALERT, show_alert=True)
            await callback_query.message.edit_reply_markup(reply_markup=None)
            return

        task = await get_task(session, callback_data.task_id, callback_query.from_user.id)
        if task is None or task.status != TaskStatus.todo or task.target_date >= local_today:
            await callback_query.answer(TASK_ALREADY_PROCESSED_ALERT, show_alert=True)
            await callback_query.message.edit_reply_markup(reply_markup=None)
            return

        try:
            updated_task = await toggle_task_status(
                session=session,
                task_id=callback_data.task_id,
                user_id=callback_query.from_user.id,
                new_status=TaskStatus.canceled,
            )
        except ValueError:
            await callback_query.answer(TASK_ALREADY_PROCESSED_ALERT, show_alert=True)
            await callback_query.message.edit_reply_markup(reply_markup=None)
            return

        await callback_query.message.edit_text(
            text=f"❌ Завдання «{updated_task.title}» закрито.",
            reply_markup=None,
        )
        await callback_query.answer("Завдання закрито!")

        remaining_overdue = await get_overdue_tasks(
            session=session,
            user_id=callback_query.from_user.id,
            before_date=local_today,
        )
        if len(remaining_overdue) == 0:
            await bot.send_message(
                chat_id=callback_query.from_user.id,
                text=FOLLOW_UP_PROMPT_TEXT,
            )
        return

    if callback_data.action == "postpone_all":
        overdue_tasks = await get_overdue_tasks(
            session=session,
            user_id=callback_query.from_user.id,
            before_date=local_today,
        )
        if not overdue_tasks:
            await callback_query.message.edit_text(
                text=ALL_PROCESSED_TEXT,
                reply_markup=None,
            )
            await callback_query.answer()
            return

        count = len(overdue_tasks)
        await batch_rollover_tasks(
            session=session,
            task_ids=[t.id for t in overdue_tasks],
            user_id=callback_query.from_user.id,
            new_date=local_today,
        )
        await callback_query.message.edit_text(
            text=f"⏩ Всі завдання ({count}) перенесено на сьогодні!",
            reply_markup=None,
        )
        await callback_query.answer("Всі завдання перенесено!")
        await bot.send_message(
            chat_id=callback_query.from_user.id,
            text=FOLLOW_UP_PROMPT_TEXT,
        )
        return

    if callback_data.action == "close_all":
        overdue_tasks = await get_overdue_tasks(
            session=session,
            user_id=callback_query.from_user.id,
            before_date=local_today,
        )
        if not overdue_tasks:
            await callback_query.message.edit_text(
                text=ALL_PROCESSED_TEXT,
                reply_markup=None,
            )
            await callback_query.answer()
            return

        count = len(overdue_tasks)
        for t in overdue_tasks:
            t.status = TaskStatus.canceled
        await session.commit()

        await callback_query.message.edit_text(
            text=f"❌ Всі завдання ({count}) закрито.",
            reply_markup=None,
        )
        await callback_query.answer("Всі завдання закрито!")
        await bot.send_message(
            chat_id=callback_query.from_user.id,
            text=FOLLOW_UP_PROMPT_TEXT,
        )
        return

    await callback_query.answer()
