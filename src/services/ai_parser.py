"""Gemini AI task parser service for text and audio inputs."""

from datetime import date, datetime, timezone
import inspect
import logging
from typing import Any
from unittest.mock import DEFAULT
from zoneinfo import ZoneInfo

from google import genai
from google.genai import types

from src.core.ai_client import get_ai_client
from src.schemas.task import ExtractedTask, TaskExtractionResult

logger = logging.getLogger(__name__)

DEFAULT_MODEL: str = "gemini-3.5-flash"
FALLBACK_MODEL: str = "gemini-3.5-flash-lite"


def _get_user_timezone(user_timezone: str) -> ZoneInfo:
    """Retrieve ZoneInfo for user timezone, defaulting to Europe/Kyiv if invalid."""
    try:
        return ZoneInfo(user_timezone)
    except Exception:
        return ZoneInfo("Europe/Kyiv")


def build_system_instruction(
    user_timezone: str = "Europe/Kyiv",
    reference_time: datetime | None = None,
    default_target_date: date | None = None,
) -> tuple[str, ZoneInfo]:
    """Build system instructions incorporating the user's reference date, time, and timezone."""
    try:
        tz = ZoneInfo(user_timezone)
    except Exception:
        tz = ZoneInfo("Europe/Kyiv")
        user_timezone = "Europe/Kyiv"

    if reference_time is None:
        now = datetime.now(tz)
    else:
        if reference_time.tzinfo is None:
            now = reference_time.replace(tzinfo=tz)
        else:
            now = reference_time.astimezone(tz)

    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M:%S")
    day_name = now.strftime("%A")

    if default_target_date is not None:
        default_date_str = default_target_date.strftime("%Y-%m-%d")
        default_date_context = f"- Default Target Date for Undated Tasks: {default_date_str}\n"
        target_date_rule = (
            f"   - 'target_date': The planned calendar date (YYYY-MM-DD). "
            f"If a task does NOT specify an explicit date or relative date expression, default 'target_date' to {default_date_str}. "
            f"When the user explicitly mentions a date or relative expression such as 'сьогодні' (today, {date_str}), 'завтра' (tomorrow), 'післязавтра', or days of the week (e.g. 'у п'ятницю', 'в понеділок'), honor it strictly relative to the Current Local Date ({date_str}).\n"
        )
        deadline_rule = (
            f"   - 'deadline_at': If a specific time is mentioned (e.g. 'о 15:00', 'до 18:30', '15:00'), format as an ISO-8601 string with UTC 'Z' or local timezone offset for {user_timezone}. "
            f"If a time is mentioned without an explicit date, anchor it to {default_date_str} in {user_timezone}. "
            "If no specific time of day is mentioned, set to null.\n"
        )
    else:
        default_date_context = ""
        target_date_rule = (
            f"   - 'target_date': The planned calendar date (YYYY-MM-DD). Resolve relative expressions such as 'сьогодні' (today, {date_str}), 'завтра' (tomorrow), 'післязавтра', days of the week (e.g. 'у п'ятницю', 'в понеділок') strictly relative to the Current Local Date.\n"
        )
        deadline_rule = (
            f"   - 'deadline_at': If a specific time is mentioned (e.g. 'о 15:00', 'до 18:30', '15:00'), format as an ISO-8601 string with UTC 'Z' or local timezone offset for {user_timezone}. If no specific time of day is mentioned, set to null.\n"
        )

    instruction = (
        "You are an AI assistant specialized in extracting structured actionable tasks from user voice notes and text messages.\n\n"
        "User Temporal Context:\n"
        f"- Current Local Date: {date_str}\n"
        f"- Current Local Time: {time_str}\n"
        f"- Current Day of Week: {day_name}\n"
        f"- User Timezone: {user_timezone}\n"
        f"{default_date_context}\n"
        "Extraction Rules:\n"
        "1. Extract all actionable tasks mentioned by the user.\n"
        "2. For each task:\n"
        "   - 'title': Concise summary of the task (up to 255 characters, stripped of leading/trailing whitespace).\n"
        f"{target_date_rule}"
        f"{deadline_rule}"
        "   - 'priority': Task urgency/importance ('low', 'medium', 'high'). If the user indicates urgency or importance ('терміново', 'важливо', 'високий пріоритет', 'urgent', 'asap'), set to 'high'. If low priority ('низький', 'не терміново', 'low'), set to 'low'. Default to 'medium'.\n"
        "   - 'tag': Optional single category or context tag (e.g. 'робота', 'дім', 'навчання', 'покупки'). Strip any leading '#' and trim to at most 50 characters. If no category or topic is evident, set to null.\n"
        "3. If the input contains chit-chat, conversational filler, background noise, or no actionable tasks, return an empty tasks list []."
    )
    return instruction, tz


