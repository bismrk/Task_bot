"""Unit tests for Gemini AI client, task schemas, and task parser service."""

from datetime import date, datetime, timezone
import os
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from src.core.ai_client import get_ai_client
from src.models.task import TaskPriority
from src.schemas.task import ExtractedTask, TaskExtractionResult
from src.services.ai_parser import (
    DEFAULT_MODEL,
    build_system_instruction,
    parse_tasks,
    parse_tasks_from_audio,
    parse_tasks_from_text,
)


# ============================================================================
# get_ai_client Tests
# ============================================================================


def test_get_ai_client_with_explicit_key() -> None:
    """Verifies REQ-AI-02: get_ai_client initializes Client with explicitly passed api_key."""
    client = get_ai_client(api_key="test-explicit-key-12345")
    assert client is not None
    assert hasattr(client, "models")


def test_get_ai_client_with_env_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies REQ-AI-02: get_ai_client initializes Client reading GEMINI_API_KEY from environment."""
    monkeypatch.setenv("GEMINI_API_KEY", "env-secret-api-key")
    client = get_ai_client()
    assert client is not None
    assert hasattr(client, "models")


def test_get_ai_client_raises_value_error_when_no_key_provided(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verifies REQ-AI-02: get_ai_client raises ValueError when GEMINI_API_KEY is not set."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="GEMINI_API_KEY environment variable is not set"):
        get_ai_client()


def test_get_ai_client_raises_value_error_when_key_is_empty_or_whitespace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verifies REQ-AI-02: get_ai_client raises ValueError when key is empty or only whitespace."""
    monkeypatch.setenv("GEMINI_API_KEY", "   ")
    with pytest.raises(ValueError, match="GEMINI_API_KEY environment variable is not set"):
        get_ai_client()

    with pytest.raises(ValueError, match="GEMINI_API_KEY environment variable is not set"):
        get_ai_client(api_key="")


# ============================================================================
# ExtractedTask & TaskExtractionResult Schema Tests
# ============================================================================


def test_extracted_task_minimal_valid() -> None:
    """Verifies REQ-AI-02: ExtractedTask sets default values for priority, deadline_at, and tag."""
    task = ExtractedTask(
        title="Купити молоко",
        target_date=date(2026, 11, 20),
    )
    assert task.title == "Купити молоко"
    assert task.target_date == date(2026, 11, 20)
    assert task.deadline_at is None
    assert task.priority == TaskPriority.medium
    assert task.tag is None


def test_extracted_task_title_stripped() -> None:
    """Verifies REQ-AI-02: ExtractedTask strips leading and trailing whitespace from title."""
    task = ExtractedTask(
        title="   Здати квартальний звіт   \n",
        target_date=date(2026, 11, 20),
    )
    assert task.title == "Здати квартальний звіт"


def test_extracted_task_empty_title_raises_validation_error() -> None:
    """Verifies REQ-AI-02: ExtractedTask rejects empty or whitespace-only titles."""
    with pytest.raises(ValidationError):
        ExtractedTask(title="", target_date=date(2026, 11, 20))

    with pytest.raises(ValidationError):
        ExtractedTask(title="   \n\t  ", target_date=date(2026, 11, 20))


def test_extracted_task_title_max_length_exceeded() -> None:
    """Verifies REQ-AI-02: ExtractedTask rejects titles exceeding 255 characters."""
    with pytest.raises(ValidationError):
        ExtractedTask(title="A" * 256, target_date=date(2026, 11, 20))

    task = ExtractedTask(title="A" * 255, target_date=date(2026, 11, 20))
    assert len(task.title) == 255


def test_extracted_task_priority_normalization() -> None:
    """Verifies REQ-AI-02: ExtractedTask normalizes priority strings and Ukrainian keywords."""
    t_high = ExtractedTask(
        title="Термінове завдання",
        target_date=date(2026, 11, 20),
        priority="high",
    )
    assert t_high.priority == TaskPriority.high

    t_urgent = ExtractedTask(
        title="Термінове завдання 2",
        target_date=date(2026, 11, 20),
        priority="терміново",
    )
    assert t_urgent.priority == TaskPriority.high

    t_low = ExtractedTask(
        title="Неважливе завдання",
        target_date=date(2026, 11, 20),
        priority="низький",
    )
    assert t_low.priority == TaskPriority.low

    t_default = ExtractedTask(
        title="Звичайне завдання",
        target_date=date(2026, 11, 20),
        priority="невідомий_пріоритет",
    )
    assert t_default.priority == TaskPriority.medium


