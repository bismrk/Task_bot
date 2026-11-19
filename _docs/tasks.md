# Project Backlog: Telegram Task Tracker Bot & Mini App

## 1. Project Setup and Test Harness

### Goal

Initialize the project foundation and dependency management using `uv`, scaffold the modular directory structure defined in `_docs/schema.md`, and establish an automated test harness with a passing pytest smoke test.

### Acceptance criteria

- [ ] `pyproject.toml` exists in the repository root with project metadata, `requires-python = ">=3.11"`, and pytest configuration.
- [ ] Core dependencies specified in `pyproject.toml` include `aiogram>=3.0`, `fastapi`, `uvicorn`, `sqlalchemy>=2.0`, `aiosqlite`, `pydantic>=2.0`, `pydantic-settings`, `apscheduler`, and `google-genai`.
- [ ] Development/test dependencies specified in `pyproject.toml` include `pytest` and `pytest-asyncio`.
- [ ] Running `uv sync` resolves all dependencies without conflict, exits with returncode 0, and generates `uv.lock`.
- [ ] Pytest configuration under `[tool.pytest.ini_options]` in `pyproject.toml` configures `testpaths = ["tests"]`, `pythonpath = [".", "src"]`, and `asyncio_mode = "auto"`.
- [ ] Project directory structure matching `_docs/schema.md` is created under `src/` with packages initialized via `__init__.py` files: `src/core/`, `src/models/`, `src/schemas/`, `src/services/`, `src/bot/handlers/`, `src/bot/keyboards/`, `src/bot/middlewares/`, `src/scheduler/`, and `src/api/routes/`.
- [ ] Test directory structure matching `_docs/testing-guidelines.md` is present: `tests/` contains `conftest.py`, `test_smoke.py`, and empty subdirectories `tests/unit/` and `tests/integration/` tracked via `.gitkeep` or `__init__.py`.
- [ ] `tests/test_smoke.py` contains a test function that imports core packages (`aiogram`, `fastapi`, `sqlalchemy`, `aiosqlite`, `pydantic`, `apscheduler`, `google.genai`) and asserts they are successfully loaded.
- [ ] `tests/test_smoke.py` contains an asynchronous test marked with `@pytest.mark.asyncio` verifying that async execution under pytest-asyncio passes.
- [ ] Running `uv run pytest` discovers and executes all tests in `tests/test_smoke.py`, completing with 0 errors, 0 failures, and exit code 0.
- [ ] Running `uv run pytest tests/test_smoke.py` executes only the smoke test file and passes with exit code 0.
- [ ] No database schema, business logic, bot handlers, or API route logic is implemented in this task.

### Out of scope

- Database engine configuration, WAL mode PRAGMA listeners, and declarative SQLAlchemy models, moved to #2
- User service layer and timezone management logic, moved to #3
- Gemini AI client wrapper, audio byte ingestion, and structured parser, moved to #4
- Task management CRUD service and midnight rollover logic, moved to #5
- Telegram bot dispatcher setup and `/start` command handler, moved to #6
- Voice and text bot ingestion handlers with inline confirmation keyboards, moved to #7
- Midnight rollover interactive dialogue, moved to #8
- FastAPI backend initialization and Telegram WebApp initData authentication, moved to #9
- Mini App REST API endpoints for tasks, moved to #10
- Frontend React + Vite + Tailwind Mini App scaffold, moved to #11
- APScheduler timezone-aware background jobs, moved to #13

### Constraints

- Files this should stay inside: `pyproject.toml`, `uv.lock`, `src/**/__init__.py`, `tests/conftest.py`, `tests/test_smoke.py`, `tests/unit/.gitkeep`, `tests/integration/.gitkeep`
- Libraries and tools to use: `uv` for package management, `pytest` and `pytest-asyncio` for test runner
- Dependencies must strictly be defined in `pyproject.toml` per `Agents.md`
- Follow testing conventions in `_docs/testing-guidelines.md`
- Follow modular architecture defined in `_docs/schema.md`
- Do not write any application business logic, models, or bot/API handlers

## 2. Database Engine and Base Models Setup

### Goal

Configure an asynchronous SQLAlchemy 2.0 database engine with SQLite WAL mode, foreign key enforcement, and busy timeout PRAGMAs, and define declarative base models for `User` and `Task` with asynchronous table initialization utilities and automated tests.

