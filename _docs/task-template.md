# Task Template

Use this template when creating tasks for the project backlog and GitHub Issues:

## <number>. <title>
Goal: <one line describing the objective>
Description: <two or three sentences detailing what the task involves, including relevant dependencies and components>
Acceptance Criteria: <reference to relevant REQ-XXX in _docs/requirements.md>

---

### Example:

## 1. Project Setup and Test Harness
Goal: Set up the project foundation, dependency management, and a passing automated test.
Description: Initialize the project structure using `uv` with dependencies specified in `pyproject.toml` (including `aiogram`, `fastapi`, `sqlalchemy`, `aiosqlite`, `pytest`, `pytest-asyncio`, and `pydantic`). Create a minimal smoke test using `pytest` that runs via `uv run pytest` and passes. Ensure the directory structure is prepared for modular application components per `_docs/schema.md` without adding business logic yet.
Acceptance Criteria: REQ-NFR-01
