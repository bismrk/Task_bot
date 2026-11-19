# Testing Guidelines

This document outlines the testing strategy, standards, and practices for the Telegram Task Tracker Bot project.
All agents and developers must read this document before writing tests, as mandated by `Agents.md`.

---

## 1. Core Principles

1. **Process Alignment:**
   - Per `_docs/process.md`, always read the **Acceptance Criteria** in `_docs/requirements.md` before starting a task and verify all criteria pass before closing the issue.
   - Commit regularly and ensure all tests pass (`uv run pytest`) before committing.

2. **Test Independence & Speed:**
   - Tests must run independently and in any order without side effects or leaking database state.
   - Database tests must execute against an isolated in-memory SQLite database (`sqlite+aiosqlite:///:memory:`).
   - Fast execution: the entire unit test suite should finish in seconds.

3. **External Service Isolation:**
   - **Never** make real network requests to Telegram or Google Gemini during test runs.
   - Use mocks or stubs for `aiogram.Bot` methods and `google.genai.Client` calls.

---

## 2. Test Commands

Run all tests through `uv`:

```bash
# Run the complete test suite
uv run pytest

# Run a single test file
uv run pytest tests/test_smoke.py

# Run a specific test function
uv run pytest tests/test_user_service.py -k "test_create_user"

# Run tests with detailed output and local variable printouts on failure
uv run pytest -v --showlocals
```

---

## 3. Directory Structure

```
tests/
├── conftest.py               # Shared fixtures (async db engine, test session, mock clients)
├── unit/                     # Unit tests for isolated business logic and utilities
│   ├── test_ai_parser.py     # Gemini extraction logic with mocked responses
│   ├── test_task_service.py  # Task CRUD, status toggling, date filters
│   └── test_user_service.py  # User creation, timezone validation
├── integration/              # Integration tests for combined layers
│   ├── test_bot_handlers.py  # aiogram message and callback routing
│   ├── test_api_routes.py    # FastAPI endpoints with initData auth headers
│   └── test_scheduler.py     # APScheduler timezone-aware jobs
└── test_smoke.py             # Minimal environment and sanity check
```

---

## 4. Asynchronous Testing Conventions

* Always mark async test functions with `@pytest.mark.asyncio`:
```python
import pytest

@pytest.mark.asyncio
async def test_user_creation_with_valid_timezone(db_session):
    # Given
    telegram_id = 123456789
    tz = "Europe/Kyiv"
    
    # When
    user = await user_service.create_user(db_session, telegram_id, tz)
    
    # Then
    assert user.telegram_id == telegram_id
    assert user.timezone == tz
```

---

## 5. Mocking Guidelines

### Mocking Telegram Bot
Do not instantiate real network sessions for `aiogram.Bot`. Use `unittest.mock.AsyncMock` or fake dispatcher contexts:
```python
from unittest.mock import AsyncMock

bot_mock = AsyncMock()
bot_mock.send_message.return_value = AsyncMock()
```

### Mocking Gemini API
Mock the `google.genai.Client` to return deterministic structured responses matching Pydantic output schemas:
```python
mock_client = AsyncMock()
mock_client.models.generate_content.return_value = AsyncMock(
    parsed=TaskExtractionResult(tasks=[...])
)
```

---

## 6. Acceptance Criteria Verification

Every test should be explicitly mapped to the corresponding requirement ID in `_docs/requirements.md` using docstrings:
```python
@pytest.mark.asyncio
async def test_invalid_timezone_rejected(db_session):
    """Verifies REQ-USR-02: Invalid timezone strings are rejected."""
    with pytest.raises(ValueError):
        await user_service.update_timezone(db_session, user_id=1, timezone="Mars/Olympus")
```