### Acceptance criteria

- [ ] `src/models/base.py` defines `Base` inheriting from SQLAlchemy 2.0 `DeclarativeBase`.
- [ ] `src/models/user.py` defines the `User` model mapped to table name `users`.
- [ ] `User.telegram_id` is defined as `BigInteger`, primary key, non-nullable (REQ-USR-01).
- [ ] `User.timezone` is defined as `String`, non-nullable, defaulting to `"Europe/Kyiv"` (REQ-USR-01).
- [ ] `User.created_at` is defined as timezone-aware UTC datetime (`DateTime(timezone=True)`), defaulting to the current UTC time (REQ-USR-01).
- [ ] `User.tasks` defines a one-to-many relationship with `Task` using `back_populates="user"` and cascade delete option `cascade="all, delete-orphan"`.
- [ ] `src/models/task.py` defines `TaskStatus` enum with values `todo`, `done`, `canceled` and `TaskPriority` enum with values `low`, `medium`, `high`.
- [ ] `src/models/task.py` defines the `Task` model mapped to table name `tasks` (REQ-TSK-01).
- [ ] `Task.id` is defined as an integer primary key with autoincrement (REQ-TSK-01).
- [ ] `Task.user_id` is defined as `BigInteger`, non-nullable, indexed foreign key referencing `users.telegram_id` with `ondelete="CASCADE"` (REQ-TSK-01).
- [ ] `Task.title` is defined as `String(255)`, non-nullable (REQ-TSK-01).
- [ ] `Task.status` is defined with type `TaskStatus`, non-nullable, defaulting to `TaskStatus.todo` (`"todo"`) (REQ-TSK-01).
- [ ] `Task.priority` is defined with type `TaskPriority`, non-nullable, defaulting to `TaskPriority.medium` (`"medium"`) (REQ-TSK-01).
- [ ] `Task.tag` is defined as an optional `String(50)`, nullable=True (REQ-TSK-01).
- [ ] `Task.target_date` is defined as `Date` (YYYY-MM-DD), non-nullable, indexed (REQ-TSK-01).
- [ ] `Task.deadline_at` is defined as an optional timezone-aware UTC datetime (`DateTime(timezone=True)`), nullable=True (REQ-TSK-01).
- [ ] `Task.recurrence` is defined as an optional `String`, nullable=True (supporting format strings like `daily` or `weekdays:[0,1,2,3,4,5,6]`) (REQ-TSK-01).
- [ ] `Task.reminder_sent_1h` is defined as `Boolean`, non-nullable, defaulting to `False` (REQ-TSK-01).
- [ ] `Task.reminder_sent_10m` is defined as `Boolean`, non-nullable, defaulting to `False` (REQ-TSK-01).
- [ ] `Task.created_at` is defined as timezone-aware UTC datetime (`DateTime(timezone=True)`), defaulting to the current UTC time (REQ-TSK-01).
- [ ] `Task.user` defines a relationship to `User` using `back_populates="tasks"`.
- [ ] `src/models/__init__.py` imports and exposes `Base`, `User`, `Task`, `TaskStatus`, and `TaskPriority`.
- [ ] `src/core/database.py` defines an asynchronous SQLAlchemy engine using `create_async_engine` configured for SQLite via `aiosqlite` with default URL `sqlite+aiosqlite:///tasks.db` or configured via environment settings (REQ-NFR-01).
- [ ] `src/core/database.py` registers a connection event listener on the engine that executes `PRAGMA foreign_keys=ON`, `PRAGMA busy_timeout=5000`, and `PRAGMA journal_mode=WAL` (REQ-NFR-01).
- [ ] `src/core/database.py` defines `async_sessionmaker` configured with `expire_on_commit=False` and `class_=AsyncSession`.
- [ ] `src/core/database.py` defines an async context manager or generator `get_session()` providing an `AsyncSession` for transactions.
- [ ] `src/core/database.py` defines an async function `init_db(engine=...)` that creates all tables in metadata (`Base.metadata.create_all`).
- [ ] `tests/conftest.py` provides an async fixture `db_session` providing an isolated in-memory SQLite async session with all tables created.
- [ ] `tests/unit/test_database.py` contains automated tests verifying `PRAGMA foreign_keys` is enabled (`1`) and `PRAGMA busy_timeout` is set to `5000` on connections.
- [ ] `tests/unit/test_database.py` contains automated tests verifying `User` creation with default timezone `"Europe/Kyiv"` and timestamp.
- [ ] Automated tests verify `Task` creation with default status `todo`, priority `medium`, and reminder flags set to `False`.
- [ ] Automated tests verify foreign key constraint enforcement: inserting a `Task` with an unpersisted `user_id` raises an `IntegrityError`.
- [ ] Automated tests verify cascade delete: deleting a `User` record automatically cascades and removes all associated `Task` records.
- [ ] All tests run with `uv run pytest` and pass with 0 errors and 0 failures.