def test_extracted_task_tag_stripping_and_normalization() -> None:
    """Verifies REQ-AI-02: ExtractedTask strips '#' prefixes and trims tags to 50 characters."""
    task = ExtractedTask(
        title="Task",
        target_date=date(2026, 11, 20),
        tag="#робота",
    )
    assert task.tag == "робота"

    task_whitespace = ExtractedTask(
        title="Task",
        target_date=date(2026, 11, 20),
        tag="   ###дім   ",
    )
    assert task_whitespace.tag == "дім"

    task_empty_tag = ExtractedTask(
        title="Task",
        target_date=date(2026, 11, 20),
        tag="###",
    )
    assert task_empty_tag.tag is None

    task_long_tag = ExtractedTask(
        title="Task",
        target_date=date(2026, 11, 20),
        tag="#" + ("x" * 60),
    )
    assert len(task_long_tag.tag) == 50


def test_extracted_task_deadline_at_timezone_validation() -> None:
    """Verifies REQ-AI-02: ExtractedTask requires timezone-aware datetime for deadline_at."""
    # Aware datetime with UTC
    dt_utc = datetime(2026, 11, 20, 15, 0, tzinfo=timezone.utc)
    t_utc = ExtractedTask(
        title="Task",
        target_date=date(2026, 11, 20),
        deadline_at=dt_utc,
    )
    assert t_utc.deadline_at == dt_utc

    # Aware datetime with Kyiv timezone
    dt_kyiv = datetime(2026, 11, 20, 15, 0, tzinfo=ZoneInfo("Europe/Kyiv"))
    t_kyiv = ExtractedTask(
        title="Task",
        target_date=date(2026, 11, 20),
        deadline_at=dt_kyiv,
    )
    assert t_kyiv.deadline_at == dt_kyiv

    # Naive datetime should fail validation
    dt_naive = datetime(2026, 11, 20, 15, 0)
    with pytest.raises(ValidationError):
        ExtractedTask(
            title="Task",
            target_date=date(2026, 11, 20),
            deadline_at=dt_naive,
        )


def test_task_extraction_result_serialization() -> None:
    """Verifies REQ-AI-02: TaskExtractionResult serialization and deserialization."""
    result = TaskExtractionResult(
        tasks=[
            ExtractedTask(
                title="Task 1",
                target_date=date(2026, 11, 20),
                deadline_at=datetime(2026, 11, 20, 15, 0, tzinfo=timezone.utc),
                priority=TaskPriority.high,
                tag="робота",
            ),
            ExtractedTask(
                title="Task 2",
                target_date=date(2026, 11, 21),
            ),
        ]
    )
    json_data = result.model_dump_json()
    reconstructed = TaskExtractionResult.model_validate_json(json_data)
    assert len(reconstructed.tasks) == 2
    assert reconstructed.tasks[0].title == "Task 1"
    assert reconstructed.tasks[0].priority == TaskPriority.high
    assert reconstructed.tasks[1].title == "Task 2"
    assert reconstructed.tasks[1].priority == TaskPriority.medium


# ============================================================================
# Prompt Construction & Timezone Tests
# ============================================================================


def test_build_system_instruction_incorporates_context() -> None:
    """Verifies REQ-AI-02: build_system_instruction injects formatted date, time, weekday, and tz."""
    ref_time = datetime(2026, 11, 20, 10, 30, 0, tzinfo=ZoneInfo("Europe/Kyiv"))
    instruction, tz = build_system_instruction(
        user_timezone="Europe/Kyiv",
        reference_time=ref_time,
    )
    assert "2026-11-20" in instruction
    assert "10:30:00" in instruction
    assert "Friday" in instruction
    assert "Europe/Kyiv" in instruction
    assert tz == ZoneInfo("Europe/Kyiv")


def test_build_system_instruction_fallback_on_invalid_timezone() -> None:
    """Verifies REQ-AI-02: build_system_instruction falls back to Europe/Kyiv on invalid timezone."""
    instruction, tz = build_system_instruction(
        user_timezone="Invalid/Timezone",
        reference_time=datetime(2026, 11, 20, 12, 0, 0),
    )
    assert "Europe/Kyiv" in instruction
    assert tz == ZoneInfo("Europe/Kyiv")


# ============================================================================
# Empty Input Tests
# ============================================================================


@pytest.mark.asyncio
async def test_parse_tasks_empty_text_returns_empty_list() -> None:
    """Verifies REQ-AI-02: parse_tasks returns [] immediately on empty text without API calls."""
    mock_client = AsyncMock()

    res_empty = await parse_tasks("", client=mock_client)
    assert res_empty == []

    res_whitespace = await parse_tasks("   \n\t  ", client=mock_client)
    assert res_whitespace == []

    # Verify no API calls were made
    assert mock_client.models.generate_content.call_count == 0
    assert mock_client.aio.models.generate_content.call_count == 0


@pytest.mark.asyncio
async def test_parse_tasks_from_text_empty_input() -> None:
    """Verifies REQ-AI-02: parse_tasks_from_text returns [] on empty string without API calls."""
    mock_client = AsyncMock()
    res = await parse_tasks_from_text("   ", client=mock_client)
    assert res == []
    assert mock_client.models.generate_content.call_count == 0


