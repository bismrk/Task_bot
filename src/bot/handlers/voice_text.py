"""Voice and text task ingestion bot handlers."""

from datetime import timedelta, timezone
import io
import logging
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from aiogram import Bot, F, Router
from aiogram.enums import ChatAction
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.keyboards.tasks import get_task_confirmation_keyboard
from src.bot.states.tasks import TaskIngestionState
from src.models.task import TaskPriority
from src.schemas.task import ExtractedTask
from src.services.ai_parser import parse_tasks_from_audio, parse_tasks_from_text
from src.services.user_service import get_or_create_user, get_user_local_time

logger = logging.getLogger(__name__)

router = Router(name="voice_text")
voice_text_router = router

EMPTY_TASKS_NOTIFICATION = (
    "💡 Не вдалося розпізнати завдання. Спробуйте надиктувати або написати чіткіше."
)


def format_extracted_tasks_message(
    tasks: list[ExtractedTask],
    user_timezone: str | None = None,
) -> str:
    """Format extracted tasks into an HTML-formatted message with semantic emojis.

    Adheres to _docs/design-system.md:
    Header: <b>📋 Розпізнані завдання:</b>
    Items: • [Назва задачі] — ⚠️ Високий | 🏷️ #робота | 📅 {target_date} | <b>🕒 до {time}</b>

    When ``user_timezone`` is provided, deadline timestamps (aware UTC or naive
    treated as UTC) are converted into the user's local timezone before formatting,
    with safe fallback to ``Europe/Kyiv`` on invalid/blank timezone strings.
    When ``user_timezone`` is ``None``, deadlines are formatted in their existing
    timezone without conversion for backward compatibility.
    """
    if not tasks:
        return ""

    target_tz: ZoneInfo | None = None
    if user_timezone is not None:
        tz_name = user_timezone.strip()
        if tz_name:
            try:
                target_tz = ZoneInfo(tz_name)
            except (ZoneInfoNotFoundError, KeyError, ValueError):
                logger.warning(
                    "Invalid user timezone %r in format_extracted_tasks_message; "
                    "falling back to Europe/Kyiv",
                    user_timezone,
                )
                target_tz = ZoneInfo("Europe/Kyiv")
        else:
            target_tz = ZoneInfo("Europe/Kyiv")

    lines = ["<b>📋 Розпізнані завдання:</b>\n"]
    for task in tasks:
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

        # Target date
        if task.target_date:
            meta_parts.append(f"📅 {task.target_date}")

        # Formatted deadline
        if task.deadline_at:
            if target_tz is not None:
                deadline_dt = task.deadline_at
                if (
                    deadline_dt.tzinfo is None
                    or deadline_dt.tzinfo.utcoffset(deadline_dt) is None
                ):
                    deadline_dt = deadline_dt.replace(tzinfo=timezone.utc)
                deadline_display = deadline_dt.astimezone(target_tz)
            else:
                deadline_display = task.deadline_at
            meta_parts.append(f"<b>🕒 до {deadline_display.strftime('%H:%M')}</b>")

        meta_str = " | ".join(meta_parts)
        lines.append(f"• {task.title} — {meta_str}")

    return "\n".join(lines)


@router.message(F.voice)
async def handle_voice_message(
    message: Message,
    bot: Bot,
    session: AsyncSession,
    state: FSMContext,
) -> Message | None:
    """Handle incoming voice message for task extraction.

    Verifies REQ-AI-01, REQ-AI-02, REQ-AI-03, REQ-USR-01:
    - Safely returns None if message.from_user or message.voice is missing.
    - Resolves user timezone from database via get_or_create_user.
    - Dispatches chat action UPLOAD_VOICE.
    - Downloads audio in-memory into io.BytesIO without writing to disk.
    - Invokes Gemini AI parser with audio bytes and user timezone.
    - If no tasks extracted, replies with polite notification without keyboard or FSM update.
    - If tasks extracted, saves pending tasks to FSM, sets waiting_confirmation state,
      and replies with formatted tasks list and confirmation keyboard.
    """
    if message.from_user is None or message.voice is None:
        return None

    user, _ = await get_or_create_user(session, telegram_id=message.from_user.id)

    await bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.UPLOAD_VOICE)

    audio_buffer = io.BytesIO()
    await bot.download(message.voice.file_id, destination=audio_buffer)
    audio_bytes = audio_buffer.getvalue()

    current_state = await state.get_state()
    is_planning_tomorrow = current_state == TaskIngestionState.planning_tomorrow.state
    if is_planning_tomorrow:
        tomorrow = get_user_local_time(user).date() + timedelta(days=1)
        tasks = await parse_tasks_from_audio(
            audio_bytes=audio_bytes,
            user_timezone=user.timezone,
            default_target_date=tomorrow,
        )
    else:
        tasks = await parse_tasks_from_audio(
            audio_bytes=audio_bytes,
            user_timezone=user.timezone,
        )

    if not tasks:
        return await message.answer(text=EMPTY_TASKS_NOTIFICATION)

    await state.update_data(
        pending_tasks=[t.model_dump(mode="json") for t in tasks],
        from_tomorrow_plan=is_planning_tomorrow,
    )
    await state.set_state(TaskIngestionState.waiting_confirmation)

    formatted_text = format_extracted_tasks_message(tasks, user_timezone=user.timezone)
    keyboard = get_task_confirmation_keyboard(user_id=message.from_user.id)
    return await message.answer(text=formatted_text, reply_markup=keyboard)


@router.message(F.text & ~F.text.startswith("/"))
async def handle_text_message(
    message: Message,
    bot: Bot,
    session: AsyncSession,
    state: FSMContext,
) -> Message | None:
    """Handle incoming non-command text message for task extraction.

    Verifies REQ-AI-02, REQ-AI-03, REQ-USR-01:
    - Safely returns None if message.from_user or message.text is empty/whitespace.
    - Resolves user timezone from database via get_or_create_user.
    - Dispatches chat action TYPING.
    - Invokes Gemini AI parser with text and user timezone (and tomorrow as default_target_date
      when in TaskIngestionState.planning_tomorrow).
    - If no tasks extracted, replies with polite notification without keyboard or FSM update.
    - If tasks extracted, saves pending tasks to FSM, sets waiting_confirmation state,
      and replies with formatted tasks list and confirmation keyboard.
    """
    if message.from_user is None or message.text is None or not message.text.strip():
        return None

    user, _ = await get_or_create_user(session, telegram_id=message.from_user.id)

    await bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)

    current_state = await state.get_state()
    is_planning_tomorrow = current_state == TaskIngestionState.planning_tomorrow.state
    if is_planning_tomorrow:
        tomorrow = get_user_local_time(user).date() + timedelta(days=1)
        tasks = await parse_tasks_from_text(
            text=message.text,
            user_timezone=user.timezone,
            default_target_date=tomorrow,
        )
    else:
        tasks = await parse_tasks_from_text(
            text=message.text,
            user_timezone=user.timezone,
        )

    if not tasks:
        return await message.answer(text=EMPTY_TASKS_NOTIFICATION)

    await state.update_data(
        pending_tasks=[t.model_dump(mode="json") for t in tasks],
        from_tomorrow_plan=is_planning_tomorrow,
    )
    await state.set_state(TaskIngestionState.waiting_confirmation)

    formatted_text = format_extracted_tasks_message(tasks, user_timezone=user.timezone)
    keyboard = get_task_confirmation_keyboard(user_id=message.from_user.id)
    return await message.answer(text=formatted_text, reply_markup=keyboard)