### Out of scope

- User registration command handling, user profile retrieval, and timezone update service logic, moved to #3
- Task CRUD service functions, rollover logic, and date filtering queries, moved to #5
- Gemini AI client, audio ingestion, and structured parser service, moved to #4
- Telegram bot dispatcher setup and `/start` onboarding command handler, moved to #6
- Voice and text bot ingestion handlers with inline confirmation keyboards, moved to #7
- Midnight rollover interactive dialogue, moved to #8
- FastAPI backend initialization and Telegram WebApp initData authentication, moved to #9
- Mini App REST API endpoints for tasks, moved to #10
- Frontend React + Vite + Tailwind Mini App scaffold, moved to #11
- APScheduler timezone-aware background jobs, moved to #13
- Deadline notification background reminders, moved to #14

### Constraints

- Files this should stay inside: `src/core/database.py`, `src/core/__init__.py`, `src/models/base.py`, `src/models/user.py`, `src/models/task.py`, `src/models/__init__.py`, `tests/conftest.py`, `tests/unit/test_database.py`
- Libraries to use: `sqlalchemy>=2.0` (Mapped, mapped_column, DeclarativeBase, async_sessionmaker, create_async_engine), `aiosqlite`, `pytest`, `pytest-asyncio`
- Do not add new dependencies without explicit permission per `Agents.md`
- Follow testing conventions in `_docs/testing-guidelines.md` (isolated in-memory SQLite `sqlite+aiosqlite:///:memory:`, `@pytest.mark.asyncio`, REQ docstrings)
- Follow modular architecture defined in `_docs/schema.md`
- Do not implement business logic services, bot handlers, or API routes in this task

## 3. User Service and Timezone Management

### Goal

Implement the user service layer and Pydantic schemas providing asynchronous functions to register, retrieve, and update user profiles, validate IANA timezones with `zoneinfo`, and convert datetimes to user local time with complete unit test coverage.

### Acceptance criteria