@pytest.mark.asyncio
async def test_parse_tasks_empty_audio_bytes_returns_empty_list() -> None:
    """Verifies REQ-AI-01: parse_tasks returns [] immediately on empty audio bytes without API calls."""
    mock_client = AsyncMock()

    res_bytes = await parse_tasks(b"", mime_type="audio/ogg", client=mock_client)
    assert res_bytes == []

    res_helper = await parse_tasks_from_audio(b"", client=mock_client)
    assert res_helper == []

    assert mock_client.models.generate_content.call_count == 0
    assert mock_client.aio.models.generate_content.call_count == 0


# ============================================================================
# parse_tasks_from_text Extraction Tests
# ============================================================================


@pytest.mark.asyncio
async def test_parse_tasks_from_text_single_task() -> None:
    """Verifies REQ-AI-02: parse_tasks_from_text extracts single task and converts deadline to UTC."""
    mock_client = AsyncMock()
    # Mocking returning a task with Kyiv timezone offset (+02:00)
    mock_task = ExtractedTask(
        title="Здати квартальний звіт",
        target_date=date(2026, 11, 20),
        deadline_at=datetime(2026, 11, 20, 15, 0, tzinfo=ZoneInfo("Europe/Kyiv")),
        priority=TaskPriority.high,
        tag="робота",
    )
    mock_client.models.generate_content.return_value = AsyncMock(
        parsed=TaskExtractionResult(tasks=[mock_task])
    )

    tasks = await parse_tasks_from_text(
        text="Завтра о 15:00 здати квартальний звіт по роботі, терміново",
        user_timezone="Europe/Kyiv",
        reference_time=datetime(2026, 11, 19, 12, 0, tzinfo=ZoneInfo("Europe/Kyiv")),
        client=mock_client,
    )

    assert len(tasks) == 1
    extracted = tasks[0]
    assert extracted.title == "Здати квартальний звіт"
    assert extracted.target_date == date(2026, 11, 20)
    assert extracted.priority == TaskPriority.high
    assert extracted.tag == "робота"
    # Verify deadline_at was converted to UTC: 15:00 Kyiv (UTC+2) -> 13:00 UTC
    assert extracted.deadline_at is not None
    assert extracted.deadline_at.tzinfo == timezone.utc
    assert extracted.deadline_at.hour == 13
    assert extracted.deadline_at.minute == 0


@pytest.mark.asyncio
async def test_parse_tasks_from_text_multiple_tasks() -> None:
    """Verifies REQ-AI-02: parse_tasks_from_text extracts multiple tasks in one message."""
    mock_client = AsyncMock()
    mock_client.models.generate_content.return_value = AsyncMock(
        parsed=TaskExtractionResult(
            tasks=[
                ExtractedTask(
                    title="Купити каву",
                    target_date=date(2026, 11, 20),
                    priority=TaskPriority.low,
                    tag="покупки",
                ),
                ExtractedTask(
                    title="Зустріч з клієнтом",
                    target_date=date(2026, 11, 20),
                    deadline_at=datetime(2026, 11, 20, 17, 0, tzinfo=ZoneInfo("Europe/Kyiv")),
                    priority=TaskPriority.high,
                    tag="робота",
                ),
            ]
        )
    )

    tasks = await parse_tasks_from_text(
        text="Купити каву і зустріч з клієнтом о 17:00",
        user_timezone="Europe/Kyiv",
        client=mock_client,
    )

    assert len(tasks) == 2
    assert tasks[0].title == "Купити каву"
    assert tasks[0].priority == TaskPriority.low
    assert tasks[0].tag == "покупки"
    assert tasks[1].title == "Зустріч з клієнтом"
    assert tasks[1].priority == TaskPriority.high
    assert tasks[1].deadline_at.hour == 15  # 17:00 Kyiv -> 15:00 UTC