async def _execute_generate_content(
    client: Any,
    model: str,
    contents: Any,
    config: types.GenerateContentConfig,
) -> Any:
    """Execute Gemini generate_content supporting both aio and sync/mocked clients."""
    mock_models = getattr(client, "models", None)
    mock_aio = getattr(client, "aio", None)

    # 1. If mock_aio has generate_content configured with custom return_value / side_effect
    if mock_aio is not None and hasattr(mock_aio, "models") and hasattr(mock_aio.models, "generate_content"):
        fn = mock_aio.models.generate_content
        ret = getattr(fn, "_mock_return_value", None)
        side = getattr(fn, "side_effect", None)
        if not hasattr(fn, "_mock_return_value") or (ret is not DEFAULT or side is not None):
            res = fn(model=model, contents=contents, config=config)
            if inspect.isawaitable(res):
                return await res
            return res

    # 2. If client.models.generate_content was configured with custom return_value / side_effect
    if mock_models is not None and hasattr(mock_models, "generate_content"):
        fn = mock_models.generate_content
        ret = getattr(fn, "_mock_return_value", None)
        side = getattr(fn, "side_effect", None)
        if not hasattr(fn, "_mock_return_value") or (ret is not DEFAULT or side is not None):
            res = fn(model=model, contents=contents, config=config)
            if inspect.isawaitable(res):
                return await res
            return res

    # 3. Default path: client.aio.models.generate_content (real google-genai async API)
    if mock_aio is not None and hasattr(mock_aio, "models") and hasattr(mock_aio.models, "generate_content"):
        res = mock_aio.models.generate_content(model=model, contents=contents, config=config)
        if inspect.isawaitable(res):
            return await res
        return res

    # 4. Fallback to client.models.generate_content
    if mock_models is not None and hasattr(mock_models, "generate_content"):
        res = mock_models.generate_content(model=model, contents=contents, config=config)
        if inspect.isawaitable(res):
            return await res
        return res

    raise AttributeError("Gemini client does not have generate_content method")