- [ ] `src/schemas/user.py` defines Pydantic models `UserBase`, `UserCreate`, `UserUpdate`, and `UserRead`.
- [ ] `UserBase` defines `timezone: str = "Europe/Kyiv"` with a field validator checking validity via `zoneinfo.ZoneInfo` and raising `ValueError` on invalid timezone strings.
- [ ] `UserCreate` defines `telegram_id: int` and inherits `timezone: str = "Europe/Kyiv"`.
- [ ] `UserUpdate` defines `timezone: str` with a field validator checking validity via `zoneinfo.ZoneInfo` and raising `ValueError` on invalid timezone strings.
- [ ] `UserRead` defines `telegram_id: int`, `timezone: str`, and `created_at: datetime`, configured with `model_config = ConfigDict(from_attributes=True)`.
- [ ] `src/schemas/__init__.py` imports and exposes `UserBase`, `UserCreate`, `UserUpdate`, and `UserRead`.
- [ ] `src/services/user_service.py` defines `validate_timezone(timezone: str) -> str` that validates IANA timezone strings using `zoneinfo.ZoneInfo(timezone)` and raises `ValueError(f"Invalid timezone: {timezone}")` for invalid identifiers (REQ-USR-02).
- [ ] `src/services/user_service.py` defines async `get_user(session: AsyncSession, telegram_id: int) -> User | None` returning the `User` database record if found, or `None` if the user does not exist.
- [ ] `src/services/user_service.py` defines async `get_or_create_user(session: AsyncSession, telegram_id: int, timezone: str = "Europe/Kyiv") -> tuple[User, bool]` that inserts and commits a new `User` with default timezone `"Europe/Kyiv"` and returns `(user, True)` if no user exists for `telegram_id` (REQ-USR-01).
- [ ] `get_or_create_user` is idempotent: calling it for an existing user returns `(user, False)` without overwriting the user's existing timezone or modifying other attributes (REQ-USR-01).
- [ ] Calling `get_or_create_user` with an invalid timezone string for a non-existent user raises `ValueError` and does not insert any user record into the database.
- [ ] `src/services/user_service.py` defines async `update_user_timezone(session: AsyncSession, telegram_id: int, timezone: str) -> User` that updates `user.timezone`, commits the transaction, and returns the updated `User` when given a valid IANA timezone (REQ-USR-02).
- [ ] Calling `update_user_timezone` with an invalid timezone string (e.g. `"Mars/Olympus"`) raises `ValueError`, aborts modification, and preserves the user's previous timezone in the database (REQ-USR-02).
- [ ] Calling `update_user_timezone` for a non-existent `telegram_id` raises `ValueError` indicating the user does not exist.
- [ ] `src/services/user_service.py` defines `get_user_local_time(user: User, dt: datetime | None = None) -> datetime` returning a timezone-aware datetime in `user.timezone`.
- [ ] `get_user_local_time` uses `datetime.now(timezone.utc)` when `dt is None`.
- [ ] `get_user_local_time` treats naive datetime inputs as UTC before converting to `user.timezone`.
- [ ] `src/services/__init__.py` imports and exposes `get_user`, `get_or_create_user`, `update_user_timezone`, `get_user_local_time`, and `validate_timezone`.
- [ ] `tests/unit/test_user_service.py` contains automated tests using the in-memory SQLite fixture `db_session` verifying new user creation via `get_or_create_user` with default `"Europe/Kyiv"` timezone (REQ-USR-01).
- [ ] `tests/unit/test_user_service.py` contains automated tests verifying `get_or_create_user` idempotency and preservation of existing custom timezones (REQ-USR-01).
- [ ] `tests/unit/test_user_service.py` contains automated tests verifying `get_or_create_user` with invalid timezone raises `ValueError` and does not persist data.
- [ ] `tests/unit/test_user_service.py` contains automated tests verifying `get_user` returns `User` for existing records and `None` for non-existent records.
- [ ] `tests/unit/test_user_service.py` contains automated tests verifying `update_user_timezone` successfully updates and commits valid IANA timezones (REQ-USR-02).
- [ ] `tests/unit/test_user_service.py` contains automated tests verifying `update_user_timezone` with invalid timezone raises `ValueError` and leaves the database record unmodified (REQ-USR-02).
- [ ] `tests/unit/test_user_service.py` contains automated tests verifying `update_user_timezone` for non-existent user raises `ValueError`.
- [ ] `tests/unit/test_user_service.py` contains automated tests verifying `get_user_local_time` with default (`None`), explicit UTC, and naive datetimes.
- [ ] `tests/unit/test_user_service.py` contains automated tests verifying Pydantic models `UserCreate`, `UserUpdate`, and `UserRead` validation and serialization.
- [ ] All test functions in `tests/unit/test_user_service.py` contain docstrings referencing requirement IDs (e.g. `REQ-USR-01`, `REQ-USR-02`) per testing guidelines.
- [ ] Running `uv run pytest` discovers and executes all tests in `tests/unit/test_user_service.py` and passes with 0 errors and 0 failures.

### Out of scope

- Telegram bot `/start` command registration handler and onboarding welcome message, moved to #6
- Custom notification preferences, reminder interval settings, and `/settings` bot/Mini App UI, moved to #17
- Task management CRUD operations and rollover logic, moved to #5
- Gemini AI client, audio ingestion, and structured parser service, moved to #4
- Voice and text message handlers with confirmation buttons, moved to #7
- Midnight rollover interactive dialogue flow (00:00), moved to #8
- FastAPI backend initialization and Telegram WebApp initData authentication, moved to #9
- Mini App REST API endpoints for tasks, moved to #10
- Frontend React + Vite + Tailwind Mini App setup, moved to #11
- APScheduler timezone-aware background jobs (00:00 & 09:00 triggers), moved to #13
- Deadline notification reminders (-1h & -10m), moved to #14