@pytest.mark.asyncio
async def test_parse_tasks_fallback_to_json_text_when_parsed_missing() -> None:
    """Verifies REQ-AI-02: parse_tasks parses response.text JSON when parsed field is None."""
    mock_client = AsyncMock()
    json_payload = (
        '{"tasks": [{"title": "Написати тести", "target_date": "2026-11-20", '
        '"deadline_at": "2026-11-20T16:00:00Z", "priority": "high", "tag": "dev"}]}'
    )
    mock_response = MagicMock()
    mock_response.parsed = None
    mock_response.text = json_payload
    mock_client.models.generate_content.return_value = mock_response

    tasks = await parse_tasks("Написати тести", client=mock_client)
    assert len(tasks) == 1
    assert tasks[0].title == "Написати тести"
    assert tasks[0].priority == TaskPriority.high
    assert tasks[0].tag == "dev"
    assert tasks[0].deadline_at == datetime(2026, 11, 20, 16, 0, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_parse_tasks_handles_markdown_fenced_json_text() -> None:
    """Verifies REQ-AI-02: parse_tasks strips markdown code fences from response.text."""
    mock_client = AsyncMock()
    fenced_payload = (
        "```json\n"
        '{"tasks": [{"title": "Перевірити PR", "target_date": "2026-11-21", '
        '"priority": "medium", "tag": "github"}]}\n'
        "```"
    )
    mock_response = MagicMock()
    mock_response.parsed = None
    mock_response.text = fenced_payload
    mock_client.models.generate_content.return_value = mock_response

    tasks = await parse_tasks("Перевірити PR", client=mock_client)
    assert len(tasks) == 1
    assert tasks[0].title == "Перевірити PR"
    assert tasks[0].tag == "github"


# ============================================================================
# parse_tasks_from_audio Tests
# ============================================================================


@pytest.mark.asyncio
async def test_parse_tasks_from_audio_packages_payload_in_memory() -> None:
    """Verifies REQ-AI-01: parse_tasks_from_audio uses types.Part.from_bytes without writing to disk."""
    mock_client = AsyncMock()
    mock_task = ExtractedTask(
        title="Голосове завдання",
        target_date=date(2026, 11, 20),
    )
    mock_client.models.generate_content.return_value = AsyncMock(
        parsed=TaskExtractionResult(tasks=[mock_task])
    )

    fake_audio_bytes = b"OggS\x00\x02fake_opus_audio_data"

    with patch("src.services.ai_parser.types.Part.from_bytes") as mock_from_bytes:
        mock_part = MagicMock()
        mock_from_bytes.return_value = mock_part

        tasks = await parse_tasks_from_audio(
            audio_bytes=fake_audio_bytes,
            mime_type="audio/ogg",
            client=mock_client,
        )

        mock_from_bytes.assert_called_once_with(
            data=fake_audio_bytes,
            mime_type="audio/ogg",
        )
        assert len(tasks) == 1
        assert tasks[0].title == "Голосове завдання"


# ============================================================================
# Non-Task Inputs (Filler/Noise) & Edge Cases
# ============================================================================


@pytest.mark.asyncio
async def test_parse_tasks_non_task_returns_empty_list() -> None:
    """Verifies REQ-AI-02: Non-task input (chitchat/noise) returning tasks: [] returns []."""
    mock_client = AsyncMock()
    mock_client.models.generate_content.return_value = AsyncMock(
        parsed=TaskExtractionResult(tasks=[])
    )

    tasks = await parse_tasks_from_text(
        text="Привіт, як справи? Яка сьогодні погода?",
        client=mock_client,
    )
    assert tasks == []


@pytest.mark.asyncio
async def test_parse_tasks_malformed_json_returns_empty_list() -> None:
    """Verifies REQ-AI-02: Malformed response text is handled gracefully and returns []."""
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.parsed = None
    mock_response.text = "This is not valid json at all!"
    mock_client.models.generate_content.return_value = mock_response

    tasks = await parse_tasks_from_text(
        text="Будь-який текст",
        client=mock_client,
    )
    assert tasks == []


@pytest.mark.asyncio
async def test_parse_tasks_api_exception_returns_empty_list() -> None:
    """Verifies REQ-AI-02: Gemini API network/service errors are handled gracefully and return []."""
    mock_client = AsyncMock()
    mock_client.models.generate_content.side_effect = RuntimeError("Gemini quota exceeded")

    tasks = await parse_tasks_from_text(
        text="Терміново зробити реліз",
        client=mock_client,
    )
    assert tasks == []


@pytest.mark.asyncio
async def test_parse_tasks_client_initialization_failure_returns_empty_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verifies REQ-AI-02: Client initialization failure when GEMINI_API_KEY unset returns []."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    tasks = await parse_tasks("Завдання без переданого клієнта", client=None)
    assert tasks == []


@pytest.mark.asyncio
async def test_parse_tasks_default_model_used() -> None:
    """Verifies REQ-AI-02: parse_tasks uses gemini-3.5-flash as DEFAULT_MODEL."""
    assert DEFAULT_MODEL == "gemini-3.5-flash"
    mock_client = AsyncMock()
    mock_client.models.generate_content.return_value = AsyncMock(
        parsed=TaskExtractionResult(tasks=[])
    )

    await parse_tasks_from_text("тест", client=mock_client)

    call_kwargs = mock_client.models.generate_content.call_args.kwargs
    assert call_kwargs["model"] == "gemini-3.5-flash"
    assert call_kwargs["config"].response_mime_type == "application/json"
    assert call_kwargs["config"].response_schema == TaskExtractionResult