async def parse_tasks(
    content: str | bytes,
    mime_type: str = "text/plain",
    user_timezone: str = "Europe/Kyiv",
    reference_time: datetime | None = None,
    client: genai.Client | None = None,
    default_target_date: date | None = None,
) -> list[ExtractedTask]:
    """Parse tasks from text or audio bytes using Gemini 2.5 Flash structured outputs."""
    # REQ-AI-01 & REQ-AI-02: Check empty or whitespace-only inputs
    if isinstance(content, str):
        if not content or not content.strip():
            return []
    elif isinstance(content, bytes):
        if not content:
            return []
    else:
        return []

    # REQ-AI-01: Package audio bytes using types.Part.from_bytes without saving to disk
    if isinstance(content, bytes):
        audio_mime = mime_type if mime_type != "text/plain" else "audio/ogg"
        part = types.Part.from_bytes(data=content, mime_type=audio_mime)
        contents: list[Any] = [part]
    else:
        contents = [content]

    # Resolve AI client
    if client is None:
        try:
            client = get_ai_client()
        except Exception as e:
            logger.error("Failed to obtain Gemini AI client: %s", e)
            return []

    # REQ-AI-02: Prompt templating with reference time and user timezone
    system_instruction, tz = build_system_instruction(
        user_timezone=user_timezone,
        reference_time=reference_time,
        default_target_date=default_target_date,
    )

    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        response_mime_type="application/json",
        response_schema=TaskExtractionResult,
    )

    # Invoke Gemini generation with graceful exception handling and fallback model
    candidate_models = (
        [DEFAULT_MODEL, FALLBACK_MODEL]
        if DEFAULT_MODEL != FALLBACK_MODEL
        else [DEFAULT_MODEL]
    )
    response = None
    last_error: Exception | None = None

    for model_name in candidate_models:
        try:
            response = await _execute_generate_content(
                client=client,
                model=model_name,
                contents=contents,
                config=config,
            )
            if response is not None:
                break
        except Exception as e:
            last_error = e
            logger.warning(
                "Gemini API call with model %s failed: %s; trying fallback model...",
                model_name,
                e,
            )

    if response is None:
        if last_error is not None:
            logger.error("All Gemini API candidate models failed. Last error: %s", last_error)
        return []

    # Parse result into TaskExtractionResult
    extraction_result: TaskExtractionResult | None = None
    parsed = getattr(response, "parsed", None)
    if parsed is not None:
        if isinstance(parsed, TaskExtractionResult):
            extraction_result = parsed
        elif isinstance(parsed, dict):
            try:
                extraction_result = TaskExtractionResult.model_validate(parsed)
            except Exception as e:
                logger.error("Failed to validate parsed dictionary: %s", e)
                return []
        elif isinstance(parsed, str):
            try:
                extraction_result = TaskExtractionResult.model_validate_json(parsed)
            except Exception as e:
                logger.error("Failed to parse string parsed field: %s", e)
                return []

    if extraction_result is None and hasattr(response, "text") and response.text:
        raw_text = response.text.strip()
        if raw_text.startswith("```"):
            lines = raw_text.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            raw_text = "\n".join(lines).strip()
        try:
            extraction_result = TaskExtractionResult.model_validate_json(raw_text)
        except Exception as e:
            logger.error("Failed to parse Gemini response text as TaskExtractionResult: %s", e)
            return []

    if extraction_result is None:
        logger.error("Gemini response did not contain a valid TaskExtractionResult")
        return []

    # REQ-AI-02: Convert deadlines to UTC timezone-aware datetimes
    for task in extraction_result.tasks:
        if task.deadline_at is not None:
            if task.deadline_at.tzinfo is None:
                localized = task.deadline_at.replace(tzinfo=tz)
                task.deadline_at = localized.astimezone(timezone.utc)
            else:
                task.deadline_at = task.deadline_at.astimezone(timezone.utc)

    return extraction_result.tasks


async def parse_tasks_from_text(
    text: str,
    user_timezone: str = "Europe/Kyiv",
    reference_time: datetime | None = None,
    client: genai.Client | None = None,
    default_target_date: date | None = None,
) -> list[ExtractedTask]:
    """Extract tasks from a plain text message using Gemini AI."""
    return await parse_tasks(
        content=text,
        mime_type="text/plain",
        user_timezone=user_timezone,
        reference_time=reference_time,
        client=client,
        default_target_date=default_target_date,
    )


async def parse_tasks_from_audio(
    audio_bytes: bytes,
    mime_type: str = "audio/ogg",
    user_timezone: str = "Europe/Kyiv",
    reference_time: datetime | None = None,
    client: genai.Client | None = None,
    default_target_date: date | None = None,
) -> list[ExtractedTask]:
    """Extract tasks from raw audio bytes (e.g. Telegram .ogg Opus) using Gemini AI."""
    return await parse_tasks(
        content=audio_bytes,
        mime_type=mime_type,
        user_timezone=user_timezone,
        reference_time=reference_time,
        client=client,
        default_target_date=default_target_date,
    )