### Constraints

- Files this should stay inside: `src/schemas/user.py`, `src/schemas/__init__.py`, `src/services/user_service.py`, `src/services/__init__.py`, `tests/unit/test_user_service.py`
- Libraries to use: `zoneinfo` (Python standard library), `datetime` (Python standard library), `pydantic>=2.0` (`BaseModel`, `ConfigDict`, `field_validator`), `sqlalchemy>=2.0` (`select`, `AsyncSession`), `pytest`, `pytest-asyncio`
- Do not add new dependencies to `pyproject.toml` without asking per `Agents.md`
- Follow testing conventions in `_docs/testing-guidelines.md` (isolated in-memory SQLite fixture `db_session`, `@pytest.mark.asyncio`, REQ docstrings)
- Follow modular architecture defined in `_docs/schema.md`
- Do not implement bot handlers, API endpoints, or background scheduler jobs in this task

## 4. Gemini AI Voice and Text Parser Service

### Goal

Build the Gemini AI client initialization, Pydantic schemas, and parser service to extract structured tasks (title, target date, deadline, priority, tag) from plain text and raw Telegram `.ogg` Opus audio bytes using Gemini 2.5 Flash structured outputs, with timezone-aware prompt contextualization, graceful edge case handling, and 100% mocked unit tests.

### Acceptance criteria

- [ ] `src/schemas/task.py` defines `ExtractedTask` model inheriting from Pydantic `BaseModel`.
- [ ] `ExtractedTask.title` is defined as a non-empty string (`str`), stripped of leading and trailing whitespace, with a maximum length of 255 characters (REQ-AI-02).
- [ ] `ExtractedTask.target_date` is defined as `datetime.date` (YYYY-MM-DD) representing the calendar date the task is planned for (REQ-AI-02).
- [ ] `ExtractedTask.deadline_at` is defined as optional timezone-aware `datetime.datetime | None = None` (in UTC or with user timezone offset) if a specific time was mentioned, or `None` if no time was mentioned (REQ-AI-02).
- [ ] `ExtractedTask.priority` is defined with type `TaskPriority` (values: `low`, `medium`, `high`) defaulting to `TaskPriority.medium` (REQ-AI-02).
- [ ] `ExtractedTask.tag` is defined as optional `str | None = None` (maximum length 50 characters) stripped of any leading `#` symbol (e.g., `"робота"`), or `None` if no category was mentioned (REQ-AI-02).
- [ ] `src/schemas/task.py` defines `TaskExtractionResult` model inheriting from Pydantic `BaseModel` containing `tasks: list[ExtractedTask] = Field(default_factory=list)` (REQ-AI-02).
- [ ] `src/schemas/__init__.py` imports and exposes `ExtractedTask` and `TaskExtractionResult`.
- [ ] `src/core/ai_client.py` defines `get_ai_client(api_key: str | None = None) -> genai.Client` that initializes and returns a `google.genai.Client` using the provided `api_key` or reading from the `GEMINI_API_KEY` environment variable.
- [ ] Calling `get_ai_client()` when `GEMINI_API_KEY` is unset and no `api_key` parameter is provided raises `ValueError("GEMINI_API_KEY environment variable is not set")`.
- [ ] `src/core/__init__.py` imports and exposes `get_ai_client`.
- [ ] `src/services/ai_parser.py` defines `DEFAULT_MODEL: str = "gemini-2.5-flash"`.
- [ ] `src/services/ai_parser.py` defines async `parse_tasks(content: str | bytes, mime_type: str = "text/plain", user_timezone: str = "Europe/Kyiv", reference_time: datetime | None = None, client: genai.Client | None = None) -> list[ExtractedTask]` supporting both text (`str`) and audio bytes (`bytes`).
- [ ] `src/services/ai_parser.py` defines async `parse_tasks_from_text(text: str, user_timezone: str = "Europe/Kyiv", reference_time: datetime | None = None, client: genai.Client | None = None) -> list[ExtractedTask]` for text-based task extraction.
- [ ] `src/services/ai_parser.py` defines async `parse_tasks_from_audio(audio_bytes: bytes, mime_type: str = "audio/ogg", user_timezone: str = "Europe/Kyiv", reference_time: datetime | None = None, client: genai.Client | None = None) -> list[ExtractedTask]` for audio-based task extraction (REQ-AI-01).
- [ ] `parse_tasks` constructs a prompt / system instruction incorporating the user's local reference time (formatted as date, time, and day of week) and timezone identifier so relative expressions ("сьогодні", "завтра", "післязавтра", "у п'ятницю", "о 15:00") resolve to exact calendar dates and timezone-aware deadlines (REQ-AI-02).
- [ ] `parse_tasks` configures Gemini generation using `types.GenerateContentConfig` with `response_mime_type="application/json"` and `response_schema=TaskExtractionResult`.
- [ ] When passed audio bytes (`bytes`), `parse_tasks` packages the audio payload in-memory using `types.Part.from_bytes(data=content, mime_type=mime_type)` (default `mime_type="audio/ogg"`) without saving files to disk (REQ-AI-01).
- [ ] Calling `parse_tasks` (or `parse_tasks_from_text`) with an empty or whitespace-only string returns an empty list `[]` immediately without invoking the Gemini client.
- [ ] Calling `parse_tasks` (or `parse_tasks_from_audio`) with empty audio bytes `b""` returns an empty list `[]` immediately without invoking the Gemini client.
- [ ] When Gemini returns an extraction result with `tasks: []` (input contains chit-chat, questions, background noise, or no actionable tasks), `parse_tasks` returns an empty list `[]` without raising an exception (REQ-AI-02).
- [ ] If the Gemini response cannot be parsed into `TaskExtractionResult` or is malformed, `parse_tasks` catches the failure, logs an error, and returns an empty list `[]`.
- [ ] If the Gemini API call encounters a network or service error, `parse_tasks` catches the error, logs it, and handles it gracefully without an unhandled crash.
- [ ] When relative dates and specific times are specified (e.g. "Завтра о 15:00 здати звіт"), `deadline_at` is returned as a timezone-aware datetime matching the user's timezone converted to UTC (REQ-AI-02).
- [ ] When task text indicates priority (e.g. "терміново", "важливо", "високий пріоритет"), `priority` is set to `TaskPriority.high`; for "низький" to `TaskPriority.low`; and defaults to `TaskPriority.medium` (REQ-AI-02).
- [ ] Extracted tags are stripped of `#` prefixes, normalized, and trimmed to a maximum of 50 characters (REQ-AI-02).
- [ ] `src/services/__init__.py` imports and exposes `parse_tasks`, `parse_tasks_from_text`, and `parse_tasks_from_audio`.
- [ ] `tests/unit/test_ai_parser.py` contains unit tests verifying `get_ai_client()` behavior with and without `GEMINI_API_KEY`.
- [ ] `tests/unit/test_ai_parser.py` contains unit tests verifying `ExtractedTask` and `TaskExtractionResult` validation, defaults, and serialization.
- [ ] `tests/unit/test_ai_parser.py` contains unit tests verifying `parse_tasks_from_text` extraction of single and multiple tasks with title, target_date, deadline_at, priority, and tag (REQ-AI-02).
- [ ] `tests/unit/test_ai_parser.py` contains unit tests verifying timezone-aware relative date resolution in prompt generation (REQ-AI-02).
- [ ] `tests/unit/test_ai_parser.py` contains unit tests verifying `parse_tasks_from_audio` packaging of `audio/ogg` bytes with `types.Part.from_bytes` (REQ-AI-01).
- [ ] `tests/unit/test_ai_parser.py` contains unit tests verifying that empty text, whitespace text, and empty audio bytes return `[]` without making API calls.
- [ ] `tests/unit/test_ai_parser.py` contains unit tests verifying non-task inputs (filler/noise) return `[]` without exceptions (REQ-AI-02).
- [ ] `tests/unit/test_ai_parser.py` contains unit tests verifying malformed API responses and API exceptions are handled cleanly.
- [ ] All unit tests in `tests/unit/test_ai_parser.py` mock `google.genai.Client` and make 0 real network calls per `_docs/testing-guidelines.md`.
- [ ] All test functions contain docstrings referencing requirement IDs (`REQ-AI-01`, `REQ-AI-02`).
- [ ] Running `uv run pytest tests/unit/test_ai_parser.py` executes all AI parser tests and passes with 0 errors and 0 failures.
- [ ] Running `uv run pytest` executes the complete test suite and passes with 0 errors and 0 failures.

### Out of scope

- Telegram voice note file download from Telegram API and aiogram audio handlers, moved to #7
- Telegram bot inline keyboard generation (`[✅ Зберегти]`, `[✏️ Виправити]`) and confirmation callbacks, moved to #7
- Task database entity persistence, CRUD database operations, and rollover queries, moved to #5
- Telegram bot dispatcher setup and `/start` onboarding command, moved to #6
- Midnight rollover interactive dialogue flow (00:00 "Хвости"), moved to #8
- FastAPI backend initialization and Telegram WebApp initData authentication, moved to #9
- Mini App REST API endpoints for tasks, moved to #10
- Frontend React Mini App checklist and task creation UI, moved to #11, #12
- APScheduler timezone-aware background jobs (00:00 review & 09:00 push), moved to #13
- Scheduled deadline proximity push notifications (-1h and -10m), moved to #14

### Constraints

- Files this should stay inside: `src/core/ai_client.py`, `src/core/__init__.py`, `src/schemas/task.py`, `src/schemas/__init__.py`, `src/services/ai_parser.py`, `src/services/__init__.py`, `tests/unit/test_ai_parser.py`
- Libraries to use: `google-genai` (`from google import genai`, `from google.genai import types`), `pydantic>=2.0` (`BaseModel`, `Field`, `field_validator`, `ConfigDict`), `datetime` and `zoneinfo` (Python standard library), `pytest`, `pytest-asyncio`, `unittest.mock` (`AsyncMock`, `MagicMock`, `patch`)
- Do not add new dependencies to `pyproject.toml` without explicit permission per `Agents.md`
- Never make real network requests to Google Gemini or Telegram in automated tests per `_docs/testing-guidelines.md`
- Follow modular architectural structure defined in `_docs/schema.md`
- Do not implement database persistence, bot handlers, or API endpoints in this task

## 5. Task Management CRUD Service
Goal: Provide core business logic to create, read, update, complete, and rollover tasks.
Description: Implement an async task service with functions to create tasks, retrieve tasks filtered by user and target date, update task statuses (`todo`, `done`, `canceled`), and manage recurrence tags. Include a dedicated method to query uncompleted tasks from previous days ("хвости") and batch-update them to rollover to a new date or mark them closed. Write unit tests verifying task state transitions, recurrence handling, and date filtering.

## 6. Telegram Bot Dispatcher and /start Command
Goal: Initialize the aiogram 3 bot dispatcher and implement the user onboarding flow.
Description: Scaffold the `aiogram 3.x` bot application with dependency injection for database sessions and configuration settings. Implement the `/start` command handler to register new users into the database, assign a default timezone, and reply with an introductory welcome message outlining bot capabilities. Write tests or verification scripts to ensure the dispatcher boots and processes the command cleanly.

## 7. Voice and Text Ingestion Bot Handlers
Goal: Connect incoming Telegram voice notes and text messages to the AI parser with confirmation buttons.
Description: Implement `aiogram 3` message handlers for voice notes and text messages that download the audio buffer or read text and pass it to the AI parser service. Format the extracted tasks into an interactive message accompanied by inline keyboard buttons (`Зберегти` / `Виправити`). Save confirmed tasks into the database and notify the user with a formatted confirmation upon button click.

## 8. Midnight Rollover Flow (00:00 "Хвости")
Goal: Build the interactive Telegram dialogue for reviewing uncompleted tasks at midnight.
Description: Implement a bot dialogue handler that displays a user's uncompleted tasks from the day with inline buttons allowing each task to be either closed or postponed to tomorrow. Follow the review by prompting the user to record or type tomorrow's task plan. Provide mock test scenarios demonstrating state management during the rollover review conversation.

## 9. FastAPI Backend Initialization and Telegram initData Auth
Goal: Set up the FastAPI server with middleware and secure Telegram Mini App authentication.
Description: Initialize the FastAPI application with CORS middleware, shared asynchronous database session dependencies, and health check endpoints. Implement an authentication dependency that verifies the Telegram WebApp `initData` HMAC-SHA256 signature against the bot token and extracts the authenticated user ID. Write unit tests testing endpoint access with valid, expired, and tampered `initData` parameters.

## 10. Task REST API Endpoints for Mini App
Goal: Expose REST endpoints for retrieving, creating, updating, and toggling tasks from the Mini App.
Description: Develop authenticated FastAPI endpoints to retrieve tasks for a given date, create new tasks, update existing task details, and toggle completion statuses. Ensure all endpoints filter and mutate records strictly for the user authenticated via `initData`. Include API integration tests verifying request validation and response payload schemas.

## 11. Telegram Mini App Frontend Setup
Goal: Initialize the React Mini App with Vite, Tailwind CSS, and Telegram WebApp SDK integration.
Description: Scaffold a React application using Vite, Tailwind CSS, and `@telegram-apps/sdk-react` to support native Telegram color schemes and viewport expansion. Set up an API client with Axios or Fetch that automatically retrieves `initData` from the Telegram SDK and attaches it to authorization headers. Verify that the build succeeds and renders an initial greeting screen inside Telegram WebApp desktop and mobile clients.

## 12. Mini App Interactive Today Checklist
Goal: Implement the primary interactive checklist interface with strikethrough, tags, and recurrence.
Description: Build the main Mini App checklist screen featuring task cards with strikethrough completion checkboxes, priority badges, tags, and deadline countdown indicators. Add interactive controls to toggle completion status, set recurrence (daily / specific weekdays), and launch a quick task-creation modal. Connect UI events to the FastAPI backend with optimistic UI updates for responsive user feedback.

## 13. Timezone-Aware Background Scheduler (00:00 & 09:00 Triggers)
Goal: Implement APScheduler background jobs that trigger midnight reviews and morning pushes per user timezone.
Description: Configure `APScheduler` with an async job runner that checks all user timezones periodically and fires events when a user reaches 00:00 or 09:00 local time. Dispatch the 00:00 rollover review dialogue and the 09:00 morning push with an inline button to launch the Telegram Mini App. Ensure job execution is idempotent to prevent duplicate messages across application restarts.

## 14. Deadline Notification Reminders (-1 Hour & -10 Minutes)
Goal: Implement background reminders for upcoming task deadlines.
Description: Create a scheduled periodic task in `APScheduler` that queries for pending tasks whose deadlines fall within 1 hour or 10 minutes from the current time. Dispatch proactive Telegram notification messages to the respective user with inline buttons to mark the task completed or snooze the reminder. Persist reminder dispatch flags in the database to prevent duplicate alerts.

## 15. Mini App Calendar View
Goal: Build an interactive calendar in the Mini App to navigate and inspect tasks on any selected date.
Description: Create a calendar UI component in the Mini App allowing users to pick any day of the month and view that date's task list and completion status. Add a supporting FastAPI endpoint that provides task counts and completion ratios per day for the selected month to render activity indicators on the calendar. Test date navigation across month boundaries and different user timezones.

## 16. Mini App Productivity Dashboard and Streaks
Goal: Develop an analytics dashboard with productivity charts, tag breakdown, and daily streaks.
Description: Create a dashboard view in the Mini App featuring metric cards for completion rate and current daily streak, alongside `Recharts` graphs showing daily productivity trends and tag distributions. Implement the supporting FastAPI analytics endpoint that calculates metrics from task history. Validate chart rendering and responsive layout across mobile screen sizes.

## 17. User Settings in Mini App and Bot
Goal: Provide interfaces in both the Mini App and Bot to configure timezones, check-in hours, and deadline alerts.
Description: Build a settings screen in the Mini App and a `/settings` command handler in the Telegram bot allowing users to select their timezone from a list and customize reminder intervals. Persist updated preferences in the database and synchronize scheduler targets accordingly. Ensure the settings form validates timezone identifiers and reminder time ranges.

## 18. End-to-End Integration, Packaging, and Deployment Verification
Goal: Connect all components into a unified runnable application with documentation and deployment configuration.
Description: Configure a unified startup script or Docker Compose setup that runs the FastAPI backend (serving static Mini App assets), the aiogram bot, and the APScheduler instance. Verify the full user journey from voice message ingestion to Mini App checklist interaction and scheduled notification delivery. Update documentation with step-by-step setup, environment variable guidance, and local testing instructions.
