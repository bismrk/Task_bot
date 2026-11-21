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

### Goal

Implement the task management CRUD service and Pydantic schemas providing asynchronous functions to create, read, update, complete, delete, query by date, and rollover tasks ("хвости") with strict tenant isolation, priority-aware ordering, and comprehensive unit test coverage.

### Acceptance criteria

- [ ] `src/schemas/task.py` defines `TaskCreate` schema inheriting from `BaseModel` with fields: `title: str` (max_length=255, non-empty, stripped), `target_date: date`, `deadline_at: datetime | None = None` (timezone-aware if present), `priority: TaskPriority = TaskPriority.medium`, `tag: str | None = None` (max_length=50, stripped of `#`), and `recurrence: str | None = None` (REQ-TSK-01).
- [ ] `src/schemas/task.py` defines `TaskUpdate` schema inheriting from `BaseModel` with optional fields for partial update: `title: str | None = None`, `target_date: date | None = None`, `deadline_at: datetime | None = None`, `priority: TaskPriority | None = None`, `tag: str | None = None`, `status: TaskStatus | None = None`, and `recurrence: str | None = None`.
- [ ] `src/schemas/task.py` defines `TaskRead` schema inheriting from `BaseModel` with fields: `id: int`, `user_id: int`, `title: str`, `status: TaskStatus`, `priority: TaskPriority`, `tag: str | None`, `target_date: date`, `deadline_at: datetime | None`, `recurrence: str | None`, `reminder_sent_1h: bool`, `reminder_sent_10m: bool`, and `created_at: datetime`, configured with `model_config = ConfigDict(from_attributes=True)`.
- [ ] Existing schemas `ExtractedTask` and `TaskExtractionResult` are preserved in `src/schemas/task.py`.
- [ ] `src/schemas/__init__.py` imports and exposes `TaskCreate`, `TaskUpdate`, `TaskRead`, `ExtractedTask`, and `TaskExtractionResult`.
- [ ] `src/services/task_service.py` defines async `create_task(session: AsyncSession, user_id: int, data: TaskCreate | ExtractedTask) -> Task` that persists a new task with `user_id=user_id`, `status=TaskStatus.todo`, `reminder_sent_1h=False`, `reminder_sent_10m=False`, and commits/flushes the record (REQ-TSK-01).
- [ ] Calling `create_task` with an `ExtractedTask` instance maps `title`, `target_date`, `deadline_at`, `priority`, `tag`, sets `recurrence=None`, and successfully creates the task.
- [ ] `src/services/task_service.py` defines async `create_tasks_batch(session: AsyncSession, user_id: int, tasks: list[TaskCreate | ExtractedTask]) -> list[Task]` that creates and persists multiple tasks in a single database transaction.
- [ ] Calling `create_tasks_batch` with an empty list `[]` returns an empty list `[]` immediately without executing database insert queries.
- [ ] `src/services/task_service.py` defines async `get_task(session: AsyncSession, task_id: int, user_id: int) -> Task | None` returning the `Task` database record if found and owned by `user_id`.
- [ ] Calling `get_task` with a `task_id` belonging to a different user returns `None`, enforcing tenant isolation (REQ-NFR-02).
- [ ] Calling `get_task` with a non-existent `task_id` returns `None`.
- [ ] `src/services/task_service.py` defines async `get_tasks_for_date(session: AsyncSession, user_id: int, target_date: date) -> list[Task]` retrieving tasks matching `user_id == user_id` and `target_date == target_date` (REQ-API-02).
- [ ] `get_tasks_for_date` orders results with `TaskStatus.todo` first sorted by priority (`TaskPriority.high` -> `TaskPriority.medium` -> `TaskPriority.low`), followed by `TaskStatus.done` tasks, then by creation time / ID.
- [ ] Calling `get_tasks_for_date` for a date with no matching tasks returns an empty list `[]`.
- [ ] `src/services/task_service.py` defines async `update_task(session: AsyncSession, task_id: int, user_id: int, data: TaskUpdate) -> Task` that updates only the fields provided in `data`, commits the transaction, and returns the updated `Task`.
- [ ] Calling `update_task` with a new `deadline_at` resets reminder flags `reminder_sent_1h = False` and `reminder_sent_10m = False`.
- [ ] Calling `update_task` for a `task_id` belonging to another user raises `ValueError("Task not found or access denied")` and leaves the database record unmodified (REQ-NFR-02).
- [ ] Calling `update_task` for a non-existent `task_id` raises `ValueError("Task not found or access denied")`.
- [ ] `src/services/task_service.py` defines async `toggle_task_status(session: AsyncSession, task_id: int, user_id: int, new_status: TaskStatus) -> Task` that updates `task.status = new_status`, commits, and returns the updated `Task` (REQ-TSK-02).
- [ ] Calling `toggle_task_status` for a `task_id` belonging to another user raises `ValueError("Task not found or access denied")` and does not change the task status (REQ-TSK-02, REQ-NFR-02).
- [ ] Calling `toggle_task_status` for a non-existent `task_id` raises `ValueError("Task not found or access denied")`.
- [ ] `src/services/task_service.py` defines async `delete_task(session: AsyncSession, task_id: int, user_id: int) -> bool` that deletes the task and returns `True` if found and owned by `user_id`.
- [ ] Calling `delete_task` for a `task_id` belonging to another user returns `False`, does not delete the task, and leaves the database unmodified (REQ-NFR-02).
- [ ] Calling `delete_task` for a non-existent `task_id` returns `False`.
- [ ] `src/services/task_service.py` defines async `get_overdue_tasks(session: AsyncSession, user_id: int, before_date: date) -> list[Task]` that retrieves all uncompleted tasks (`status == TaskStatus.todo`) where `target_date < before_date` belonging to `user_id`, ordered by `target_date ASC` then priority `high -> medium -> low` (REQ-SCH-01).
- [ ] `get_overdue_tasks` ignores tasks with status `TaskStatus.done` or `TaskStatus.canceled`, and ignores tasks on or after `before_date`.
- [ ] `get_overdue_tasks` strictly filters by `user_id` and does not return overdue tasks belonging to other users (REQ-NFR-02).
- [ ] Calling `get_overdue_tasks` when no overdue tasks exist returns an empty list `[]`.
- [ ] `src/services/task_service.py` defines async `rollover_task(session: AsyncSession, task_id: int, user_id: int, new_date: date) -> Task` that updates `task.target_date = new_date`, commits, and returns the updated `Task` (REQ-SCH-01).
- [ ] Calling `rollover_task` for a `task_id` belonging to another user raises `ValueError("Task not found or access denied")` and does not change `target_date` (REQ-NFR-02).
- [ ] Calling `rollover_task` for a non-existent `task_id` raises `ValueError("Task not found or access denied")`.
- [ ] `src/services/task_service.py` defines async `batch_rollover_tasks(session: AsyncSession, task_ids: list[int], user_id: int, new_date: date) -> list[Task]` that updates `target_date = new_date` for all tasks in `task_ids` owned by `user_id`, commits, and returns the list of updated `Task` instances (REQ-SCH-01).
- [ ] Calling `batch_rollover_tasks` with an empty `task_ids` list returns `[]` immediately without executing database updates.
- [ ] `batch_rollover_tasks` ignores any `task_id` in `task_ids` that belongs to another user without mutating other users' data (REQ-NFR-02).
- [ ] `src/services/__init__.py` imports and exposes `create_task`, `create_tasks_batch`, `get_task`, `get_tasks_for_date`, `update_task`, `toggle_task_status`, `delete_task`, `get_overdue_tasks`, `rollover_task`, and `batch_rollover_tasks`.
- [ ] `tests/unit/test_task_service.py` contains automated unit tests using the in-memory SQLite fixture `db_session` verifying `create_task` with `TaskCreate` persists all fields, default status `todo`, priority, and reminder flags (REQ-TSK-01).
- [ ] Automated tests verify `create_task` with `ExtractedTask` correctly populates `Task` attributes and sets `recurrence=None`.
- [ ] Automated tests verify `create_tasks_batch` creates multiple tasks and handles empty list `[]`.
- [ ] Automated tests verify `get_task` returns `Task` for owner and `None` for non-existent or other user's task (REQ-NFR-02).
- [ ] Automated tests verify `get_tasks_for_date` returns tasks for target date sorted by status (`todo` before `done`) and priority (`high` -> `medium` -> `low`), and returns `[]` when no tasks match.
- [ ] Automated tests verify `update_task` updates fields, resets reminder flags when `deadline_at` is updated, and raises `ValueError` for non-existent or foreign user tasks (REQ-NFR-02).
- [ ] Automated tests verify `toggle_task_status` transitions between `todo`, `done`, and `canceled`, and raises `ValueError` when mutating another user's task (REQ-TSK-02, REQ-NFR-02).
- [ ] Automated tests verify `delete_task` deletes owner's task returning `True`, and returns `False` for non-existent or foreign user tasks without deleting records (REQ-NFR-02).
- [ ] Automated tests verify `get_overdue_tasks` returns only uncompleted tasks (`status == todo`) with `target_date < before_date` strictly for the given user (REQ-SCH-01, REQ-NFR-02).
- [ ] Automated tests verify `rollover_task` updates `target_date` to new date and enforces tenant ownership (REQ-SCH-01, REQ-NFR-02).
- [ ] Automated tests verify `batch_rollover_tasks` updates multiple tasks for owner and does not mutate tasks belonging to another user (REQ-SCH-01, REQ-NFR-02).
- [ ] Automated tests verify Pydantic schemas `TaskCreate`, `TaskUpdate`, and `TaskRead` validation, defaults, field limits, and `from_attributes=True` serialization.
- [ ] All test functions in `tests/unit/test_task_service.py` contain docstrings referencing requirement IDs (`REQ-TSK-01`, `REQ-TSK-02`, `REQ-SCH-01`, `REQ-NFR-02`).
- [ ] Running `uv run pytest tests/unit/test_task_service.py` executes all task service tests and passes with 0 errors and 0 failures.
- [ ] Running `uv run pytest` executes the complete test suite and passes with 0 errors and 0 failures.

### Out of scope

- Telegram bot dispatcher setup and `/start` onboarding command handler, moved to #6
- Voice and text message bot handlers and inline confirmation keyboards (`[✅ Зберегти]`), moved to #7
- Midnight rollover interactive dialogue flow (00:00 "Хвости" bot UI), moved to #8
- FastAPI backend initialization and Telegram WebApp initData authentication, moved to #9
- Mini App REST API endpoints for tasks (`/api/tasks`), moved to #10
- Frontend React Mini App checklist and task creation UI, moved to #11, #12
- Recurring task automatic generation logic across days (REQ-TMA-02), moved to #12
- APScheduler timezone-aware background jobs (00:00 rollover & 09:00 push), moved to #13
- Scheduled deadline proximity push notifications (-1h and -10m), moved to #14

### Constraints

- Files this should stay inside: `src/schemas/task.py`, `src/schemas/__init__.py`, `src/services/task_service.py`, `src/services/__init__.py`, `tests/unit/test_task_service.py`
- Libraries to use: `sqlalchemy>=2.0` (`select`, `update`, `delete`, `case`, `AsyncSession`), `pydantic>=2.0` (`BaseModel`, `Field`, `ConfigDict`, `field_validator`), `datetime` (Python standard library), `pytest`, `pytest-asyncio`
- Do not add new dependencies to `pyproject.toml` without explicit permission per `Agents.md`
- Follow testing conventions in `_docs/testing-guidelines.md` (isolated in-memory SQLite fixture `db_session`, `@pytest.mark.asyncio`, REQ docstrings)
- All database queries must strictly enforce tenant isolation by filtering `Task.user_id == user_id` per REQ-NFR-02
- Follow modular architecture defined in `_docs/schema.md`
- Do not implement bot handlers, API endpoints, or background scheduler jobs in this task

## 6. Telegram Bot Dispatcher and /start Command

### Goal

Configure the application settings using `pydantic-settings`, initialize the `aiogram 3` bot and dispatcher with database session dependency injection middleware, and implement the `/start` command onboarding flow that registers new users with default timezone `Europe/Kyiv`, greets returning users, and displays the launch inline keyboard with 100% mocked automated tests.

### Acceptance criteria

- [ ] `src/core/config.py` defines `Settings` class inheriting from `pydantic_settings.BaseSettings`.
- [ ] `Settings.BOT_TOKEN` is defined as `str` defaulting to `""`.
- [ ] `Settings.GEMINI_API_KEY` is defined as `str` defaulting to `""`.
- [ ] `Settings.DATABASE_URL` is defined as `str` defaulting to `"sqlite+aiosqlite:///tasks.db"`.
- [ ] `Settings.WEBAPP_URL` is defined as optional `str | None` defaulting to `None`.
- [ ] `Settings.HOST` is defined as `str` defaulting to `"0.0.0.0"`.
- [ ] `Settings.PORT` is defined as `int` defaulting to `8000`.
- [ ] `Settings.DEBUG` is defined as `bool` defaulting to `True`.
- [ ] `Settings` configures `model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")`.
- [ ] `src/core/config.py` defines `get_settings() -> Settings` providing a cached or default `Settings` instance.
- [ ] `src/core/__init__.py` imports and exposes `Settings` and `get_settings`.
- [ ] `src/bot/middlewares/db.py` defines `DbSessionMiddleware` inheriting from `aiogram.BaseMiddleware`.
- [ ] `DbSessionMiddleware.__init__(self, sessionmaker: async_sessionmaker[AsyncSession] | None = None)` stores the sessionmaker, defaulting to `src.core.database.async_session_maker` if not provided.
- [ ] `DbSessionMiddleware` implements `__call__(self, handler, event, data)` which opens an asynchronous session context using `self.sessionmaker()`, injects `session` into `data["session"]`, awaits the handler, commits the session on success, rolls back on exception, and ensures the session is closed upon exit.
- [ ] If an exception occurs within the handler, `DbSessionMiddleware` rolls back the session and re-raises the exception.
- [ ] `src/bot/middlewares/__init__.py` imports and exposes `DbSessionMiddleware`.
- [ ] `src/bot/keyboards/start.py` defines `get_start_keyboard(webapp_url: str | None = None) -> InlineKeyboardMarkup`.
- [ ] When `webapp_url` is provided as a non-empty string, `get_start_keyboard` returns an `InlineKeyboardMarkup` containing an `InlineKeyboardButton` with text `"🚀 Відкрити план"` and `web_app=WebAppInfo(url=webapp_url)` per `_docs/design-system.md`.
- [ ] When `webapp_url` is `None` or empty, `get_start_keyboard` returns an `InlineKeyboardMarkup` containing an `InlineKeyboardButton` with text `"🚀 Відкрити план"` and `callback_data="open_plan"`.
- [ ] The keyboard layout complies with `_docs/design-system.md` (maximum 2 buttons per row).
- [ ] `src/bot/keyboards/__init__.py` imports and exposes `get_start_keyboard`.
- [ ] `src/bot/handlers/start.py` defines `router = Router(name="start")`.
- [ ] `src/bot/handlers/start.py` defines async handler `start_command(message: Message, session: AsyncSession, webapp_url: str | None = None) -> Message | None` decorated with `@router.message(CommandStart())`.
- [ ] If `message.from_user` is `None`, `start_command` returns immediately without executing database operations or raising an error.
- [ ] `start_command` calls `get_or_create_user(session, telegram_id=message.from_user.id, timezone="Europe/Kyiv")` (REQ-USR-01).
- [ ] When `created is True` (new user), `start_command` replies to the user with a welcoming onboarding message outlining bot features (voice tasks, reminders, 00:00 rollover, 09:00 digest) and attaches `get_start_keyboard(webapp_url)` (REQ-USR-01).
- [ ] When `created is False` (existing user), `start_command` replies to the user with a returning welcome message (e.g. "З поверненням!") and attaches `get_start_keyboard(webapp_url)` without duplicating user records or modifying the user's existing timezone (REQ-USR-01).
- [ ] All message texts use semantic emojis (`🚀`, `📋`, `✨`, `💡`, `🕒`) and clean HTML formatting per `_docs/design-system.md`.
- [ ] `src/bot/handlers/__init__.py` imports and exposes `start_router`.
- [ ] `src/bot/dispatcher.py` defines `create_bot(token: str | None = None, default_parse_mode: ParseMode = ParseMode.HTML) -> Bot` initializing `Bot` with the provided token, falling back to `get_settings().BOT_TOKEN`, or raising `ValueError("BOT_TOKEN is not set")` if no token is provided.
- [ ] `src/bot/dispatcher.py` defines `create_dispatcher(sessionmaker: async_sessionmaker[AsyncSession] | None = None, webapp_url: str | None = None) -> Dispatcher`.
- [ ] `create_dispatcher` registers `DbSessionMiddleware(sessionmaker)` on `dp.message.middleware` (and `dp.callback_query.middleware`).
- [ ] `create_dispatcher` passes `webapp_url` into workflow data (`dp.workflow_data` or handler kwargs) so handlers have access to `webapp_url`.
- [ ] `create_dispatcher` includes `start_router`.
- [ ] `src/bot/__init__.py` imports and exposes `create_bot` and `create_dispatcher`.
- [ ] `tests/unit/test_config.py` contains automated tests verifying `Settings` default values and `.env` override loading.
- [ ] `tests/unit/test_bot_dispatcher.py` contains automated tests verifying `create_bot` initializes `Bot` with provided token or settings.
- [ ] `tests/unit/test_bot_dispatcher.py` contains automated tests verifying `create_dispatcher` attaches `DbSessionMiddleware` and includes `start_router`.
- [ ] `tests/unit/test_bot_dispatcher.py` contains automated tests verifying `get_start_keyboard` generates `WebAppInfo` button when `webapp_url` is provided and fallback `callback_data` button when `webapp_url` is omitted.
- [ ] `tests/integration/test_bot_handlers.py` contains automated tests verifying `DbSessionMiddleware` injects an active `AsyncSession`, commits after successful handler execution, and rolls back on exception.
- [ ] `tests/integration/test_bot_handlers.py` contains automated tests using the in-memory SQLite fixture `db_session` verifying new user registration on `/start`: user record is persisted in `users` with `telegram_id` and default timezone `"Europe/Kyiv"`, and onboarding message is sent (REQ-USR-01).
- [ ] `tests/integration/test_bot_handlers.py` contains automated tests verifying existing user on `/start`: no duplicate user created, existing timezone preserved, and returning user message sent (REQ-USR-01).
- [ ] `tests/integration/test_bot_handlers.py` contains automated tests verifying `/start` with message where `from_user is None` is handled safely without database modification or crash.
- [ ] All tests mock Telegram Bot API calls (`message.answer`, `bot.send_message`, etc.) using `unittest.mock.AsyncMock` with zero real network requests per `_docs/testing-guidelines.md`.
- [ ] All test functions contain docstrings referencing requirement ID `REQ-USR-01`.
- [ ] Running `uv run pytest` executes all tests and passes with 0 errors and 0 failures.

### Out of scope

- Voice note audio download and text message AI parsing handlers, moved to #7
- Inline confirmation keyboards (`[✅ Зберегти]`, `[✏️ Виправити]`) and task batch saving callback handlers, moved to #7
- Midnight rollover interactive dialogue flow (00:00 "Хвости" bot UI), moved to #8
- FastAPI backend initialization, WebApp initData HMAC-SHA256 authentication, and health check endpoints, moved to #9
- Mini App REST API endpoints for tasks (`/api/tasks`), moved to #10
- Frontend React Mini App checklist and task creation UI, moved to #11, #12
- Recurring task automatic generation logic across days (REQ-TMA-02), moved to #12
- APScheduler timezone-aware background jobs (00:00 rollover & 09:00 push), moved to #13
- Scheduled deadline proximity push notifications (-1h and -10m), moved to #14
- User `/settings` command handler and timezone configuration UI, moved to #17

### Constraints

- Files this should stay inside: `src/core/config.py`, `src/core/__init__.py`, `src/bot/dispatcher.py`, `src/bot/__init__.py`, `src/bot/middlewares/db.py`, `src/bot/middlewares/__init__.py`, `src/bot/keyboards/start.py`, `src/bot/keyboards/__init__.py`, `src/bot/handlers/start.py`, `src/bot/handlers/__init__.py`, `tests/unit/test_config.py`, `tests/unit/test_bot_dispatcher.py`, `tests/integration/test_bot_handlers.py`
- Libraries to use: `aiogram>=3.0` (`Bot`, `Dispatcher`, `Router`, `BaseMiddleware`, `CommandStart`, `ParseMode`, `DefaultBotProperties`, `InlineKeyboardMarkup`, `InlineKeyboardButton`, `WebAppInfo`, `Message`, `User`), `pydantic-settings>=2.0` (`BaseSettings`, `SettingsConfigDict`), `sqlalchemy>=2.0` (`AsyncSession`, `async_sessionmaker`), `pytest`, `pytest-asyncio`, `unittest.mock` (`AsyncMock`, `MagicMock`, `patch`)
- Do not add new dependencies to `pyproject.toml` without explicit permission per `Agents.md`
- Follow testing conventions in `_docs/testing-guidelines.md` (isolated in-memory SQLite fixture `db_session`, `@pytest.mark.asyncio`, zero real network calls to Telegram API, REQ docstrings)
- Follow Telegram bot formatting and UI guidelines in `_docs/design-system.md` (clean semantic emojis, HTML parse mode, max 2 buttons per row, `[🚀 Відкрити план]`)
- Follow modular architectural structure defined in `_docs/schema.md`
- Do not implement voice/text ingestion handlers, task parsing callbacks, API endpoints, or scheduler jobs in this task

## 7. Voice and Text Ingestion Bot Handlers

### Goal

Implement `aiogram 3` message and callback handlers for voice notes and text messages that download audio into memory or read text, extract structured tasks using the Gemini AI parser service with user timezone context, present parsed tasks with inline confirmation buttons (`[✅ Зберегти]` and `[✏️ Виправити]`), persist confirmed tasks to the database via batch creation, and enforce tenant security with 100% mocked integration tests.

### Acceptance criteria

- [ ] `src/bot/keyboards/tasks.py` defines `TaskConfirmCallback` inheriting from `aiogram.filters.callback_data.CallbackData` with prefix `"task_confirm"` and fields `action: str` (values: `"save"`, `"edit"`) and `user_id: int`.
- [ ] `src/bot/keyboards/tasks.py` defines `get_task_confirmation_keyboard(user_id: int) -> InlineKeyboardMarkup` returning an inline keyboard with positive confirmation `[✅ Зберегти]` and modification `[✏️ Виправити]` arranged with a maximum of 2 buttons per row per `_docs/design-system.md`.
- [ ] `src/bot/keyboards/__init__.py` imports and exposes `TaskConfirmCallback` and `get_task_confirmation_keyboard`.
- [ ] `src/bot/states/tasks.py` defines `TaskIngestionState` inheriting from `aiogram.fsm.state.StatesGroup` with state `waiting_confirmation = State()`.
- [ ] `src/bot/states/__init__.py` imports and exposes `TaskIngestionState`.
- [ ] `src/bot/handlers/voice_text.py` defines helper `format_extracted_tasks_message(tasks: list[ExtractedTask]) -> str` that formats extracted tasks into an HTML-formatted message with a bold header (`<b>📋 Розпізнані завдання:</b>`), bulleted items with task titles, priority badges (`⚠️ Високий`, `⚡ Середній`, `💤 Низький`), category tags (`🏷️ #{tag}`), target dates (`📅 {target_date}`), and formatted deadlines (`🕒 до {time}`) per `_docs/design-system.md`.
- [ ] `src/bot/handlers/voice_text.py` defines `router = Router(name="voice_text")` (or `voice_text_router`).
- [ ] `src/bot/handlers/voice_text.py` defines async handler `handle_voice_message(message: Message, bot: Bot, session: AsyncSession, state: FSMContext) -> Message | None` filtered by `F.voice`.
- [ ] If `message.from_user` is `None` or `message.voice` is `None`, `handle_voice_message` returns immediately without errors or database modifications.
- [ ] `handle_voice_message` calls `get_or_create_user(session, telegram_id=message.from_user.id)` to obtain the user's configured `user.timezone` (REQ-USR-01).
- [ ] `handle_voice_message` dispatches chat action `upload_voice` (or `record_voice` / `typing`) via `bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.UPLOAD_VOICE)` while processing audio (REQ-AI-01).
- [ ] `handle_voice_message` downloads audio bytes directly into memory via `bot.download(message.voice.file_id, destination=io.BytesIO())` without saving temporary files to disk (REQ-AI-01).
- [ ] `handle_voice_message` invokes `parse_tasks_from_audio(audio_bytes=..., user_timezone=user.timezone)` with the in-memory audio bytes and user timezone (REQ-AI-01, REQ-AI-02).
- [ ] `src/bot/handlers/voice_text.py` defines async handler `handle_text_message(message: Message, bot: Bot, session: AsyncSession, state: FSMContext) -> Message | None` filtered by `F.text & ~F.text.startswith("/")`.
- [ ] If `message.from_user` is `None` or `message.text` is empty or whitespace-only, `handle_text_message` returns immediately without errors or database modifications.
- [ ] `handle_text_message` calls `get_or_create_user(session, telegram_id=message.from_user.id)` to obtain `user.timezone` (REQ-USR-01).
- [ ] `handle_text_message` dispatches chat action `typing` via `bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)` while processing text (REQ-AI-02).
- [ ] `handle_text_message` invokes `parse_tasks_from_text(text=message.text, user_timezone=user.timezone)` with the message text and user timezone (REQ-AI-02).
- [ ] When AI extraction returns an empty list `tasks: []` (chit-chat, noise, or no actionable tasks), the bot replies with a polite notification message (e.g. `💡 Не вдалося розпізнати завдання. Спробуйте надиктувати або написати чіткіше.`), attaches no confirmation keyboard, and does not enter `waiting_confirmation` FSM state (REQ-AI-02).
- [ ] When AI extraction returns one or more tasks (`tasks: list[ExtractedTask]`):
  - Extracted tasks are serialized and stored in FSM state data via `await state.update_data(pending_tasks=[t.model_dump(mode="json") for t in tasks])`.
  - FSM state is set to `TaskIngestionState.waiting_confirmation` via `await state.set_state(...)`.
  - Bot replies with the formatted tasks message and attaches `get_task_confirmation_keyboard(user_id=message.from_user.id)` (REQ-AI-03).
- [ ] `src/bot/handlers/callbacks.py` defines `router = Router(name="callbacks")` (or callback handler registered in `src/bot/handlers/voice_text.py`) handling `TaskConfirmCallback.filter()`.
- [ ] Tenant Security: If `callback_query.from_user.id != callback_data.user_id`, the callback is rejected immediately with alert `await callback_query.answer("⚠️ Ви не можете керувати завданнями іншого користувача.", show_alert=True)` without altering database or FSM state (REQ-AI-03, REQ-NFR-02).
- [ ] Confirmation Callback (`action == "save"`):
  - Deserializes pending tasks from FSM state data into `list[ExtractedTask]`.
  - If pending tasks exist in state, persists tasks via `create_tasks_batch(session, user_id=callback_query.from_user.id, tasks=extracted_tasks)` in a single database transaction with status `todo` (REQ-TSK-01, REQ-AI-03).
  - Edits original message to remove the inline keyboard and display confirmation text (`✅ <b>Завдання успішно збережено!</b>`) (REQ-AI-03).
  - Clears FSM state via `await state.clear()`.
  - Acknowledges callback with `await callback_query.answer("Збережено!")`.
  - If pending tasks are missing from state (session expired or already saved), alerts user via `await callback_query.answer("⚠️ Завдання вже збережено або сесія застаріла.", show_alert=True)` and removes the keyboard from message.
- [ ] Edit Callback (`action == "edit"`):
  - Clears FSM state via `await state.clear()`.
  - Edits message or sends prompt instructing the user to dictate or type again (`✏️ Будь ласка, надиктуйте або надішліть текстом нове формулювання завдань.`) and removes the confirmation keyboard (REQ-AI-03).
  - Acknowledges callback with `await callback_query.answer()`.
- [ ] `src/bot/handlers/__init__.py` imports and exposes `voice_text_router` and `callbacks_router` (or combined `task_router`).
- [ ] `src/bot/dispatcher.py` updates `create_dispatcher` to include `voice_text_router` and `callbacks_router` alongside `start_router`.
- [ ] `tests/integration/test_task_ingestion_handlers.py` contains automated integration tests verifying voice message handling: mocks `bot.download` returning `io.BytesIO` audio bytes, mocks `parse_tasks_from_audio`, asserts chat action is sent, tasks are formatted with inline keyboard, and serialized tasks are saved in FSM state (REQ-AI-01, REQ-AI-02).
- [ ] `tests/integration/test_task_ingestion_handlers.py` contains automated integration tests verifying text message handling: sends plain text, mocks `parse_tasks_from_text`, asserts typing action is sent, tasks are presented with inline keyboard, and FSM state is updated (REQ-AI-02).
- [ ] `tests/integration/test_task_ingestion_handlers.py` contains automated integration tests verifying command messages (`/start`, `/settings`) are ignored by `handle_text_message` and not parsed as tasks.
- [ ] `tests/integration/test_task_ingestion_handlers.py` contains automated integration tests verifying empty extraction results (`tasks: []`): sends voice/text returning `[]`, asserts friendly message without keyboard is sent, and FSM state remains empty (REQ-AI-02).
- [ ] `tests/integration/test_task_ingestion_handlers.py` contains automated integration tests verifying `[✅ Зберегти]` callback: persists tasks in database with status `todo` and `user_id`, edits message to confirmation text without keyboard, and clears FSM state (REQ-AI-03).
- [ ] `tests/integration/test_task_ingestion_handlers.py` contains automated integration tests verifying `[✏️ Виправити]` callback: prompts user to re-dictate or re-type, removes keyboard, and clears FSM state (REQ-AI-03).
- [ ] `tests/integration/test_task_ingestion_handlers.py` contains automated integration tests verifying tenant security: callback query from an unauthorized user (`callback_query.from_user.id != callback_data.user_id`) triggers `answer_callback_query(show_alert=True)` and does not persist tasks or clear owner state (REQ-AI-03, REQ-NFR-02).
- [ ] `tests/integration/test_task_ingestion_handlers.py` contains automated integration tests verifying expired or missing FSM state on callback triggers alert without raising unhandled exceptions.
- [ ] All integration tests use the in-memory SQLite fixture `db_session` and 100% mocked Telegram API and Gemini calls with zero real network requests per `_docs/testing-guidelines.md`.
- [ ] All test functions contain docstrings referencing requirement IDs (`REQ-AI-01`, `REQ-AI-02`, `REQ-AI-03`, `REQ-TSK-01`).
- [ ] Running `uv run pytest tests/integration/test_task_ingestion_handlers.py` passes with 0 errors and 0 failures.
- [ ] Running `uv run pytest` executes the complete test suite and passes with 0 errors and 0 failures.

### Out of scope

- Midnight rollover interactive dialogue flow (00:00 "Хвости" bot UI), moved to #8
- FastAPI backend initialization, WebApp initData HMAC-SHA256 authentication, and health check endpoints, moved to #9
- Mini App REST API endpoints for tasks (`/api/tasks`), moved to #10
- Frontend React Mini App checklist and task creation UI, moved to #11, #12
- Recurring task automatic generation logic across days (REQ-TMA-02), moved to #12
- APScheduler timezone-aware background jobs (00:00 rollover & 09:00 push), moved to #13
- Scheduled deadline proximity push notifications (-1h and -10m), moved to #14
- Interactive task editing (individual field modification UI / modal or fine-grained editing flow) beyond prompt-to-redictate, moved to #12
- User `/settings` command handler and timezone configuration UI, moved to #17

### Constraints

- Files this should stay inside: `src/bot/keyboards/tasks.py`, `src/bot/keyboards/__init__.py`, `src/bot/states/tasks.py`, `src/bot/states/__init__.py`, `src/bot/handlers/voice_text.py`, `src/bot/handlers/callbacks.py`, `src/bot/handlers/__init__.py`, `src/bot/dispatcher.py`, `tests/integration/test_task_ingestion_handlers.py`
- Libraries to use: `aiogram>=3.0` (`Bot`, `Dispatcher`, `Router`, `F`, `ChatAction`, `Message`, `CallbackQuery`, `InlineKeyboardMarkup`, `InlineKeyboardButton`, `CallbackData`, `FSMContext`, `State`, `StatesGroup`, `MemoryStorage`), `sqlalchemy>=2.0` (`AsyncSession`), `pydantic>=2.0`, `pytest`, `pytest-asyncio`, `unittest.mock` (`AsyncMock`, `MagicMock`, `patch`)
- Do not add new dependencies to `pyproject.toml` without explicit permission per `Agents.md`
- Never save voice audio files to disk; audio buffers must be downloaded and parsed strictly in memory (`io.BytesIO`) per REQ-AI-01
- Never make real network requests to Telegram or Google Gemini in automated tests per `_docs/testing-guidelines.md`
- Follow Telegram bot formatting and UI guidelines in `_docs/design-system.md` (clean semantic emojis, HTML parse mode, max 2 buttons per row, `[✅ Зберегти]`, `[✏️ Виправити]`)
- Follow modular architectural structure defined in `_docs/schema.md`
- Do not implement rollover dialogue (#8), API endpoints (#9, #10), Mini App UI (#11, #12), or scheduler jobs (#13, #14) in this task

## 8. Midnight Rollover Flow (00:00 "Хвости")

### Goal

Build the interactive Telegram midnight rollover dialogue and callback handlers that detect overdue uncompleted tasks ("хвости") at 00:00 user local time, display them with per-task and batch inline action buttons to postpone (`[⏩ Перенести на сьогодні]`) or close (`[❌ Закрити]`), dynamically update message states upon resolution, prompt the user to plan the new day once all tasks are cleared, and enforce strict tenant isolation with comprehensive integration tests.

### Acceptance criteria

- [ ] `src/bot/keyboards/rollover.py` defines `RolloverCallback` inheriting from `aiogram.filters.callback_data.CallbackData` with prefix `"rollover"` and fields: `action: str` (values: `"postpone"`, `"close"`, `"postpone_all"`, `"close_all"`), `task_id: int | None = None`, and `user_id: int`.
- [ ] `src/bot/keyboards/rollover.py` defines `get_task_rollover_keyboard(task_id: int, user_id: int) -> InlineKeyboardMarkup` returning inline buttons `[⏩ Перенести на сьогодні]` (action `"postpone"`) and `[❌ Закрити]` (action `"close"`) arranged with a maximum of 2 buttons per row per `_docs/design-system.md`.
- [ ] `src/bot/keyboards/rollover.py` defines `get_batch_rollover_keyboard(user_id: int) -> InlineKeyboardMarkup` returning inline buttons `[⏩ Перенести всі]` (action `"postpone_all"`) and `[❌ Закрити всі]` (action `"close_all"`) arranged with a maximum of 2 buttons per row per `_docs/design-system.md`.
- [ ] `src/bot/keyboards/__init__.py` imports and exposes `RolloverCallback`, `get_task_rollover_keyboard`, and `get_batch_rollover_keyboard`.
- [ ] `src/bot/handlers/rollover.py` defines `format_overdue_task_item(task: Task) -> str` formatting an overdue task into an HTML string with semantic emojis: title, priority badge (`⚠️ Високий`, `⚡ Середній`, `💤 Низький`), category tag (`🏷️ #{tag}`), and original target date (`📅 {task.target_date}`) per `_docs/design-system.md`.
- [ ] `src/bot/handlers/rollover.py` defines async function `send_midnight_rollover_dialogue(bot: Bot, session: AsyncSession, user: User, reference_date: date | None = None) -> list[Message]` to trigger the rollover review dialogue (REQ-SCH-01).
- [ ] `send_midnight_rollover_dialogue` computes the user's local date `local_today`: uses `reference_date` if provided; otherwise resolves local date via `get_user_local_time(user).date()`.
- [ ] `send_midnight_rollover_dialogue` queries uncompleted overdue tasks using `get_overdue_tasks(session, user_id=user.telegram_id, before_date=local_today)` (REQ-SCH-01, REQ-NFR-02).
- [ ] When no overdue tasks exist (`overdue_tasks == []`), `send_midnight_rollover_dialogue` sends a single congratulatory message to `chat_id=user.telegram_id`: `✨ <b>Всі вчорашні завдання виконано!</b> Чудова робота.\n\nНадиктуйте або напишіть план на сьогодні 🚀` with no inline keyboard, and returns `[sent_message]` (REQ-SCH-01).
- [ ] When overdue tasks exist, `send_midnight_rollover_dialogue`:
  - Sends an overview batch control message with text `📋 <b>Невиконані завдання за вчора ("хвости"):</b>\nУ вас залишилося {count} невиконаних завдань.` attached with `get_batch_rollover_keyboard(user_id=user.telegram_id)`.
  - Sends each overdue task as an individual message formatted via `format_overdue_task_item(task)` attached with `get_task_rollover_keyboard(task_id=task.id, user_id=user.telegram_id)`.
  - Returns the list of all sent `Message` objects in the order sent.
- [ ] `src/bot/handlers/rollover.py` defines `router = Router(name="rollover")` (or `rollover_router`).
- [ ] `src/bot/handlers/rollover.py` defines async callback handler `handle_rollover_callback(callback_query: CallbackQuery, callback_data: RolloverCallback, bot: Bot, session: AsyncSession) -> None` decorated with `@router.callback_query(RolloverCallback.filter())`.
- [ ] If `callback_query.from_user` is `None` or `callback_query.message` is not an instance of `Message`, `handle_rollover_callback` returns immediately without errors or database modifications.
- [ ] Tenant Security Check: If `callback_query.from_user.id != callback_data.user_id`, the callback is rejected immediately with alert `await callback_query.answer("⚠️ Ви не можете керувати завданнями іншого користувача.", show_alert=True)` without altering database or message state (REQ-NFR-02).
- [ ] Single Task Postpone Callback (`action == "postpone"`):
  - Resolves `local_today` from user timezone.
  - If `callback_data.task_id` is missing or the task cannot be found in database, alerts user via `await callback_query.answer("⚠️ Завдання вже опрацьовано або не знайдено.", show_alert=True)` and removes the keyboard from message.
  - Postpones task via `rollover_task(session, task_id=callback_data.task_id, user_id=callback_query.from_user.id, new_date=local_today)` updating `target_date` to today (REQ-SCH-01, REQ-TSK-01).
  - Dynamically edits `callback_query.message` to confirmation text (e.g. `⏩ Завдання «{task.title}» перенесено на сьогодні!`) and removes inline keyboard (`reply_markup=None`).
  - Answers callback via `await callback_query.answer("Перенесено на сьогодні!")`.
  - Checks remaining overdue tasks via `get_overdue_tasks(session, user_id=callback_query.from_user.id, before_date=local_today)`; if no overdue tasks remain (`len == 0`), automatically sends follow-up prompt: `await bot.send_message(chat_id=callback_query.from_user.id, text="✨ Всі хвости розібрано! Надиктуйте або напишіть план на сьогодні 🚀")`.
- [ ] Single Task Close Callback (`action == "close"`):
  - Resolves `local_today` from user timezone.
  - If `callback_data.task_id` is missing or the task cannot be found in database, alerts user via `await callback_query.answer("⚠️ Завдання вже опрацьовано або не знайдено.", show_alert=True)` and removes the keyboard from message.
  - Cancels task via `toggle_task_status(session, task_id=callback_data.task_id, user_id=callback_query.from_user.id, new_status=TaskStatus.canceled)` (REQ-SCH-01, REQ-TSK-02).
  - Dynamically edits `callback_query.message` to confirmation text (e.g. `❌ Завдання «{task.title}» закрито.`) and removes inline keyboard (`reply_markup=None`).
  - Answers callback via `await callback_query.answer("Завдання закрито!")`.
  - Checks remaining overdue tasks via `get_overdue_tasks(session, user_id=callback_query.from_user.id, before_date=local_today)`; if no overdue tasks remain (`len == 0`), automatically sends follow-up prompt: `await bot.send_message(chat_id=callback_query.from_user.id, text="✨ Всі хвости розібрано! Надиктуйте або напишіть план на сьогодні 🚀")`.
- [ ] Batch Postpone Callback (`action == "postpone_all"`):
  - Resolves `local_today` from user timezone.
  - Retrieves remaining overdue tasks via `get_overdue_tasks(session, user_id=callback_query.from_user.id, before_date=local_today)`.
  - If no overdue tasks remain, edits message to `✨ Всі хвости вже опрацьовано!`, removes keyboard, and answers callback.
  - If overdue tasks exist, calls `batch_rollover_tasks(session, task_ids=[t.id for t in overdue_tasks], user_id=callback_query.from_user.id, new_date=local_today)` to postpone all overdue tasks to today (REQ-SCH-01).
  - Dynamically edits message to `⏩ Всі завдання ({count}) перенесено на сьогодні!` and removes inline keyboard (`reply_markup=None`).
  - Answers callback via `await callback_query.answer("Всі завдання перенесено!")`.
  - Automatically sends follow-up prompt: `await bot.send_message(chat_id=callback_query.from_user.id, text="✨ Всі хвости розібрано! Надиктуйте або напишіть план на сьогодні 🚀")`.
- [ ] Batch Close Callback (`action == "close_all"`):
  - Resolves `local_today` from user timezone.
  - Retrieves remaining overdue tasks via `get_overdue_tasks(session, user_id=callback_query.from_user.id, before_date=local_today)`.
  - If no overdue tasks remain, edits message to `✨ Всі хвости вже опрацьовано!`, removes keyboard, and answers callback.
  - If overdue tasks exist, updates status of all remaining overdue tasks to `TaskStatus.canceled` and commits the session (REQ-SCH-01, REQ-TSK-02).
  - Dynamically edits message to `❌ Всі завдання ({count}) закрито.` and removes inline keyboard (`reply_markup=None`).
  - Answers callback via `await callback_query.answer("Всі завдання закрито!")`.
  - Automatically sends follow-up prompt: `await bot.send_message(chat_id=callback_query.from_user.id, text="✨ Всі хвости розібрано! Надиктуйте або напишіть план на сьогодні 🚀")`.
- [ ] `src/bot/handlers/__init__.py` imports and exposes `rollover_router`.
- [ ] `src/bot/dispatcher.py` updates `create_dispatcher` to include `rollover_router` alongside `start_router`, `voice_text_router`, and `callbacks_router`.
- [ ] `tests/integration/test_rollover_handlers.py` contains automated integration tests verifying `send_midnight_rollover_dialogue` when user has zero overdue tasks sends single congratulatory message and returns `list[Message]` of length 1 (REQ-SCH-01).
- [ ] `tests/integration/test_rollover_handlers.py` contains automated integration tests verifying `send_midnight_rollover_dialogue` when user has multiple overdue tasks sends overview batch message and per-task messages with inline keyboards (REQ-SCH-01).
- [ ] `tests/integration/test_rollover_handlers.py` contains automated integration tests verifying `send_midnight_rollover_dialogue` respects `reference_date` parameter for deterministic testing.
- [ ] `tests/integration/test_rollover_handlers.py` contains automated integration tests verifying single task postpone callback (`action == "postpone"`): task `target_date` is updated to today in DB, message text is edited, keyboard is removed, callback is answered, and follow-up prompt is sent only if no overdue tasks remain (REQ-SCH-01, REQ-TSK-01).
- [ ] `tests/integration/test_rollover_handlers.py` contains automated integration tests verifying single task close callback (`action == "close"`): task status is updated to `TaskStatus.canceled` in DB, message text is edited, keyboard is removed, callback is answered, and follow-up prompt is sent only if no overdue tasks remain (REQ-SCH-01, REQ-TSK-02).
- [ ] `tests/integration/test_rollover_handlers.py` contains automated integration tests verifying batch postpone callback (`action == "postpone_all"`): all overdue tasks have `target_date` updated to today in DB, overview message is edited without keyboard, callback is answered, and follow-up prompt is sent (REQ-SCH-01).
- [ ] `tests/integration/test_rollover_handlers.py` contains automated integration tests verifying batch close callback (`action == "close_all"`): all overdue tasks have status updated to `TaskStatus.canceled` in DB, overview message is edited without keyboard, callback is answered, and follow-up prompt is sent (REQ-SCH-01, REQ-TSK-02).
- [ ] `tests/integration/test_rollover_handlers.py` contains automated integration tests verifying tenant security enforcement: callback query from unauthorized user (`from_user.id != callback_data.user_id`) triggers `answer(show_alert=True)` with error message and leaves DB and messages untouched (REQ-NFR-02).
- [ ] `tests/integration/test_rollover_handlers.py` contains automated integration tests verifying handling of already-resolved or non-existent tasks: displays alert without raising unhandled exceptions.
- [ ] All integration tests in `tests/integration/test_rollover_handlers.py` mock 100% of Telegram API calls (`bot.send_message`, `callback_query.answer`, `message.edit_text`, `message.edit_reply_markup`) using `unittest.mock.AsyncMock` with zero real network requests per `_docs/testing-guidelines.md`.
- [ ] All test functions contain docstrings referencing requirement IDs (`REQ-SCH-01`, `REQ-TSK-01`, `REQ-TSK-02`, `REQ-NFR-02`).
- [ ] Running `uv run pytest tests/integration/test_rollover_handlers.py` executes all rollover tests and passes with 0 errors and 0 failures.
- [ ] Running `uv run pytest` executes the complete test suite and passes with 0 errors and 0 failures.

### Out of scope

- APScheduler timezone-aware background jobs and minute-by-minute 00:00 trigger scheduler, moved to #13
- Scheduled deadline proximity push notifications (-1h and -10m), moved to #14
- Morning push digest (09:00) with Mini App launch button, moved to #13
- FastAPI backend initialization and Telegram WebApp initData authentication, moved to #9
- Mini App REST API endpoints for tasks (`/api/tasks`), moved to #10
- Frontend React Mini App checklist and task creation UI, moved to #11, #12
- Recurring task automatic generation logic across days (REQ-TMA-02), moved to #12
- User `/settings` command handler and timezone configuration UI, moved to #17

### Constraints

- Files this should stay inside: `src/bot/keyboards/rollover.py`, `src/bot/keyboards/__init__.py`, `src/bot/handlers/rollover.py`, `src/bot/handlers/__init__.py`, `src/bot/dispatcher.py`, `tests/integration/test_rollover_handlers.py`
- Libraries to use: `aiogram>=3.0` (`Bot`, `Dispatcher`, `Router`, `F`, `Message`, `CallbackQuery`, `InlineKeyboardMarkup`, `InlineKeyboardButton`, `CallbackData`), `sqlalchemy>=2.0` (`AsyncSession`, `select`), `datetime` and `zoneinfo` (Python standard library), `pytest`, `pytest-asyncio`, `unittest.mock` (`AsyncMock`, `MagicMock`)
- Do not add new dependencies to `pyproject.toml` without explicit permission per `Agents.md`
- Never make real network requests to Telegram in automated tests per `_docs/testing-guidelines.md`
- Follow Telegram bot formatting and UI guidelines in `_docs/design-system.md` (clean semantic emojis, HTML parse mode, max 2 buttons per row, `[⏩ Перенести на сьогодні]`, `[❌ Закрити]`, `[⏩ Перенести всі]`, `[❌ Закрити всі]`)
- Strict tenant isolation filtering by `user_id` per `REQ-NFR-02`
- Follow modular architectural structure defined in `_docs/schema.md`
- Do not implement background scheduler jobs (#13), API endpoints (#9, #10), or Mini App UI (#11, #12) in this task

## 9. FastAPI Backend Initialization and Telegram initData Auth

### Goal

Initialize the FastAPI application with CORS middleware, health check, and asynchronous database session dependency injection, and implement secure Telegram Mini App authentication that validates `initData` HMAC-SHA256 signatures, enforces 24-hour expiration, and extracts authenticated users with comprehensive integration tests.

### Acceptance criteria

- [ ] `src/api/deps.py` defines async generator dependency `get_db_session(request: Request) -> AsyncGenerator[AsyncSession, None]` that retrieves the sessionmaker from `request.app.state.sessionmaker` (or defaults to `src.core.database.async_session_maker`), yields an `AsyncSession`, commits on success, rolls back on exception, and closes the session upon exit.
- [ ] `src/api/deps.py` imports and exposes `get_db_session`.
- [ ] `src/api/auth.py` defines `validate_init_data(raw_init_data: str, bot_token: str, max_age_seconds: int = 86400) -> dict[str, Any]` validating Telegram WebApp `initData` per official Telegram specifications (REQ-API-01).
- [ ] `validate_init_data` extracts and parses URL-encoded query parameters from `raw_init_data`.
- [ ] If `hash` parameter is missing from `raw_init_data`, `validate_init_data` raises `HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing hash in initData")` (REQ-API-01).
- [ ] If `auth_date` parameter is missing or cannot be parsed as an integer Unix timestamp, `validate_init_data` raises `HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing or invalid auth_date in initData")` (REQ-API-01).
- [ ] `validate_init_data` enforces expiration: if `current_timestamp - auth_date > max_age_seconds` (default 86400s / 24h), it raises `HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Telegram initData has expired")` (REQ-API-01).
- [ ] If `auth_date` is in the future beyond acceptable clock drift (e.g. `auth_date - current_timestamp > 60`), `validate_init_data` raises `HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Telegram initData auth_date is in the future")`.
- [ ] `validate_init_data` constructs data-check string by filtering out `hash`, sorting remaining key-value pairs alphabetically by key, and joining them with `\n` in `key=value` format.
- [ ] `validate_init_data` computes secret key using `hmac.new(key=b"WebAppData", msg=bot_token.encode("utf-8"), digestmod=hashlib.sha256).digest()`.
- [ ] `validate_init_data` calculates expected signature via `hmac.new(key=secret_key, msg=data_check_string.encode("utf-8"), digestmod=hashlib.sha256).hexdigest()`.
- [ ] `validate_init_data` verifies calculated signature against extracted `hash` using constant-time comparison `hmac.compare_digest`. If signatures do not match (tampered parameters or wrong bot token), it raises `HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Telegram initData signature")` (REQ-API-01).
- [ ] `validate_init_data` parses `user` parameter as JSON. If `user` parameter is missing, invalid JSON, or missing `id`, it raises `HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing or invalid user object in initData")`.
- [ ] `validate_init_data` returns the validated dictionary containing parsed parameters with `"user"` parsed into a Python dictionary.
- [ ] `src/api/auth.py` defines FastAPI dependency `get_current_user_id(request: Request, settings: Settings = Depends(get_settings)) -> int`.
- [ ] `get_current_user_id` extracts raw initData from either `Authorization` header (supporting `tma <raw_init_data>` and `Bearer <raw_init_data>` prefixes case-insensitively) or `X-Telegram-Init-Data` header.
- [ ] If authorization headers are missing, empty, or use an unrecognized scheme, `get_current_user_id` raises `HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing or invalid authentication credentials")`.
- [ ] `get_current_user_id` obtains `bot_token` from `request.app.state.settings.BOT_TOKEN` or `settings.BOT_TOKEN`, calls `validate_init_data`, and returns `int(parsed_data["user"]["id"])`.
- [ ] `src/api/auth.py` defines FastAPI dependency `get_current_user(user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_db_session)) -> User`.
- [ ] `get_current_user` calls `get_or_create_user(session, telegram_id=user_id)` to retrieve existing user or automatically provision new user with default timezone `"Europe/Kyiv"`, ensuring seamless onboarding for direct Mini App launches, and returns the `User` record (REQ-USR-01, REQ-NFR-02).
- [ ] `src/api/auth.py` imports and exposes `validate_init_data`, `get_current_user_id`, and `get_current_user`.
- [ ] `src/api/app.py` defines factory function `create_app(settings: Settings | None = None, sessionmaker: async_sessionmaker[AsyncSession] | None = None) -> FastAPI`.
- [ ] `create_app` stores `settings` in `app.state.settings` (falling back to `get_settings()` if None).
- [ ] `create_app` stores `sessionmaker` in `app.state.sessionmaker` (falling back to `src.core.database.async_session_maker` if None).
- [ ] `create_app` adds `CORSMiddleware` configured with `allow_origins=["*"]`, `allow_credentials=True`, `allow_methods=["*"]`, and `allow_headers=["*"]` to support Telegram WebApp client environments.
- [ ] `create_app` defines public health check endpoint `GET /health` returning `{"status": "ok"}` with HTTP 200 without requiring authentication.
- [ ] `create_app` defines protected endpoint `GET /api/me` returning `UserRead` with HTTP 200 for the authenticated user using `Depends(get_current_user)`.
- [ ] `src/api/__init__.py` imports and exposes `create_app`, `get_current_user_id`, `get_current_user`, `get_db_session`, and `validate_init_data`.
- [ ] `tests/integration/test_api_auth.py` provides test helper `create_test_init_data(user_data: dict, bot_token: str, auth_date: int | None = None) -> str` generating cryptographically valid signed Telegram `initData` query strings.
- [ ] `tests/integration/test_api_auth.py` contains automated tests using `TestClient` verifying `GET /health` returns HTTP 200 and `{"status": "ok"}` with no authentication headers.
- [ ] `tests/integration/test_api_auth.py` contains automated tests verifying CORS preflight/response headers include `access-control-allow-origin`.
- [ ] `tests/integration/test_api_auth.py` contains automated tests verifying `GET /api/me` with valid `initData` via `Authorization: tma <initData>` returns HTTP 200 and JSON matching `UserRead` schema (`telegram_id`, `timezone`, `created_at`) (REQ-API-01).
- [ ] `tests/integration/test_api_auth.py` contains automated tests verifying `GET /api/me` with valid `initData` via `Authorization: Bearer <initData>` returns HTTP 200 (REQ-API-01).
- [ ] `tests/integration/test_api_auth.py` contains automated tests verifying `GET /api/me` with valid `initData` via `X-Telegram-Init-Data` header returns HTTP 200 (REQ-API-01).
- [ ] `tests/integration/test_api_auth.py` contains automated tests verifying `GET /api/me` with tampered `initData` (altered user attributes or query values) returns HTTP 401 Unauthorized (REQ-API-01).
- [ ] `tests/integration/test_api_auth.py` contains automated tests verifying `GET /api/me` with signature signed by an invalid bot token returns HTTP 401 Unauthorized (REQ-API-01).
- [ ] `tests/integration/test_api_auth.py` contains automated tests verifying `GET /api/me` with expired `auth_date` (> 86400s) returns HTTP 401 Unauthorized (REQ-API-01).
- [ ] `tests/integration/test_api_auth.py` contains automated tests verifying `GET /api/me` with future `auth_date` returns HTTP 401 Unauthorized.
- [ ] `tests/integration/test_api_auth.py` contains automated tests verifying `GET /api/me` with missing `hash` returns HTTP 401 Unauthorized (REQ-API-01).
- [ ] `tests/integration/test_api_auth.py` contains automated tests verifying `GET /api/me` with missing `auth_date` returns HTTP 401 Unauthorized (REQ-API-01).
- [ ] `tests/integration/test_api_auth.py` contains automated tests verifying `GET /api/me` with missing `user` parameter returns HTTP 401 Unauthorized (REQ-API-01).
- [ ] `tests/integration/test_api_auth.py` contains automated tests verifying `GET /api/me` with missing authorization headers returns HTTP 401 Unauthorized.
- [ ] `tests/integration/test_api_auth.py` contains automated tests verifying `GET /api/me` with malformed header scheme (e.g. `Authorization: Basic 12345`) returns HTTP 401 Unauthorized.
- [ ] `tests/integration/test_api_auth.py` contains automated tests verifying `get_current_user` provisions new user record in database if user does not exist upon initial Mini App authentication (REQ-USR-01).
- [ ] `tests/integration/test_api_auth.py` contains automated tests verifying `get_current_user` returns existing user record without duplicating or overwriting existing timezone (REQ-USR-01, REQ-NFR-02).
- [ ] All tests execute against an isolated in-memory SQLite database sessionmaker with zero real network requests per `_docs/testing-guidelines.md`.
- [ ] All test functions contain docstrings referencing requirement IDs (`REQ-API-01`, `REQ-USR-01`, `REQ-NFR-02`).
- [ ] Running `uv run pytest tests/integration/test_api_auth.py` passes with 0 errors and 0 failures.
- [ ] Running `uv run pytest` executes the complete test suite and passes with 0 errors and 0 failures.

### Out of scope

- Mini App REST API endpoints for tasks (`GET /api/tasks`, `POST /api/tasks`, `PATCH /api/tasks/{id}`, `DELETE /api/tasks/{id}`), moved to #10
- Frontend React + Vite + Tailwind Mini App scaffold and Telegram WebApp SDK initialization, moved to #11
- Mini App interactive today checklist UI and task creation modal, moved to #12
- Timezone-aware background scheduler jobs (00:00 rollover & 09:00 push), moved to #13
- Scheduled deadline proximity push notifications (-1h and -10m), moved to #14
- Mini App calendar view and activity indicator endpoints, moved to #15
- Mini App productivity dashboard and streak analytics endpoints, moved to #16
- User settings endpoints and UI, moved to #17
- Production deployment, Docker Compose, and unified runner script (`main.py`), moved to #18

### Constraints

- Files this should stay inside: `src/api/app.py`, `src/api/auth.py`, `src/api/deps.py`, `src/api/routes/__init__.py`, `src/api/__init__.py`, `tests/integration/test_api_auth.py`
- Libraries to use: `fastapi` (`FastAPI`, `Depends`, `HTTPException`, `status`, `Request`), `fastapi.middleware.cors.CORSMiddleware`, `fastapi.testclient.TestClient`, `pydantic>=2.0`, `sqlalchemy>=2.0` (`AsyncSession`, `async_sessionmaker`), Python standard library (`hmac`, `hashlib`, `urllib.parse`, `json`, `time`), `pytest`, `pytest-asyncio`
- Do not add new dependencies to `pyproject.toml` without explicit permission per `Agents.md`
- Follow testing conventions in `_docs/testing-guidelines.md` (isolated in-memory SQLite fixture, `@pytest.mark.asyncio`, zero real network requests, REQ docstrings)
- Enforce tenant isolation and authentication security per `REQ-API-01` and `REQ-NFR-02`
- Follow modular architectural structure defined in `_docs/schema.md`
- Do not implement task CRUD endpoints (#10) or frontend components (#11, #12) in this task

## 10. Task REST API Endpoints for Mini App

### Goal

Build and register authenticated REST API endpoints under `/api/tasks` in FastAPI for retrieving, creating, viewing, updating, toggling status, and deleting tasks for the Telegram Mini App, strictly enforcing tenant isolation and validating request payloads with comprehensive integration test coverage.

### Acceptance criteria

- [ ] `src/api/routes/tasks.py` defines `router = APIRouter(prefix="/api/tasks", tags=["tasks"])`.
- [ ] `src/api/routes/tasks.py` implements `GET /api/tasks` with optional query parameter `date: date | None = Query(default=None)` (REQ-API-02).
- [ ] If `date` query parameter is omitted or `None`, `GET /api/tasks` defaults to the user's current calendar date computed via `get_user_local_time(current_user).date()` using the authenticated user's timezone.
- [ ] `GET /api/tasks` retrieves tasks via `get_tasks_for_date(session=session, user_id=current_user.telegram_id, target_date=target_date)`.
- [ ] `GET /api/tasks` returns a JSON list matching `list[TaskRead]` schema with HTTP 200 OK.
- [ ] `GET /api/tasks` returns tasks ordered strictly: uncompleted tasks (`TaskStatus.todo`) first sorted by priority (`TaskPriority.high` -> `TaskPriority.medium` -> `TaskPriority.low`), followed by completed tasks (`TaskStatus.done`), then by `created_at` ascending and `id` ascending (REQ-API-02).
- [ ] `GET /api/tasks` returns an empty list `[]` with HTTP 200 OK when no tasks exist for the specified date.
- [ ] `GET /api/tasks` strictly filters results by `current_user.telegram_id` and never returns tasks owned by other users (REQ-NFR-02).
- [ ] Calling `GET /api/tasks` with an invalid date string format (e.g. `date=invalid-date`) returns HTTP 422 Unprocessable Entity.
- [ ] `src/api/routes/tasks.py` implements `POST /api/tasks` accepting a JSON payload validated against `TaskCreate` schema (REQ-TSK-01, REQ-API-02).
- [ ] `POST /api/tasks` creates a task via `create_task(session=session, user_id=current_user.telegram_id, data=payload)` with initial `status=TaskStatus.todo`, `reminder_sent_1h=False`, `reminder_sent_10m=False`.
- [ ] `POST /api/tasks` returns the newly created task serialized as `TaskRead` with HTTP 201 Created (`status_code=status.HTTP_201_CREATED`, `response_model=TaskRead`).
- [ ] Calling `POST /api/tasks` with invalid data (e.g. missing title, empty string title, or invalid date format) returns HTTP 422 Unprocessable Entity without inserting records into the database.
- [ ] `src/api/routes/tasks.py` implements `GET /api/tasks/{task_id}` accepting path parameter `task_id: int`.
- [ ] `GET /api/tasks/{task_id}` retrieves the task via `get_task(session=session, task_id=task_id, user_id=current_user.telegram_id)`.
- [ ] `GET /api/tasks/{task_id}` returns the task serialized as `TaskRead` with HTTP 200 OK if found and owned by `current_user.telegram_id`.
- [ ] Calling `GET /api/tasks/{task_id}` for a non-existent `task_id` raises `HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")`.
- [ ] Calling `GET /api/tasks/{task_id}` for a `task_id` belonging to another user raises `HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")`, preventing cross-tenant leakage (REQ-NFR-02).
- [ ] `src/api/routes/tasks.py` implements `PATCH /api/tasks/{task_id}` accepting path parameter `task_id: int` and JSON payload validated against `TaskUpdate` schema for partial updates (REQ-API-02).
- [ ] `PATCH /api/tasks/{task_id}` updates fields via `update_task(session=session, task_id=task_id, user_id=current_user.telegram_id, data=payload)`.
- [ ] `PATCH /api/tasks/{task_id}` returns the updated task serialized as `TaskRead` with HTTP 200 OK.
- [ ] Calling `PATCH /api/tasks/{task_id}` with a new `deadline_at` resets reminder flags `reminder_sent_1h=False` and `reminder_sent_10m=False`.
- [ ] Calling `PATCH /api/tasks/{task_id}` for a non-existent `task_id` raises `HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")`.
- [ ] Calling `PATCH /api/tasks/{task_id}` for a `task_id` belonging to another user raises `HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")` and does not mutate the record (REQ-NFR-02).
- [ ] Calling `PATCH /api/tasks/{task_id}` with invalid update fields (e.g. empty string title or invalid status) returns HTTP 422 Unprocessable Entity.
- [ ] `src/api/routes/tasks.py` implements `PATCH /api/tasks/{task_id}/toggle` convenience endpoint accepting path parameter `task_id: int` for checklist toggling (REQ-TSK-02).
- [ ] `PATCH /api/tasks/{task_id}/toggle` toggles status: if current `status == TaskStatus.done`, sets `TaskStatus.todo`; otherwise sets `TaskStatus.done` via `toggle_task_status(session=session, task_id=task_id, user_id=current_user.telegram_id, new_status=new_status)`.
- [ ] `PATCH /api/tasks/{task_id}/toggle` returns the updated task serialized as `TaskRead` with HTTP 200 OK.
- [ ] Calling `PATCH /api/tasks/{task_id}/toggle` for a non-existent `task_id` raises `HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")`.
- [ ] Calling `PATCH /api/tasks/{task_id}/toggle` for a `task_id` belonging to another user raises `HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")` and does not modify the task status (REQ-TSK-02, REQ-NFR-02).
- [ ] `src/api/routes/tasks.py` implements `DELETE /api/tasks/{task_id}` accepting path parameter `task_id: int` (REQ-API-02).
- [ ] `DELETE /api/tasks/{task_id}` deletes the task via `delete_task(session=session, task_id=task_id, user_id=current_user.telegram_id)`.
- [ ] `DELETE /api/tasks/{task_id}` returns HTTP 204 No Content with an empty response body when the task is successfully deleted.
- [ ] Calling `DELETE /api/tasks/{task_id}` for a non-existent `task_id` raises `HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")`.
- [ ] Calling `DELETE /api/tasks/{task_id}` for a `task_id` belonging to another user raises `HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")` and leaves the database record intact (REQ-NFR-02).
- [ ] All endpoints in `src/api/routes/tasks.py` require authentication via `current_user: User = Depends(get_current_user)` and database session via `session: AsyncSession = Depends(get_db_session)`.
- [ ] Calling any task endpoint without valid Telegram `initData` in `Authorization` header (`tma <data>` or `Bearer <data>`) or `X-Telegram-Init-Data` header returns HTTP 401 Unauthorized (REQ-API-01).
- [ ] `src/api/routes/__init__.py` imports and exposes `tasks_router` from `src.api.routes.tasks`.
- [ ] `src/api/app.py` includes `tasks_router` on the FastAPI application instance.
- [ ] `src/api/__init__.py` imports and exposes `tasks_router`.
- [ ] `tests/integration/test_api_tasks.py` contains automated integration tests executing against an isolated in-memory SQLite database using `TestClient` with valid signed `initData`.
- [ ] Automated tests verify `GET /api/tasks` without `date` defaults to user local date in their configured timezone.
- [ ] Automated tests verify `GET /api/tasks?date=YYYY-MM-DD` returns tasks for the specified date sorted by status (`todo` before `done`) and priority (`high` -> `medium` -> `low`) (REQ-API-02).
- [ ] Automated tests verify `GET /api/tasks` returns `[]` when no tasks exist for the date.
- [ ] Automated tests verify `GET /api/tasks` strictly filters by authenticated user, excluding other users' tasks (REQ-NFR-02).
- [ ] Automated tests verify `POST /api/tasks` persists task with `status=todo`, `user_id=current_user.telegram_id`, and returns HTTP 201 Created and `TaskRead` (REQ-TSK-01, REQ-API-02).
- [ ] Automated tests verify `POST /api/tasks` with invalid payload returns HTTP 422 Unprocessable Entity.
- [ ] Automated tests verify `GET /api/tasks/{task_id}` returns task for owner with HTTP 200 and `TaskRead`.
- [ ] Automated tests verify `GET /api/tasks/{task_id}` returns HTTP 404 Not Found for non-existent or other user's task ID (REQ-NFR-02).
- [ ] Automated tests verify `PATCH /api/tasks/{task_id}` updates fields, resets reminder flags when `deadline_at` changes, and returns HTTP 200 and updated `TaskRead`.
- [ ] Automated tests verify `PATCH /api/tasks/{task_id}` returns HTTP 404 Not Found for non-existent or other user's task ID (REQ-NFR-02).
- [ ] Automated tests verify `PATCH /api/tasks/{task_id}/toggle` toggles status from `todo` to `done` and from `done` to `todo`, returning HTTP 200 and updated `TaskRead` (REQ-TSK-02).
- [ ] Automated tests verify `PATCH /api/tasks/{task_id}/toggle` returns HTTP 404 Not Found for non-existent or other user's task ID (REQ-NFR-02).
- [ ] Automated tests verify `DELETE /api/tasks/{task_id}` removes the task, returns HTTP 204 No Content, and subsequent `GET` returns HTTP 404 Not Found.
- [ ] Automated tests verify `DELETE /api/tasks/{task_id}` returns HTTP 404 Not Found for non-existent or other user's task ID without modifying database (REQ-NFR-02).
- [ ] Automated tests verify all task endpoints return HTTP 401 Unauthorized when authentication credentials are missing or invalid (REQ-API-01).
- [ ] All test functions contain docstrings referencing requirement IDs (`REQ-API-02`, `REQ-TSK-01`, `REQ-TSK-02`, `REQ-NFR-02`, `REQ-API-01`).
- [ ] Running `uv run pytest tests/integration/test_api_tasks.py` executes all task API integration tests and passes with 0 errors and 0 failures.
- [ ] Running `uv run pytest` executes the complete test suite and passes with 0 errors and 0 failures.

### Out of scope

- Telegram Mini App frontend React scaffold and Telegram SDK initialization, moved to #11
- Mini App interactive checklist UI, task cards, and creation modal, moved to #12
- Recurring task automatic rollover and generation logic (REQ-TMA-02), moved to #12
- Timezone-aware background scheduler jobs (00:00 rollover & 09:00 push), moved to #13
- Scheduled deadline proximity push notifications (-1h and -10m), moved to #14
- Mini App calendar view and activity indicator endpoints (`GET /api/tasks/calendar-summary`), moved to #15
- Mini App productivity dashboard and streak analytics endpoints (`GET /api/tasks/analytics`), moved to #16
- User settings endpoints and UI (`PATCH /api/settings/timezone`), moved to #17
- Production deployment, Docker Compose, and unified runner script (`main.py`), moved to #18

### Constraints

- Files this should stay inside: `src/api/routes/tasks.py`, `src/api/routes/__init__.py`, `src/api/app.py`, `src/api/__init__.py`, `tests/integration/test_api_tasks.py`
- Libraries to use: `fastapi` (`APIRouter`, `Depends`, `HTTPException`, `status`, `Query`, `Path`), `fastapi.testclient.TestClient`, `sqlalchemy>=2.0` (`AsyncSession`), `pydantic>=2.0`, `datetime` and `zoneinfo` (Python standard library), `pytest`, `pytest-asyncio`
- Do not add new dependencies to `pyproject.toml` without explicit permission per `Agents.md`
- Reuse existing service functions in `src/services/task_service.py` (`create_task`, `get_task`, `get_tasks_for_date`, `update_task`, `toggle_task_status`, `delete_task`) and `src/services/user_service.py` (`get_user_local_time`) rather than writing raw database queries in route handlers
- Use authentication dependency `src.api.auth.get_current_user` and database session dependency `src.api.deps.get_db_session`
- Strictly enforce tenant isolation per `REQ-NFR-02` (all task access is filtered by `current_user.telegram_id`, cross-tenant access returns HTTP 404 Not Found)
- Follow testing conventions in `_docs/testing-guidelines.md` (isolated in-memory SQLite fixture, `@pytest.mark.asyncio`, zero real network requests, REQ docstrings)
- Follow modular architectural structure defined in `_docs/schema.md`
- Do not implement frontend UI components or background scheduler jobs in this task

## 11. Telegram Mini App Frontend Setup

### Goal

Scaffold and configure the Telegram Mini App frontend inside `frontend/` using Vite, React, TypeScript, Tailwind CSS, and `@telegram-apps/sdk-react`, integrating Telegram WebApp theme variables and viewport expansion, setting up an authenticated API client with mock fallback for local browser development, implementing an initial greeting screen calling `GET /api/me`, serving the built frontend assets from FastAPI with SPA routing fallback, and verifying the setup with automated tests.

### Acceptance criteria

- [ ] `frontend/` directory is created in repository root containing the Vite + React + TypeScript + Tailwind CSS project structure.
- [ ] `frontend/package.json` defines project metadata (`"type": "module"`), dependencies (`react`, `react-dom`, `@telegram-apps/sdk-react`, `lucide-react`), and devDependencies (`vite`, `@vitejs/plugin-react`, `typescript`, `@types/react`, `@types/react-dom`, `tailwindcss`, `postcss`, `autoprefixer`).
- [ ] `frontend/package.json` defines scripts: `"dev": "vite"`, `"build": "tsc && vite build"`, `"preview": "vite preview"`, and `"typecheck": "tsc --noEmit"`.
- [ ] `frontend/vite.config.ts` configures `@vitejs/plugin-react`, sets `build.outDir` to `"dist"`, and configures development proxy for `/api` pointing to FastAPI backend (e.g. `http://localhost:8000`).
- [ ] `frontend/tsconfig.json` and `frontend/tsconfig.node.json` configure TypeScript with strict type checking enabled, `"jsx": "react-jsx"`, and Vite module resolution.
- [ ] `frontend/tailwind.config.js` and `frontend/postcss.config.js` configure content paths `["./index.html", "./src/**/*.{js,ts,jsx,tsx}"]` and theme color tokens mapping to Telegram CSS variables:
  - `bg-background`: `var(--tg-theme-bg-color, #ffffff)`
  - `bg-secondary`: `var(--tg-theme-secondary-bg-color, #f4f4f5)`
  - `text-foreground`: `var(--tg-theme-text-color, #000000)`
  - `text-muted`: `var(--tg-theme-hint-color, #71717a)`
  - `bg-primary`: `var(--tg-theme-button-color, #2481cc)`
  - `text-primary-foreground`: `var(--tg-theme-button-text-color, #ffffff)`.
- [ ] `frontend/index.html` includes viewport `<meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no, viewport-fit=cover">`, loads `<script src="https://telegram.org/js/telegram-web-app.js"></script>`, and mounts root `<div id="root"></div>`.
- [ ] `frontend/src/index.css` imports Tailwind directives (`@tailwind base; @tailwind components; @tailwind utilities;`), defines fallback Telegram theme CSS variables, and adds mobile safe-area padding support (`env(safe-area-inset-top)` and `env(safe-area-inset-bottom)`).
- [ ] `frontend/src/main.tsx` mounts the application root component wrapped in `<React.StrictMode>`.
- [ ] On application mount, the Mini App invokes `ready()` and `expand()` via the Telegram WebApp SDK or `window.Telegram?.WebApp` to expand the viewport per `_docs/design-system.md`.
- [ ] The app handles initialization outside the Telegram client environment (e.g. in standard desktop web browsers) safely without throwing unhandled exceptions or crashing.
- [ ] Theme detection identifies whether the Telegram client is in dark mode or light mode (via Telegram `colorScheme` or `isDark` boolean) and applies corresponding styling.
- [ ] `frontend/src/api/types.ts` defines TypeScript interface `UserProfile` matching the backend `UserRead` schema (`telegram_id: number; timezone: string; created_at: string;`).
- [ ] `frontend/src/api/client.ts` implements a centralized HTTP client helper that extracts raw `initData` from the Telegram SDK launch parameters or `window.Telegram?.WebApp?.initData`.
- [ ] If `initData` is empty/absent (e.g. browser development outside Telegram), `client.ts` falls back to mock credentials or `VITE_DEV_INIT_DATA` environment variable to enable local development and testing.
- [ ] All outgoing API requests from `frontend/src/api/client.ts` automatically attach the `Authorization: tma <raw_init_data>` header when `initData` is available (REQ-API-01).
- [ ] `frontend/src/api/client.ts` provides `fetchCurrentUser(): Promise<UserProfile>` that issues a `GET` request to `/api/me`.
- [ ] `frontend/src/App.tsx` calls `fetchCurrentUser()` on mount and renders an initial greeting screen.
- [ ] `frontend/src/App.tsx` displays a loading skeleton or spinner while user data is being fetched.
- [ ] `frontend/src/App.tsx` displays an informative error card with a retry button if the initial API call fails.
- [ ] On successful retrieval, `frontend/src/App.tsx` renders:
  - Header with title "Telegram Task Tracker" and a Telegram Mini App status badge.
  - User identifier card displaying `telegram_id` (or username if available).
  - Timezone badge displaying the user's timezone (e.g., `Europe/Kyiv`).
  - Theme mode indicator badge displaying current mode (`Dark` / `Light`).
  - Connection status indicator badge ("Connected" with a green status indicator).
- [ ] Running `npm run typecheck` (or `npx tsc --noEmit`) in `frontend/` succeeds with exit code 0 and 0 type errors.
- [ ] Running `npm run build` in `frontend/` succeeds with exit code 0 and outputs production assets to `frontend/dist/index.html`.
- [ ] `src/api/app.py` checks whether `frontend/dist` directory exists on disk.
- [ ] When `frontend/dist` exists, `src/api/app.py` mounts static files and serves `index.html` at `/` with SPA fallback for non-API client routes.
- [ ] When `frontend/dist` exists, API routes (`/api/*`) and system endpoints (`/health`, `/docs`, `/openapi.json`) continue to take precedence and are not intercepted by the static file handler.
- [ ] When `frontend/dist` does not exist, `create_app()` initializes cleanly without throwing errors or failing to start.
- [ ] `tests/integration/test_frontend_build.py` contains automated tests verifying static file mounting and SPA fallback behavior when `frontend/dist` exists (or using a temporary static assets fixture).
- [ ] `tests/integration/test_frontend_build.py` verifies `GET /health` and `GET /api/me` remain accessible and unaffected by static file mounting.
- [ ] `tests/integration/test_frontend_build.py` contains docstrings referencing requirement IDs (`REQ-TMA-01`, `REQ-API-01`).
- [ ] Running `uv run pytest tests/integration/test_frontend_build.py` passes with exit code 0.
- [ ] Running `uv run pytest` executes the entire test suite and passes with 0 errors and 0 failures.

### Out of scope

- Mini App interactive today checklist screen, task cards, strikethrough checkboxes, and creation modal (REQ-TMA-01), moved to #12
- Recurring task automatic rollover and generation logic (REQ-TMA-02), moved to #12
- Timezone-aware background scheduler jobs (00:00 rollover & 09:00 push), moved to #13
- Scheduled deadline proximity push notifications (-1h and -10m), moved to #14
- Mini App calendar tab and monthly activity indicator endpoints (REQ-TMA-03), moved to #15
- Mini App productivity dashboard and streak analytics (REQ-TMA-04), moved to #16
- User settings UI for changing timezone and notification preferences (REQ-USR-02), moved to #17
- Production Dockerfile, Docker Compose, and multi-process runner script (`main.py`), moved to #18

### Constraints

- Files this should stay inside:
  - Frontend: `frontend/package.json`, `frontend/package-lock.json`, `frontend/vite.config.ts`, `frontend/tsconfig.json`, `frontend/tsconfig.node.json`, `frontend/tailwind.config.js` (or config files), `frontend/postcss.config.js`, `frontend/index.html`, `frontend/src/**`, `.gitignore`
  - Backend integration: `src/api/app.py`, `tests/integration/test_frontend_build.py`
- Libraries to use:
  - Frontend: React 18 or 19 (`react`, `react-dom`), `typescript`, `vite`, `@vitejs/plugin-react`, `tailwindcss`, `postcss`, `autoprefixer`, `@telegram-apps/sdk-react` (or `@telegram-apps/sdk`), `lucide-react`
  - Backend: `fastapi`, `starlette.staticfiles.StaticFiles`, `pytest`, `pytest-asyncio`, `fastapi.testclient.TestClient`
- Dependencies:
  - Python dependencies are strictly defined in `pyproject.toml` — do not add new Python dependencies without asking (`StaticFiles` is already provided by Starlette/FastAPI)
  - All frontend dependencies must be declared in `frontend/package.json`
- Guidelines:
  - Strictly follow UI and theming specifications in `_docs/design-system.md` (Telegram theme CSS variables, safe-area insets, `ready()`, `expand()`)
  - Strictly follow testing standards in `_docs/testing-guidelines.md` (zero network calls, isolated fixtures, requirement ID docstrings)
  - Ensure `frontend/node_modules/` and `frontend/dist/` are excluded from git tracking
  - Do not implement task checklist UI components (#12) or background scheduler jobs (#13) in this task

## 12. Mini App Interactive Today Checklist

### Goal

Build the interactive Today Checklist in the Telegram Mini App featuring task cards with animated circular checkboxes, strikethrough styling, priority badges, tags, deadline countdowns, recurrence badges, and quick deletion, backed by optimistic UI updates, native Telegram haptic feedback, a task creation modal dialog, and automated recurring task generation across days.

### Acceptance criteria

- [x] `frontend/src/api/types.ts` defines `TaskStatus` type union `'todo' | 'done' | 'canceled'` matching backend `TaskStatus` enum.
- [x] `frontend/src/api/types.ts` defines `TaskPriority` type union `'low' | 'medium' | 'high'` matching backend `TaskPriority` enum.
- [x] `frontend/src/api/types.ts` defines `TaskRead` interface containing `id: number`, `user_id: number`, `title: string`, `status: TaskStatus`, `priority: TaskPriority`, `tag: string | null`, `target_date: string`, `deadline_at: string | null`, `recurrence: string | null`, `reminder_sent_1h: boolean`, `reminder_sent_10m: boolean`, and `created_at: string`.
- [x] `frontend/src/api/types.ts` defines `TaskCreate` interface containing `title: string`, `target_date: string`, `deadline_at?: string | null`, `priority?: TaskPriority`, `tag?: string | null`, and `recurrence?: string | null`.
- [x] `frontend/src/api/types.ts` defines `TaskUpdate` interface containing optional fields `title?: string`, `target_date?: string`, `deadline_at?: string | null`, `priority?: TaskPriority`, `tag?: string | null`, `status?: TaskStatus`, and `recurrence?: string | null`.
- [x] `frontend/src/api/client.ts` implements and exports `fetchTasks(date?: string): Promise<TaskRead[]>` issuing `GET /api/tasks` (or `/api/tasks?date=${date}` if `date` is provided) with Telegram `Authorization: tma <initData>` header (REQ-API-01, REQ-API-02).
- [x] `frontend/src/api/client.ts` implements and exports `createTask(payload: TaskCreate): Promise<TaskRead>` issuing `POST /api/tasks` with JSON payload and Telegram `Authorization` header (REQ-TSK-01, REQ-API-02).
- [x] `frontend/src/api/client.ts` implements and exports `toggleTask(taskId: number): Promise<TaskRead>` issuing `PATCH /api/tasks/${taskId}/toggle` with Telegram `Authorization` header (REQ-TSK-02).
- [x] `frontend/src/api/client.ts` implements and exports `updateTask(taskId: number, payload: TaskUpdate): Promise<TaskRead>` issuing `PATCH /api/tasks/${taskId}` with JSON payload and Telegram `Authorization` header (REQ-API-02).
- [x] `frontend/src/api/client.ts` implements and exports `deleteTask(taskId: number): Promise<void>` issuing `DELETE /api/tasks/${taskId}` with Telegram `Authorization` header (REQ-API-02).
- [x] `TaskCard` renders an animated circular checkbox reflecting `task.status === 'done'`.
- [x] When `task.status === 'done'`, task title is rendered with strikethrough styling (`line-through`) and muted opacity (`opacity-60`) per `_docs/design-system.md` (REQ-TMA-01).
- [x] When `task.status === 'todo'`, task title is rendered with crisp normal text without strikethrough or reduced opacity.
- [x] `TaskCard` renders a priority badge styled per `_docs/design-system.md`:
  - High: `bg-red-500/10 text-red-500 border-red-500/20`
  - Medium: `bg-amber-500/10 text-amber-500 border-amber-500/20`
  - Low: `bg-slate-500/10 text-slate-400 border-slate-500/20`.
- [x] When `task.tag` is present, `TaskCard` renders a tag chip displaying `#{task.tag}`.
- [x] When `task.deadline_at` is present, `TaskCard` renders a deadline countdown/indicator displaying formatted time (e.g. `🕒 15:00`).
- [x] When `task.recurrence` is present, `TaskCard` renders a recurrence badge (e.g. `🔁 Щодня` for `daily`, or `🔁 Будні` for `weekdays:[0,1,2,3,4]`).
- [x] Clicking the circular checkbox invokes `onToggle(task.id)` and triggers Telegram haptic feedback `impactOccurred('light')` via `window.Telegram?.WebApp?.HapticFeedback` when available per `_docs/design-system.md`.
- [x] `TaskCard` renders a delete action button; clicking it invokes `onDelete(task.id)` and triggers Telegram haptic feedback `impactOccurred('medium')` via `window.Telegram?.WebApp?.HapticFeedback` when available per `_docs/design-system.md`.
- [x] State transitions between `todo` and `done` render smooth animated transitions.
- [x] `TaskCreationModal` renders an accessible modal dialog or bottom sheet when `isOpen` is true and does not render when `isOpen` is false.
- [x] Modal contains a required text input for `title` (max 255 characters).
- [x] Modal contains a priority selector allowing the user to select between `low`, `medium`, and `high`, defaulting to `medium`.
- [x] Modal contains an optional text input for `tag` (max 50 characters, automatically stripping `#`).
- [x] Modal contains an optional time input for `deadline` (HH:MM) that combines with the task's target date.
- [x] Modal contains a recurrence selector with choices: None (`null`), Daily (`daily`), and Weekdays (`weekdays:[0,1,2,3,4]`).
- [x] Modal submit button is disabled when `title` is empty or contains only whitespace.
- [x] Submitting the form calls `onSubmit(payload)` with formatted `TaskCreate` data and closes the modal on success.
- [x] Clicking the cancel button or backdrop invokes `onClose()` and dismisses the modal without submitting.
- [x] `TodayChecklist` renders a header with progress counter displaying "X з Y виконано" (e.g. "2 з 5 виконано") and a visual progress bar indicating the completion percentage.
- [x] When 0 tasks exist for today, renders an empty state card with an icon, message ("На сьогодні завдань немає"), and prompt to add tasks.
- [x] When tasks exist, renders task cards ordered with `todo` tasks first sorted by priority (high -> medium -> low), followed by `done` tasks.
- [x] Implements optimistic UI update on status toggle: toggling a checkbox immediately flips task status between `todo` and `done` and updates the progress counter in local state; if the backend API call fails, changes are rolled back to the prior state and an error notification is shown (REQ-TMA-01).
- [x] Implements optimistic UI update on deletion: clicking delete immediately removes the task from local state and updates the counter; if the backend API call fails, the task is restored to the list and an error notification is shown.
- [x] Renders a prominent Floating Action Button (FAB) or button labeled `+ Додати завдання` that opens `TaskCreationModal`.
- [x] When a new task is created via `TaskCreationModal`, it is immediately added to the checklist and the progress counter updates.
- [x] `frontend/src/App.tsx` embeds `TodayChecklist` as the primary screen of the Mini App.
- [x] On mount, fetches today's tasks via `fetchTasks()` in addition to user profile details.
- [x] Displays a loading skeleton or indicator while checklist data is loading.
- [x] Renders an error banner with a retry action if fetching tasks fails.
- [x] `src/services/task_service.py` defines async `ensure_recurring_tasks_for_date(session: AsyncSession, user_id: int, target_date: date) -> list[Task]` (REQ-TMA-02).
- [x] `ensure_recurring_tasks_for_date` queries recurring tasks (`recurrence.isnot(None)`) owned by `user_id` where `target_date < target_date`.
- [x] For each recurring rule matching `target_date` (`daily` every day; `weekdays:[...]` matching `target_date.weekday()`):
  - Checks if an instance with the same title and recurrence rule already exists for `target_date` under `user_id`.
  - If no instance exists for `target_date`, creates a new task instance for `target_date` with `status=TaskStatus.todo`, copying `title`, `priority`, `tag`, `recurrence`, and relative `deadline_at` (adjusted to `target_date`), with `reminder_sent_1h=False` and `reminder_sent_10m=False`.
- [x] `GET /api/tasks` invokes `ensure_recurring_tasks_for_date` for `target_date` before returning results so recurring tasks automatically appear in the checklist on new days (REQ-TMA-02).
- [x] `src/services/__init__.py` imports and exposes `ensure_recurring_tasks_for_date`.
- [x] `tests/integration/test_checklist_api_flow.py` contains automated integration tests using `TestClient` and in-memory SQLite fixture with valid signed `initData`.
- [x] Automated tests verify the complete checklist API flow: initial empty list retrieval, task creation with priority, tag, deadline, and recurrence, status toggle to `done` and back to `todo`, task update, and task deletion.
- [x] Automated tests verify recurring task generation: calling `GET /api/tasks?date=YYYY-MM-DD` for a new date automatically creates a `todo` task instance for `daily` and matching `weekdays` recurring tasks (REQ-TMA-02).
- [x] Automated tests verify tenant isolation: requests to toggle or delete another user's task return HTTP 404 and do not modify database records (REQ-NFR-02).
- [x] All test functions contain docstrings referencing requirement IDs (`REQ-TMA-01`, `REQ-TMA-02`, `REQ-API-02`, `REQ-TSK-01`, `REQ-TSK-02`, `REQ-NFR-02`).
- [x] Running `npm run typecheck` (or `npx tsc --noEmit`) in `frontend/` succeeds with exit code 0 and 0 errors.
- [x] Running `npm run build` in `frontend/` succeeds with exit code 0 and updates static production assets in `frontend/dist/`.
- [x] Running `uv run pytest tests/integration/test_checklist_api_flow.py` passes with exit code 0.
- [x] Running `uv run pytest` executes the complete test suite and passes with 0 errors and 0 failures.

### Out of scope

- Mini App Calendar view tab and monthly activity indicator endpoints (`GET /api/tasks/calendar-summary`), moved to #15
- Mini App productivity dashboard, completion rate charts, and daily streaks (`GET /api/tasks/analytics`), moved to #16
- User settings UI for configuring timezones and reminder intervals (`PATCH /api/settings/timezone`), moved to #17
- APScheduler timezone-aware background jobs (00:00 rollover & 09:00 push), moved to #13
- Scheduled deadline proximity push notifications (-1h and -10m), moved to #14
- Production deployment, Docker Compose, and unified runner script (`main.py`), moved to #18

### Constraints

- Files this should stay inside:
  - Frontend: `frontend/src/api/types.ts`, `frontend/src/api/client.ts`, `frontend/src/components/TaskCard.tsx`, `frontend/src/components/TaskCreationModal.tsx`, `frontend/src/components/TodayChecklist.tsx`, `frontend/src/App.tsx`, `frontend/dist/**`
  - Backend: `src/services/task_service.py`, `src/services/__init__.py`, `src/api/routes/tasks.py`, `tests/integration/test_checklist_api_flow.py`
- Libraries to use:
  - Frontend: React 18, TypeScript, Tailwind CSS, `lucide-react`, `@telegram-apps/sdk-react`
  - Backend: FastAPI, SQLAlchemy 2.0 (`AsyncSession`, `select`), Pydantic 2, pytest, pytest-asyncio, `fastapi.testclient.TestClient`
- Do not add new dependencies to `pyproject.toml` or `package.json` without asking per `Agents.md`
- Follow design system guidelines in `_docs/design-system.md` (priority badges, strikethrough, haptic feedback, safe area insets)
- Follow testing conventions in `_docs/testing-guidelines.md` (isolated in-memory SQLite fixture, `@pytest.mark.asyncio`, zero real network calls, REQ docstrings)
- Strictly enforce tenant isolation per `REQ-NFR-02`


## 13. Timezone-Aware Background Scheduler (00:00 & 09:00 Triggers)

### Goal

Implement an APScheduler background service using `AsyncIOScheduler` that runs periodic minute-by-minute checks across all registered users to trigger timezone-aware 00:00 midnight rollover review dialogues and 09:00 morning digest pushes with Telegram Mini App launch buttons, complete with restart-resilient database idempotency tracking, robust per-user exception isolation, graceful Telegram error handling (including blocked bots), and 100% automated integration test coverage.

### Acceptance criteria

- [x] `src/models/user.py` updates the `User` model with `last_midnight_review_date: Mapped[date | None] = mapped_column(Date, nullable=True, default=None)` to persist the calendar date of the last triggered 00:00 review (REQ-SCH-01, REQ-NFR-03).
- [x] `src/models/user.py` updates the `User` model with `last_morning_push_date: Mapped[date | None] = mapped_column(Date, nullable=True, default=None)` to persist the calendar date of the last triggered 09:00 morning push (REQ-SCH-02, REQ-NFR-03).
- [x] Both fields default to `None` for newly created users and support existing user instances without breaking database migrations or existing queries.
- [x] `src/scheduler/jobs.py` defines async function `process_user_midnight_rollover(bot: Bot, session: AsyncSession, user: User, now_dt: datetime | None = None) -> bool` (REQ-SCH-01).
- [x] `process_user_midnight_rollover` computes the user's local datetime using `get_user_local_time(user, now_dt)`.
- [x] `process_user_midnight_rollover` checks if the user's local time is in the 00:00 window (`local_time.hour == 0 and local_time.minute == 0`); returns `False` if not in the window.
- [x] Idempotency Check: if `user.last_midnight_review_date == local_time.date()`, `process_user_midnight_rollover` returns `False` immediately without sending any messages or re-evaluating tasks (REQ-SCH-01, REQ-NFR-03).
- [x] When eligible (00:00 and not yet triggered today):
  - Calls `send_midnight_rollover_dialogue(bot=bot, session=session, user=user, reference_date=local_time.date())` (REQ-SCH-01).
  - When the user has zero overdue tasks, sends the congratulatory message (`✨ Всі вчорашні завдання виконано!...`) without inline keyboards (REQ-SCH-01).
  - When the user has one or more overdue tasks, sends the batch overview control message with `get_batch_rollover_keyboard` and individual task messages with `get_task_rollover_keyboard` (REQ-SCH-01).
  - Updates `user.last_midnight_review_date = local_time.date()` and commits the database transaction.
  - Returns `True`.
- [x] `src/scheduler/jobs.py` defines async function `process_user_morning_push(bot: Bot, session: AsyncSession, user: User, webapp_url: str | None = None, now_dt: datetime | None = None) -> bool` (REQ-SCH-02).
- [x] `process_user_morning_push` computes the user's local datetime using `get_user_local_time(user, now_dt)`.
- [x] `process_user_morning_push` checks if the user's local time is in the 09:00 window (`local_time.hour == 9 and local_time.minute == 0`); returns `False` if not in the window.
- [x] Idempotency Check: if `user.last_morning_push_date == local_time.date()`, `process_user_morning_push` returns `False` immediately without sending any messages (REQ-SCH-02, REQ-NFR-03).
- [x] When eligible (09:00 and not yet triggered today):
  - Calls `ensure_recurring_tasks_for_date(session=session, user_id=user.telegram_id, target_date=local_time.date())` so any daily or matching weekday recurring tasks are generated before digest creation (REQ-TMA-02).
  - Queries tasks for today using `get_tasks_for_date(session=session, user_id=user.telegram_id, target_date=local_time.date())`.
  - Filters pending tasks where `task.status == TaskStatus.todo`.
  - Generates inline keyboard with `[🚀 Відкрити план]` button using `get_start_keyboard(webapp_url)` (attaching `WebAppInfo(url=webapp_url)` when `webapp_url` is configured, or callback `open_plan` fallback) complying with `_docs/design-system.md` (REQ-SCH-02).
  - When pending tasks exist (`todo_tasks` is not empty):
    - Formats HTML morning digest message with header `📋 <b>План на сьогодні ({formatted_date}):</b>`, task count `У вас {count} запланованих завдань на сьогодні:`, and preview bulleted items with task titles, priority badges (`⚠️ Високий`, `⚡ Середній`, `💤 Низький`), category tags (`🏷️ #{tag}`), and deadlines (`🕒 до {time}`) per `_docs/design-system.md`.
    - Sends message to `chat_id=user.telegram_id` with the formatted digest text and the `[🚀 Відкрити план]` keyboard.
  - When zero pending tasks exist (`todo_tasks` is empty):
    - Formats HTML friendly morning message: `☀️ <b>Доброго ранку!</b>\n\nНа сьогодні у вас немає запланованих завдань.\nВідпочиньте або надиктуйте нові плани на день 🚀` per `_docs/design-system.md`.
    - Sends message to `chat_id=user.telegram_id` with the friendly text and the `[🚀 Відкрити план]` keyboard.
  - Updates `user.last_morning_push_date = local_time.date()` and commits the database transaction.
  - Returns `True`.
- [x] `src/scheduler/jobs.py` defines async function `run_timezone_checks(bot: Bot, sessionmaker: async_sessionmaker[AsyncSession], webapp_url: str | None = None, reference_time: datetime | None = None) -> dict[str, int]`.
- [x] `run_timezone_checks` opens an async database session using `sessionmaker()`, queries all registered users via `select(User)`, and iterates over each user.
- [x] Exception Isolation per User: processing for each individual user is wrapped in a dedicated `try...except` block so that a failure or exception for one user never prevents subsequent users from being processed.
- [x] Blocked Bot Handling: catches `TelegramForbiddenError` (or `TelegramAPIError` where the bot was blocked or deleted by the user), logs a warning (`User {telegram_id} has blocked the bot`), marks the trigger date for that user to avoid repeated attempts, and continues to the next user without crashing the job.
- [x] General Exception Handling: catches generic exceptions during a user's execution, logs the error and stack trace via `logger.exception(...)`, rolls back any pending transaction on the session, and continues processing the next user.
- [x] `run_timezone_checks` returns a dictionary of counters: `{"midnight_triggered": int, "morning_triggered": int, "errors": int}`.
- [x] `src/scheduler/manager.py` defines `create_scheduler() -> AsyncIOScheduler` initializing `AsyncIOScheduler(timezone="UTC")`.
- [x] `src/scheduler/manager.py` defines `setup_scheduler(scheduler: AsyncIOScheduler, bot: Bot, sessionmaker: async_sessionmaker[AsyncSession], webapp_url: str | None = None) -> AsyncIOScheduler`.
- [x] `setup_scheduler` registers a periodic job executing `run_timezone_checks(bot, sessionmaker, webapp_url)` scheduled to run every minute (e.g. `CronTrigger(second=0)` or `IntervalTrigger(minutes=1)`).
- [x] The registered job is configured with `id="timezone_checks"`, `name="Timezone-Aware Background Checks"`, `replace_existing=True`, `max_instances=1`, and `coalesce=True`.
- [x] `src/scheduler/manager.py` defines `start_scheduler(scheduler: AsyncIOScheduler) -> None` that starts the scheduler if it is not already running.
- [x] `src/scheduler/manager.py` defines `stop_scheduler(scheduler: AsyncIOScheduler, wait: bool = False) -> None` that cleanly shuts down the scheduler if it is running.
- [x] `src/scheduler/__init__.py` imports and exposes `create_scheduler`, `setup_scheduler`, `start_scheduler`, `stop_scheduler`, `run_timezone_checks`, `process_user_midnight_rollover`, and `process_user_morning_push`.
- [x] `tests/integration/test_scheduler.py` provides automated integration tests using the in-memory SQLite fixture `db_session` / `sessionmaker` and 100% mocked Telegram `Bot` via `unittest.mock.AsyncMock` with zero real network calls per `_docs/testing-guidelines.md`.
- [x] Automated tests verify `process_user_midnight_rollover` at local 00:00:
  - User with overdue tasks receives batch overview message and individual task messages with rollover keyboards, and `user.last_midnight_review_date` is updated (REQ-SCH-01).
  - User with 0 overdue tasks receives congratulatory message without keyboard, and `user.last_midnight_review_date` is updated (REQ-SCH-01).
  - When local time is not 00:00 (e.g. 23:59 or 00:01), no message is sent and `last_midnight_review_date` is unchanged.
- [x] Automated tests verify `process_user_morning_push` at local 09:00:
  - Calls `ensure_recurring_tasks_for_date`, populating recurring tasks for today before digest creation (REQ-TMA-02).
  - User with pending tasks receives morning digest with task count, formatted task items, and `[🚀 Відкрити план]` button, and `user.last_morning_push_date` is updated (REQ-SCH-02).
  - User with 0 pending tasks receives friendly morning message with `[🚀 Відкрити план]` button, and `user.last_morning_push_date` is updated (REQ-SCH-02).
  - When local time is not 09:00, no message is sent and `last_morning_push_date` is unchanged.
- [x] Automated tests verify timezone independence: multiple users configured in different timezones (e.g. `Asia/Tokyo`, `Europe/Kyiv`, `America/New_York`) are evaluated simultaneously, and triggers execute strictly for the user whose local clock matches 00:00 or 09:00.
- [x] Automated tests verify restart-resilient idempotency (REQ-NFR-03): executing `run_timezone_checks` multiple times in succession or after an application restart during the same minute does not dispatch duplicate messages once `last_midnight_review_date` or `last_morning_push_date` matches today's date.
- [x] Automated tests verify Telegram exception handling: when `bot.send_message` raises `TelegramForbiddenError` (bot blocked by user), the error is caught and logged, the trigger flag is recorded, and the process completes cleanly without an unhandled exception.
- [x] Automated tests verify per-user exception isolation: if an unexpected exception occurs while processing user 1, user 2 is still processed successfully and the error counter is incremented.
- [x] Automated tests verify scheduler lifecycle: `create_scheduler`, `setup_scheduler`, job configuration parameters, `start_scheduler`, and `stop_scheduler`.
- [x] All test functions contain docstrings referencing requirement IDs (`REQ-SCH-01`, `REQ-SCH-02`, `REQ-TMA-02`, `REQ-NFR-02`, `REQ-NFR-03`).
- [x] Running `uv run pytest tests/integration/test_scheduler.py` passes with 0 errors and 0 failures.
- [x] Running `uv run pytest` executes the complete test suite and passes with 0 errors and 0 failures.

### Out of scope

- Proactive deadline notification reminders (-1 hour and -10 minutes proximity checks with `reminder_sent_1h` and `reminder_sent_10m`), moved to #14
- Mini App calendar tab, monthly task counts, and date activity indicator endpoints (`GET /api/tasks/calendar-summary`), moved to #15
- Mini App productivity dashboard, completion rate charts, and daily streaks (`GET /api/tasks/analytics`), moved to #16
- User `/settings` command handler and timezone configuration UI (`PATCH /api/settings/timezone`), moved to #17
- Production multi-process startup runner, unified Dockerfile, and end-to-end deployment verification (`main.py`), moved to #18

### Constraints

- Files this should stay inside:
  - `src/models/user.py`
  - `src/scheduler/jobs.py`
  - `src/scheduler/manager.py`
  - `src/scheduler/__init__.py`
  - `tests/integration/test_scheduler.py`
- Libraries to use:
  - `apscheduler` (`from apscheduler.schedulers.asyncio import AsyncIOScheduler`, `from apscheduler.triggers.cron import CronTrigger` or `from apscheduler.triggers.interval import IntervalTrigger`)
  - `aiogram>=3.0` (`Bot`, `exceptions.TelegramForbiddenError`, `exceptions.TelegramAPIError`, `types.InlineKeyboardMarkup`, `types.InlineKeyboardButton`, `types.WebAppInfo`)
  - `sqlalchemy>=2.0` (`select`, `AsyncSession`, `async_sessionmaker`, `Date`)
  - Python standard library (`datetime`, `zoneinfo.ZoneInfo`, `logging`, `unittest.mock`)
  - `pytest`, `pytest-asyncio`
- Do not add new dependencies to `pyproject.toml` without explicit permission per `Agents.md` (`apscheduler` is already an existing dependency in `pyproject.toml`)
- Reuse existing service functions and handlers:
  - `send_midnight_rollover_dialogue` in `src/bot/handlers/rollover.py`
  - `get_start_keyboard` in `src/bot/keyboards/start.py`
  - `get_user_local_time` in `src/services/user_service.py`
  - `get_tasks_for_date` and `ensure_recurring_tasks_for_date` in `src/services/task_service.py`
- Follow testing conventions in `_docs/testing-guidelines.md` (isolated in-memory SQLite fixture, `@pytest.mark.asyncio`, zero real network requests to Telegram, requirement ID docstrings)
- Follow formatting and design guidelines in `_docs/design-system.md` (semantic emojis, clean HTML parse mode, `[🚀 Відкрити план]`, max 2 buttons per row)
- Strictly enforce tenant isolation per `REQ-NFR-02`
- Follow modular architectural structure defined in `_docs/schema.md`
- Do not write implementation code or modify code files in `src/` or `tests/` in this task

## 14. Deadline Notification Reminders (-1 Hour & -10 Minutes)

### Goal

Implement an automated background deadline monitoring service using APScheduler that periodically scans for pending tasks nearing their deadlines (at -1 hour and -10 minute thresholds), dispatches proactive Telegram notification messages with actionable inline buttons (`[✅ Виконано]` and `[⏰ +15 хв]`), handles completion and snooze callbacks with strict tenant isolation, guarantees database idempotency via persisted reminder flags, ensures per-task and per-user exception isolation, and is verified with 100% automated integration test coverage.

### Acceptance criteria

- [x] `src/scheduler/jobs.py` defines async function `run_deadline_checks(bot: Bot, sessionmaker: async_sessionmaker[AsyncSession], now_dt: datetime | None = None) -> dict[str, int]` (REQ-SCH-03).
- [x] `run_deadline_checks` opens an async database session using `sessionmaker()` and queries all tasks where `status == TaskStatus.todo` and `deadline_at is not None`.
- [x] If `now_dt` is not provided, it defaults to the current UTC datetime (`datetime.now(timezone.utc)`).
- [x] For each candidate task, `delta_sec = (task.deadline_at - now_dt).total_seconds()` is computed with both datetimes normalized to timezone-aware UTC.
- [x] **10-minute proximity check (-10m)**:
  - If `0 < delta_sec <= 600` and `not task.reminder_sent_10m`:
    - Sends 10-minute warning notification message to `chat_id=task.user_id` with inline keyboard `[✅ Виконано]` and `[⏰ +15 хв]` (REQ-SCH-03).
    - Sets `task.reminder_sent_10m = True` and `task.reminder_sent_1h = True` (to ensure 1h notification is not redundantly dispatched if task was created or scheduled directly within the 10m window).
    - Commits the transaction to the database.
    - Increments the `reminders_10m_sent` counter.
- [x] **1-hour proximity check (-1h)**:
  - If `600 < delta_sec <= 3600` (or `0 < delta_sec <= 3600`) and `not task.reminder_sent_1h`:
    - Sends 1-hour advance reminder notification message to `chat_id=task.user_id` with inline keyboard `[✅ Виконано]` and `[⏰ +15 хв]` (REQ-SCH-03).
    - Sets `task.reminder_sent_1h = True`.
    - Commits the transaction to the database.
    - Increments the `reminders_1h_sent` counter.
- [x] **Past deadlines (`delta_sec <= 0`)**:
  - Tasks whose deadlines have already passed (`delta_sec <= 0`) are ignored and do not trigger notifications.
- [x] **Completed / Canceled tasks**:
  - Tasks with status `TaskStatus.done` or `TaskStatus.canceled` are excluded from reminder processing and receive no alerts (REQ-SCH-03).
- [x] **Tasks without deadline (`deadline_at is None`)**:
  - Tasks without a deadline are excluded from reminder checks.
- [x] **Restart-Resilient Idempotency (REQ-NFR-03)**:
  - Repeating `run_deadline_checks` during the same minute or after an application restart does not dispatch duplicate reminders once `task.reminder_sent_1h` or `task.reminder_sent_10m` is set to `True`.
- [x] **Per-Task Exception Isolation (REQ-NFR-02)**:
  - Processing for each task is wrapped in a dedicated `try...except` block so that a failure or exception while dispatching to one user/task never halts or impacts notifications for other tasks.
- [x] **Telegram Exception & Blocked Bot Handling**:
  - Catches `TelegramForbiddenError` (or `TelegramAPIError` where the bot was blocked or deactivated by the user), logs a warning (`User {user_id} has blocked the bot`), marks the reminder flags as sent to prevent repeated retry attempts on subsequent checks, and continues cleanly.
  - Catches general exceptions, logs the error via `logger.exception(...)`, rolls back the database session (`await session.rollback()`), and increments the `errors` counter.
- [x] `run_deadline_checks` returns a statistics dictionary: `{"reminders_1h_sent": int, "reminders_10m_sent": int, "errors": int}`.
- [x] `src/bot/keyboards/deadline.py` defines `DeadlineCallback(CallbackData, prefix="deadline")` with fields `action: str`, `task_id: int`, `user_id: int`, and `minutes: int = 15`.
- [x] `src/bot/keyboards/deadline.py` defines `get_deadline_keyboard(task_id: int, user_id: int, snooze_minutes: int = 15) -> InlineKeyboardMarkup` adhering to `_docs/design-system.md` (max 2 buttons per row):
  - Row 1: `[✅ Виконано]` (`action="done"`) and `[⏰ +15 хв]` (`action="snooze"`, `minutes=snooze_minutes`).
- [x] Notification message formatting adheres to `_docs/design-system.md`:
  - 1-Hour Reminder HTML formatting:
    `⏳ <b>Нагадування про дедлайн!</b>\n\nЗалишилася 1 година до завершення:\n• <b>{task.title}</b> — {priority_badge} | {tag_badge} | 🕒 до {time}`
  - 10-Minute Reminder HTML formatting:
    `🚨 <b>Увага! Дедлайн через 10 хвилин!</b>\n\nЧас завершувати завдання:\n• <b>{task.title}</b> — {priority_badge} | {tag_badge} | 🕒 до {time}`
  - Priority badge: `⚠️ Високий` (high), `⚡ Середній` (medium), `💤 Низький` (low).
  - Category tag badge: `🏷️ #{tag}` if tag is set, or omitted if `None`.
  - Deadline time formatted in the user's local timezone (or HH:MM format).
- [x] `src/bot/handlers/deadline.py` defines `deadline_router = Router(name="deadline")` (or `router`).
- [x] `deadline_router` handles `DeadlineCallback.filter()` queries with strict tenant isolation (REQ-NFR-02):
  - If `callback_query.from_user.id != callback_data.user_id`: rejects callback with alert `"⚠️ Ви не можете керувати завданнями іншого користувача."` (`show_alert=True`) and leaves database unchanged.
- [x] If the referenced task does not exist or has been deleted: alerts user `"⚠️ Завдання не знайдено або вже видалено."` (`show_alert=True`), removes inline keyboard, and aborts.
- [x] **Done Callback (`action == "done"`)**:
  - If task is already `done`, alerts user `"⚠️ Завдання вже виконано."`, removes keyboard, and answers callback.
  - Updates task status to `TaskStatus.done` and commits transaction (REQ-TSK-02).
  - Updates the Telegram message to confirm completion: displays strikethrough title `<s>{task.title}</s>` and celebratory confirmation `✅ <b>Завдання виконано!</b>`, and removes inline keyboard (`reply_markup=None`) per `_docs/design-system.md`.
  - Answers callback query with `"✅ Виконано!"`.
- [x] **Snooze Callback (`action == "snooze"`)**:
  - If task is already `done`, alerts user `"⚠️ Завдання вже виконано."`, removes keyboard, and answers callback.
  - Extends `task.deadline_at` by `callback_data.minutes` (e.g. +15 minutes).
  - Updates `task.target_date = task.deadline_at.date()` if snooze extends the deadline into the next calendar date.
  - Resets reminder flags: sets `task.reminder_sent_10m = False`. If the new deadline is > 60 minutes away from current time, also sets `task.reminder_sent_1h = False`.
  - Commits transaction to database.
  - Updates Telegram message text to confirm extension: e.g. `⏰ <b>Дедлайн відкладено на +{minutes} хв!</b>\n\n• <b>{task.title}</b> — новий дедлайн: 🕒 {new_time}`, and updates inline keyboard.
  - Answers callback query with `"⏰ Відкладено на {minutes} хв"`.
- [x] `src/bot/handlers/__init__.py` exposes `deadline_router`.
- [x] `src/bot/keyboards/__init__.py` exposes `DeadlineCallback` and `get_deadline_keyboard`.
- [x] `src/bot/dispatcher.py` (`create_dispatcher`) registers `deadline_router`.
- [x] `src/scheduler/manager.py` updates `setup_scheduler`:
  - Registers periodic job for `run_deadline_checks(bot, sessionmaker)`.
  - Configures job with `id="deadline_checks"`, `name="Deadline Proximity Checks"`, `replace_existing=True`, `max_instances=1`, and `coalesce=True`.
  - Scheduled every minute using `CronTrigger(second=30, timezone="UTC")` (or `IntervalTrigger(minutes=1)`), staggered from the 00-second timezone checks.
- [x] `src/scheduler/__init__.py` exposes `run_deadline_checks`.
- [x] `tests/integration/test_deadline_reminders.py` provides automated integration tests using the in-memory SQLite fixture `db_session` / `session_factory` and mocked Telegram `Bot` via `unittest.mock.AsyncMock` with zero real network calls per `_docs/testing-guidelines.md`.
- [x] Automated tests verify 1-hour proximity trigger:
  - Task with deadline in 50 minutes, `status == todo`, and `reminder_sent_1h == False` dispatches 1h notification message, sets `reminder_sent_1h = True`, and leaves `reminder_sent_10m = False` (REQ-SCH-03).
- [x] Automated tests verify 10-minute proximity trigger:
  - Task with deadline in 8 minutes, `status == todo`, and `reminder_sent_10m == False` dispatches 10m notification message, sets `reminder_sent_10m = True`, and sets `reminder_sent_1h = True` (REQ-SCH-03).
- [x] Automated tests verify edge cases:
  - Task with deadline > 1 hour away (e.g. 75 minutes) does not dispatch notification; flags remain `False`.
  - Task with deadline in the past (`delta_sec <= 0`) does not dispatch notification; flags remain unchanged.
  - Task with status `done` or `canceled` does not dispatch notification even if deadline is in 5 minutes (REQ-SCH-03).
  - Task with `deadline_at is None` does not dispatch notification.
- [x] Automated tests verify idempotency:
  - Successive calls to `run_deadline_checks` do not dispatch duplicate notifications once flags are `True` (REQ-SCH-03, REQ-NFR-03).
- [x] Automated tests verify Done callback:
  - Tapping `[✅ Виконано]` updates task status to `done` in DB, edits Telegram message to crossed-out/confirmed state, and removes keyboard (REQ-TSK-02).
- [x] Automated tests verify Snooze callback:
  - Tapping `[⏰ +15 хв]` extends `deadline_at` by 15 minutes, resets `reminder_sent_10m = False`, and edits Telegram message confirming extension (REQ-SCH-03).
- [x] Automated tests verify tenant isolation:
  - Callback from an unauthorized user (`from_user.id != task.user_id`) produces warning alert and does not alter task state or deadline (REQ-NFR-02).
- [x] Automated tests verify error isolation and blocked bot:
  - `TelegramForbiddenError` during dispatch is caught and logged, reminder flags are marked to prevent retry storms, and other tasks/users continue processing cleanly.
  - Unexpected exception on task 1 does not prevent task 2 from receiving its reminder.
- [x] Automated tests verify scheduler registration:
  - `setup_scheduler` registers job `deadline_checks` with expected trigger and parameters.
- [x] All test functions contain docstrings referencing requirement IDs (`REQ-SCH-03`, `REQ-NFR-02`, `REQ-NFR-03`, `REQ-TSK-02`).
- [x] Running `uv run pytest tests/integration/test_deadline_reminders.py` passes with 0 errors and 0 failures.
- [x] Running `uv run pytest` executes the complete test suite and passes with 0 errors and 0 failures.

### Out of scope

- Interactive calendar view in Mini App and monthly task density endpoints (`GET /api/tasks/calendar-summary`), moved to #15
- Mini App productivity dashboard, completion rate charts, and daily streaks (`GET /api/tasks/analytics`), moved to #16
- User settings UI for configuring custom notification intervals, reminder preferences, and quiet hours (`/settings`), moved to #17
- Production deployment, Docker Compose, and unified multi-process runner script (`main.py`), moved to #18

### Constraints

- Files this should stay inside:
  - `src/scheduler/jobs.py`
  - `src/scheduler/manager.py`
  - `src/scheduler/__init__.py`
  - `src/bot/keyboards/deadline.py`
  - `src/bot/keyboards/__init__.py`
  - `src/bot/handlers/deadline.py`
  - `src/bot/handlers/__init__.py`
  - `src/bot/dispatcher.py`
  - `tests/integration/test_deadline_reminders.py`
- Libraries to use:
  - `aiogram>=3.0` (`Bot`, `Router`, `F`, `exceptions.TelegramForbiddenError`, `exceptions.TelegramAPIError`, `types.CallbackQuery`, `types.InlineKeyboardMarkup`, `types.InlineKeyboardButton`, `filters.callback_data.CallbackData`)
  - `apscheduler` (`AsyncIOScheduler`, `CronTrigger` or `IntervalTrigger`)
  - `sqlalchemy>=2.0` (`select`, `AsyncSession`, `async_sessionmaker`)
  - Python standard library (`datetime`, `timezone`, `timedelta`, `zoneinfo.ZoneInfo`, `logging`, `unittest.mock`)
  - `pytest`, `pytest-asyncio`
- Do not add new dependencies to `pyproject.toml` without explicit permission per `Agents.md` (all required dependencies are already present)
- Reuse existing models and service methods:
  - `Task` model in `src/models/task.py` (`reminder_sent_1h`, `reminder_sent_10m`, `deadline_at`, `status`, `user_id`, `priority`, `tag`)
  - `User` model in `src/models/user.py`
  - `get_task`, `toggle_task_status`, `update_task` in `src/services/task_service.py`
- Follow design system guidelines in `_docs/design-system.md` (semantic emojis `⏳`, `🚨`, `✅`, `⏰`, max 2 buttons per row, strikethrough for completed tasks, clean HTML parse mode)
- Follow testing conventions in `_docs/testing-guidelines.md` (isolated in-memory SQLite fixture `db_session` / `session_factory`, `@pytest.mark.asyncio`, zero real network calls to Telegram, requirement ID docstrings)
- Strictly enforce tenant isolation per `REQ-NFR-02`
- Follow modular architectural structure defined in `_docs/schema.md`
- Do not write implementation code or modify code files in `src/` or `tests/` in this task

## 15. Mini App Calendar View

### Goal

Build an interactive Calendar View and navigation tab bar in the Telegram Mini App allowing users to inspect and manage tasks for any selected date with monthly activity indicator dots, backed by an authenticated, tenant-isolated FastAPI monthly summary endpoint and comprehensive automated tests.

### Acceptance criteria

- [x] `src/schemas/task.py` defines `CalendarDaySummary` model inheriting from Pydantic `BaseModel` with fields: `date: date`, `total_tasks: int`, `completed_tasks: int`, and `status: Literal["all_done", "partial", "todo_only"]` (REQ-TMA-03).
- [x] `CalendarDaySummary.status` reflects the completion ratio: `"all_done"` if `completed_tasks == total_tasks > 0`; `"partial"` if `0 < completed_tasks < total_tasks`; `"todo_only"` if `completed_tasks == 0 < total_tasks`.
- [x] `src/schemas/__init__.py` imports and exposes `CalendarDaySummary`.
- [x] `src/services/task_service.py` defines async `get_calendar_summary(session: AsyncSession, user_id: int, year: int, month: int) -> list[CalendarDaySummary]` (REQ-TMA-03, REQ-NFR-02).
- [x] `get_calendar_summary` computes the start and end dates of the requested month using `calendar.monthrange(year, month)` (accounting for leap years in February).
- [x] `get_calendar_summary` queries tasks where `Task.user_id == user_id`, `Task.target_date >= start_date`, and `Task.target_date <= end_date`, excluding canceled tasks (`Task.status != TaskStatus.canceled`).
- [x] `get_calendar_summary` aggregates task counts per day (`total_tasks = count()`, `completed_tasks = count(status == done)`), assigns the corresponding `status` indicator, and returns summaries ordered by `date ASC`.
- [x] When no tasks exist for a user in the requested month, `get_calendar_summary` returns an empty list `[]`.
- [x] `get_calendar_summary` strictly enforces tenant isolation by querying only `Task.user_id == user_id`, ensuring tasks of other users are never returned (REQ-NFR-02).
- [x] `src/services/__init__.py` imports and exposes `get_calendar_summary`.
- [x] `src/api/routes/tasks.py` defines `GET /api/tasks/calendar-summary` endpoint accepting query parameters `year: int = Query(..., ge=1900, le=2100)` and `month: int = Query(..., ge=1, le=12)`, returning `list[CalendarDaySummary]` (REQ-TMA-03).
- [x] Endpoint requires Telegram authentication via `current_user: User = Depends(get_current_user)` (REQ-API-01).
- [x] Requests without valid Telegram `Authorization: tma <initData>` return HTTP 401 Unauthorized.
- [x] Requests with invalid query parameters (e.g. `month=0`, `month=13`, `year=1899`, `year=2101`) are rejected with HTTP 422 Unprocessable Entity.
- [x] Endpoint is registered before dynamic path `GET /api/tasks/{task_id}` to prevent FastAPI route collision.
- [x] `frontend/src/api/types.ts` defines `CalendarDaySummary` interface containing: `date: string`, `total_tasks: number`, `completed_tasks: number`, and `status: 'all_done' | 'partial' | 'todo_only'`.
- [x] `frontend/src/api/types.ts` defines navigation tab type union `type AppTab = 'today' | 'calendar' | 'analytics' | 'settings'`.
- [x] `frontend/src/api/client.ts` implements and exports `fetchCalendarSummary(year: number, month: number): Promise<CalendarDaySummary[]>` calling `GET /api/tasks/calendar-summary?year=${year}&month=${month}` with Telegram `Authorization` header (REQ-API-01, REQ-TMA-03).
- [x] `frontend/src/components/NavigationTabBar.tsx` renders a bottom navigation tab bar allowing switching between screens: "Сьогодні" (Today) and "Календар" (Calendar).
- [x] Navigation bar visually highlights the active tab with primary accent styling (`text-primary`, active background/indicator) and inactive tabs with muted styling (`text-muted`).
- [x] Includes placeholder/disabled tab items for future tabs: "Аналітика" (#16) and "Налаштування" (#17).
- [x] Tapping a tab triggers Telegram haptic feedback `impactOccurred('light')` via `window.Telegram?.WebApp?.HapticFeedback` when available.
- [x] `frontend/src/components/CalendarView.tsx` renders the calendar screen with month navigation, 7-column calendar grid, activity dots, and selected date task list (REQ-TMA-03).
- [x] Header renders the current viewed month and year formatted in Ukrainian (e.g. "Листопад 2026") with `<` (previous month) and `>` (next month) navigation buttons.
- [x] Clicking `<` or `>` transitions month view across month and year boundaries (e.g., from January to December of previous year) and triggers `fetchCalendarSummary` for the new month.
- [x] Includes a "Сьогодні" shortcut button to jump directly back to the current month and today's date.
- [x] Grid displays 7 weekday column headers starting on Monday per `_docs/design-system.md`: "Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд".
- [x] Grid correctly calculates the first day of the month offset and pads prior and next month days so calendar rows align accurately with Monday start.
- [x] Days with scheduled tasks display activity indicator dots below the day number per `_docs/design-system.md`:
  - Green dot (`bg-emerald-500` / `bg-green-500`): all tasks completed (`status === "all_done"` / 100%).
  - Amber dot (`bg-amber-500`): partially completed tasks (`status === "partial"`).
  - Gray dot (`bg-slate-400`): scheduled tasks with 0% completed (`status === "todo_only"`).
- [x] Days with 0 tasks render no activity indicator dot.
- [x] The currently selected date is highlighted with a rounded accent pill / primary background styling per `_docs/design-system.md`.
- [x] Today's date is visually distinguished with a badge or subtle border when not selected.
- [x] Clicking any calendar day selects that date, triggers Telegram haptic feedback `impactOccurred('light')`, and fetches tasks for that date via `fetchTasks(selectedDate)`.
- [x] Below the calendar grid, displays a section header with the selected date (e.g. "Завдання на 21 листопада 2026") and task count.
- [x] Renders tasks for the selected date using `TaskCard` items supporting status toggle (`onToggle`) and deletion (`onDelete`).
- [x] Toggling or deleting a task updates local state optimistically and recalculates the calendar indicator dot for that day.
- [x] When 0 tasks exist on the selected date, renders an empty state card ("На цей день завдань немає") with an icon and prompt to add tasks.
- [x] Renders a `+ Додати завдання` button that opens `TaskCreationModal` with `targetDate` pre-filled to the selected date.
- [x] Creating a task via `TaskCreationModal` appends the task to the selected date's list and updates the calendar day's indicator dot.
- [x] Displays a loading spinner or skeleton while calendar summary or selected date tasks are being fetched.
- [x] Displays an error banner with a retry button if loading calendar summary fails.
- [x] `frontend/src/App.tsx` embeds `NavigationTabBar` and conditionally renders `TodayChecklist` or `CalendarView` based on active tab state.
- [x] Running `npm run typecheck` in `frontend/` passes with exit code 0 and 0 errors.
- [x] Running `npm run build` in `frontend/` passes with exit code 0 and updates `frontend/dist/`.
- [x] `tests/integration/test_api_calendar_summary.py` contains automated integration tests using `TestClient` and in-memory SQLite fixture with valid signed `initData`.
- [x] Automated tests verify `GET /api/tasks/calendar-summary` returns daily summaries with accurate `total_tasks`, `completed_tasks`, and `status` values (`all_done`, `partial`, `todo_only`) (REQ-TMA-03).
- [x] Automated tests verify that a month with 0 tasks returns an empty list `[]`.
- [x] Automated tests verify invalid query parameters: `month=0`, `month=13`, `year=1899`, `year=2101` return HTTP 422 Unprocessable Entity.
- [x] Automated tests verify authentication: requests without `Authorization` header or with invalid signature return HTTP 401 Unauthorized (REQ-API-01).
- [x] Automated tests verify strict tenant isolation: tasks belonging to User B are never included in User A's monthly summary (REQ-NFR-02).
- [x] Automated tests verify month boundaries: tasks in adjacent months (e.g., last day of previous month or first day of next month) are excluded from the summary.
- [x] All test functions contain docstrings referencing requirement IDs (`REQ-TMA-03`, `REQ-API-01`, `REQ-API-02`, `REQ-NFR-02`).
- [x] Running `uv run pytest tests/integration/test_api_calendar_summary.py` passes with exit code 0.
- [x] Running `uv run pytest` executes the complete test suite and passes with 0 errors and 0 failures.

### Out of scope

- Mini App productivity dashboard, completion rate charts, and daily streaks (`GET /api/tasks/analytics`), moved to #16
- User settings UI in Mini App and bot for configuring timezones and reminder preferences (`PATCH /api/settings/timezone`), moved to #17
- Production multi-process startup runner, Docker Compose setup, and deployment verification (`main.py`), moved to #18
- Drag-and-drop task rescheduling between calendar dates or multi-date range selection, moved to #16

### Constraints

- Files this should stay inside:
  - Frontend: `frontend/src/api/types.ts`, `frontend/src/api/client.ts`, `frontend/src/components/CalendarView.tsx`, `frontend/src/components/NavigationTabBar.tsx`, `frontend/src/App.tsx`, `frontend/dist/**`
  - Backend: `src/schemas/task.py`, `src/schemas/__init__.py`, `src/services/task_service.py`, `src/services/__init__.py`, `src/api/routes/tasks.py`, `tests/integration/test_api_calendar_summary.py`
- Libraries to use:
  - Frontend: React 18, TypeScript, Tailwind CSS, `lucide-react`, `@telegram-apps/sdk-react`
  - Backend: FastAPI, SQLAlchemy 2.0 (`select`, `func`, `case`, `AsyncSession`), Pydantic 2, Python standard library (`calendar`, `datetime`), pytest, pytest-asyncio, `fastapi.testclient.TestClient`
- Dependencies:
  - Python dependencies are strictly defined in `pyproject.toml` — do not add new dependencies without asking per `Agents.md`.
  - Frontend dependencies are strictly defined in `frontend/package.json` — do not add new dependencies without asking per `Agents.md`.
- Guidelines:
  - Follow design system guidelines in `_docs/design-system.md` (Section 2.B Calendar View: 7 days per row starting Monday, rounded accent pill for selected date, status indicator dots: green = 100% completed, amber = partially completed, gray = scheduled 0% completed; native Telegram haptic feedback).
  - Follow testing conventions in `_docs/testing-guidelines.md` (isolated in-memory SQLite fixture, `@pytest.mark.asyncio`, zero real network calls, requirement ID docstrings).
  - Strictly enforce tenant isolation per `REQ-NFR-02` by always filtering by `user_id == current_user.telegram_id`.
  - Do not write implementation code or modify code files in `src/`, `frontend/`, or `tests/`.

## 16. Mini App Productivity Dashboard and Streaks

### Goal

Develop and integrate an interactive Productivity Analytics Dashboard and daily streak tracking system in the Telegram Mini App and FastAPI backend, featuring metric summary cards, Recharts-powered daily trend and tag distribution charts, and an authenticated, tenant-isolated analytics REST endpoint, verified by automated integration tests and a mobile-responsive UI.

### Acceptance criteria

- [x] `src/schemas/task.py` defines `DailyTrendItem(BaseModel)` with fields: `date: date`, `completed_tasks: int = Field(default=0, ge=0)`, `total_tasks: int = Field(default=0, ge=0)`, `completion_rate: float = Field(default=0.0, ge=0.0, le=100.0)`, and `model_config = ConfigDict(from_attributes=True)`.
- [x] `src/schemas/task.py` defines `TagBreakdownItem(BaseModel)` with fields: `tag: str`, `count: int = Field(default=0, ge=0)`, `completed_count: int = Field(default=0, ge=0)`, `percentage: float = Field(default=0.0, ge=0.0, le=100.0)`, and `model_config = ConfigDict(from_attributes=True)`.
- [x] `src/schemas/task.py` defines `AnalyticsResponse(BaseModel)` with fields: `streak_current: int = Field(default=0, ge=0)`, `streak_longest: int = Field(default=0, ge=0)`, `total_tasks: int = Field(default=0, ge=0)`, `completed_tasks: int = Field(default=0, ge=0)`, `completion_rate: float = Field(default=0.0, ge=0.0, le=100.0)`, `daily_trends: list[DailyTrendItem] = Field(default_factory=list)`, `tag_breakdown: list[TagBreakdownItem] = Field(default_factory=list)`, and `model_config = ConfigDict(from_attributes=True)`.
- [x] `src/schemas/__init__.py` imports and exposes `DailyTrendItem`, `TagBreakdownItem`, and `AnalyticsResponse`.
- [x] `src/services/task_service.py` defines async `get_productivity_analytics(session: AsyncSession, user_id: int, days: int = 14, reference_date: date | None = None) -> AnalyticsResponse` (REQ-TMA-04, REQ-NFR-02).
- [x] `get_productivity_analytics` determines reference `today`: uses `reference_date` if provided; otherwise resolves current date from the user's configured timezone via `get_user_local_time(user).date()` (falling back to `date.today()`).
- [x] Streak calculation logic:
  - Considers a day completed if the user has >= 1 task with `status == TaskStatus.done` on that calendar date (`target_date`).
  - Active streak evaluation:
    - If user has completed tasks on `today`, current streak includes `today` and counts backward consecutive preceding calendar days with >= 1 completed task.
    - If user has 0 completed tasks on `today`, but completed >= 1 task on `yesterday` (`today - timedelta(days=1)`), the streak remains active (grace period for today) and counts backward starting from `yesterday`.
    - If user has 0 completed tasks on both `today` and `yesterday`, `streak_current` is reset to 0.
  - Longest streak evaluation:
    - Analyzes the user's entire task completion history to compute `streak_longest` (maximum consecutive calendar days with >= 1 completed task).
  - Edge case: new users or users with 0 completed tasks return `streak_current = 0` and `streak_longest = 0`.
- [x] Daily trends logic:
  - Generates a continuous sequence of `days` calendar dates ending on `today` (from `today - timedelta(days=days - 1)` to `today` inclusive).
  - Queries non-canceled tasks (`status != TaskStatus.canceled`) for `user_id` within the date window.
  - Aggregates `total_tasks` and `completed_tasks` (`status == TaskStatus.done`) per date.
  - Calculates `completion_rate = round((completed_tasks / total_tasks) * 100.0, 1)` if `total_tasks > 0`, else `0.0`.
  - Every date in the requested range is present in `daily_trends` ordered by `date ASC`. Days with 0 tasks output `total_tasks = 0`, `completed_tasks = 0`, `completion_rate = 0.0`.
- [x] Tag breakdown logic:
  - Aggregates non-canceled tasks (`status != TaskStatus.canceled`) within the date window grouped by `tag`.
  - For tasks where `tag is None` or empty, groups them under label `"Без тегу"`.
  - Calculates for each tag: `count` (total non-canceled tasks with this tag), `completed_count` (tasks with `status == TaskStatus.done`), and `percentage = round((count / window_total_tasks) * 100.0, 1)` where `window_total_tasks` is total non-canceled tasks in the window (or `0.0` if 0).
  - Orders tag breakdown items by `count DESC`, then `tag ASC`.
- [x] Window summary metrics:
  - Computes `total_tasks` as total non-canceled tasks in the window.
  - Computes `completed_tasks` as count of tasks with `status == TaskStatus.done` in the window.
  - Computes `completion_rate = round((completed_tasks / total_tasks) * 100.0, 1)` if `total_tasks > 0`, else `0.0`.
- [x] Strictly enforces tenant isolation by filtering all queries by `Task.user_id == user_id`, guaranteeing tasks of other users are never included in streaks, trends, or tag breakdowns (REQ-NFR-02).
- [x] `src/services/__init__.py` imports and exposes `get_productivity_analytics`.
- [x] `src/api/routes/tasks.py` implements `GET /api/tasks/analytics` endpoint returning `AnalyticsResponse` (REQ-TMA-04).
- [x] Accepts optional query parameter `days: int = Query(default=14, ge=7, le=90)` specifying the time window for trends and breakdowns.
- [x] Enforces Telegram authentication via `current_user: User = Depends(get_current_user)` and database session via `session: AsyncSession = Depends(get_db_session)` (REQ-API-01).
- [x] Positioned before `GET /api/tasks/{task_id}` to avoid routing collisions in FastAPI.
- [x] Returns HTTP 200 OK with JSON matching `AnalyticsResponse` schema.
- [x] Calling endpoint without valid Telegram `initData` or with invalid HMAC-SHA256 signature returns HTTP 401 Unauthorized (REQ-API-01).
- [x] Calling endpoint with `days < 7` or `days > 90` (e.g. `days=6` or `days=91`) returns HTTP 422 Unprocessable Entity.
- [x] `frontend/src/api/types.ts` defines `DailyTrendItem` interface: `date: string; completed_tasks: number; total_tasks: number; completion_rate: number;`.
- [x] `frontend/src/api/types.ts` defines `TagBreakdownItem` interface: `tag: string; count: number; completed_count: number; percentage: number;`.
- [x] `frontend/src/api/types.ts` defines `AnalyticsResponse` interface matching backend schema: `streak_current: number; streak_longest: number; total_tasks: number; completed_tasks: number; completion_rate: number; daily_trends: DailyTrendItem[]; tag_breakdown: TagBreakdownItem[];`.
- [x] `frontend/src/api/client.ts` implements and exports `fetchAnalytics(days?: number): Promise<AnalyticsResponse>` calling `GET /api/tasks/analytics` with optional `?days=${days}` and Telegram `Authorization: tma <initData>` header (REQ-API-01, REQ-TMA-04).
- [x] `frontend/src/components/NavigationTabBar.tsx` enables "Аналітика" tab by removing `disabled: true` from the `analytics` tab configuration.
- [x] Tapping "Аналітика" tab switches active tab to `'analytics'` and triggers Telegram haptic feedback `impactOccurred('light')` when available.
- [x] `frontend/src/components/AnalyticsView.tsx` component is created and implements the full analytics dashboard view (REQ-TMA-04).
- [x] Time Window Selector:
  - Renders pill buttons to switch between ranges (e.g. `7 днів`, `14 днів`, `30 днів`), defaulting to 14 days.
  - Selecting a range fetches analytics for the chosen period and triggers Telegram haptic feedback `impactOccurred('light')`.
- [x] Daily Streak Card:
  - Prominent flame icon (`🔥`), bold number (`streak_current`), and celebratory/motivational micro-copy per `_docs/design-system.md`:
    - "Днів поспіль!", "Продовжуйте в тому ж дусі!" when streak is active with tasks completed today.
    - "Стрік тримається! Виконайте завдання сьогодні 🔥" when yesterday was completed but today is pending.
    - "Почніть свій перший стрік сьогодні!" when streak is 0.
  - Best streak badge displaying all-time record: `🏆 Рекорд: {streak_longest} днів`.
- [x] Metric Cards Grid:
  - Renders summary cards with theme-aware styling and semantic icons:
    - Total Tasks card (`Всього завдань`, `total_tasks`).
    - Completed Tasks card (`Виконано`, `completed_tasks`).
    - Completion Rate card (`Успішність`, `{completion_rate}%`) with progress indicator.
- [x] Productivity Trend Chart (`Recharts`):
  - Renders daily productivity trends using `Recharts` (`ResponsiveContainer`, `BarChart` or `AreaChart`, `XAxis`, `YAxis`, `Tooltip`, `Bar` or `Area`).
  - Colors and styling adhere to `_docs/design-system.md`:
    - Palette adapts dynamically to Telegram theme variables (`--tg-theme-button-color`, `--tg-theme-secondary-bg-color`, `--tg-theme-text-color`, `--tg-theme-hint-color`).
    - Tooltip background and borders match Telegram secondary background (`--tg-theme-secondary-bg-color`).
    - X-axis formats dates as readable short strings (e.g. `19.11`).
- [x] Tag Breakdown Section:
  - Renders distribution of tasks by category/tag with tag names (`#{tag}`), task counts, completed counts, and percentage progress bars.
  - Tasks without a tag are displayed with neutral chip styling labeled `"Без тегу"`.
- [x] Empty State & Edge Cases:
  - When user has 0 tasks across the window, renders an empty state card with an icon, encouraging copy ("Ще немає даних для аналітики"), and a prompt to add tasks.
- [x] Loading & Error States:
  - Displays a skeleton loader or spinner while analytics data is being fetched.
  - Displays an error alert banner with a `Спробувати знову` retry button if the API request fails.
- [x] `frontend/src/App.tsx` conditionally renders `AnalyticsView` when `activeTab === 'analytics'`.
- [x] Running `npm run typecheck` (or `npx tsc --noEmit`) in `frontend/` succeeds with exit code 0 and 0 errors.
- [x] Running `npm run build` in `frontend/` succeeds with exit code 0 and updates production static assets in `frontend/dist/`.
- [x] `tests/integration/test_api_analytics.py` contains automated integration tests executing against an isolated in-memory SQLite database using `TestClient` with valid signed `initData`.
- [x] Automated tests verify streak calculation logic:
  - Consecutive days ending today: user completed tasks today, yesterday, and 2 days ago -> asserts `streak_current == 3`.
  - Consecutive days ending yesterday: user completed tasks yesterday and 2 days ago, but 0 tasks today -> asserts `streak_current == 2` (grace period).
  - Broken streak: user completed tasks 2 days ago, but 0 tasks yesterday and 0 today -> asserts `streak_current == 0`.
  - Longest streak: user had a 5-day streak last week, took a 2-day gap, and now has a 2-day streak -> asserts `streak_current == 2` and `streak_longest == 5`.
  - New user with 0 completed tasks -> asserts `streak_current == 0` and `streak_longest == 0`.
- [x] Automated tests verify daily trend generation:
  - Continuous sequence: asserts `len(daily_trends) == days` and dates are sequential with no missing days.
  - Zero-task days: asserts `total_tasks == 0`, `completed_tasks == 0`, `completion_rate == 0.0`.
  - Partial & full completion days: asserts accurate `total_tasks`, `completed_tasks`, and `completion_rate`.
- [x] Automated tests verify tag breakdown:
  - Correct aggregation of non-canceled tasks by tag, task counts, completed counts, and percentages.
  - Tasks with `tag is None` grouped under `"Без тегу"`.
  - Canceled tasks excluded from breakdown.
- [x] Automated tests verify time window parameter:
  - Queries with `days=7`, `days=14`, `days=30` return expected date ranges.
  - Invalid parameters: `days=6`, `days=91`, or non-integer `days` return HTTP 422 Unprocessable Entity.
- [x] Automated tests verify tenant isolation:
  - Tasks belonging to User B are completely excluded from User A's analytics metrics, streaks, daily trends, and tag breakdowns (REQ-NFR-02).
- [x] Automated tests verify authentication:
  - Requests without `Authorization` header or with invalid signature return HTTP 401 Unauthorized (REQ-API-01).
- [x] All test functions contain docstrings referencing requirement IDs (`REQ-TMA-04`, `REQ-API-01`, `REQ-NFR-02`).
- [x] Running `uv run pytest tests/integration/test_api_analytics.py` passes with exit code 0.
- [x] Running `uv run pytest` executes the complete test suite and passes with 0 errors and 0 failures.

### Out of scope

- User settings UI in Mini App and `/settings` bot command for configuring custom timezones and reminder preferences (`PATCH /api/settings/timezone`), moved to #17
- Production multi-process startup runner (`main.py`), unified Dockerfile, Docker Compose configuration, and end-to-end deployment verification, moved to #18
- Social streak sharing to Telegram stories or external channels, moved to future backlog
- Gamification badges, achievements, experience points (XP), and leaderboards, moved to future backlog
- Exporting productivity reports to PDF, CSV, or Excel formats, moved to future backlog

### Constraints

- Files this should stay inside:
  - Frontend: `frontend/package.json`, `frontend/package-lock.json`, `frontend/src/api/types.ts`, `frontend/src/api/client.ts`, `frontend/src/components/NavigationTabBar.tsx`, `frontend/src/components/AnalyticsView.tsx`, `frontend/src/App.tsx`, `frontend/dist/**`
  - Backend: `src/schemas/task.py`, `src/schemas/__init__.py`, `src/services/task_service.py`, `src/services/__init__.py`, `src/api/routes/tasks.py`, `tests/integration/test_api_analytics.py`
- Libraries to use:
  - Frontend: React 18, TypeScript, Tailwind CSS, `lucide-react`, `@telegram-apps/sdk-react`, `recharts` (declare in `frontend/package.json`)
  - Backend: FastAPI, SQLAlchemy 2.0 (`select`, `func`, `case`, `AsyncSession`), Pydantic 2 (`BaseModel`, `Field`, `ConfigDict`), Python standard library (`datetime`, `zoneinfo`), pytest, pytest-asyncio, `fastapi.testclient.TestClient`
- Dependencies:
  - Python dependencies are strictly defined in `pyproject.toml` — do not add new Python dependencies without asking per `Agents.md`.
  - Frontend dependencies are defined in `frontend/package.json` (`recharts` is required for analytics charts per `_docs/plan.md`).
- Guidelines:
  - Follow design system guidelines in `_docs/design-system.md` (Section 2.C Dashboard & Analytics: theme-aware palette, Recharts tooltips matching `--tg-theme-secondary-bg-color`, daily streak card featuring prominent flame icon `🔥`, bold number, and celebratory micro-copy; native Telegram haptic feedback).
  - Follow testing conventions in `_docs/testing-guidelines.md` (isolated in-memory SQLite fixture, `@pytest.mark.asyncio`, zero real network calls, requirement ID docstrings).
  - Strictly enforce tenant isolation per `REQ-NFR-02` by always filtering by `user_id == current_user.telegram_id`.
  - Do not write implementation code or modify code files in `src/`, `frontend/`, or `tests/`.

## 17. User Settings in Mini App and Bot

### Goal

Implement comprehensive user settings interfaces in both the Telegram bot and Telegram Mini App allowing users to view and update their individual IANA timezone preference, featuring a validated `PATCH /api/settings/timezone` REST API endpoint (with `/api/me/timezone` alias), a Telegram bot `/settings` command handler with interactive quick-selection inline keyboard, and an interactive Settings tab in the Mini App with live local time calculation, search/dropdown selector, and haptic feedback, fully verified by automated integration tests and a production frontend build.

### Acceptance criteria

- [x] `src/schemas/user.py` defines `TimezoneUpdate(BaseModel)` with field `timezone: str`.
- [x] `TimezoneUpdate` validates that `timezone` is a valid IANA timezone string using `validate_timezone` (or `_validate_timezone` calling `zoneinfo.ZoneInfo(tz)`), raising `ValueError` for invalid timezone identifiers.
- [x] `src/schemas/user.py` exports `TimezoneUpdate` alongside existing schemas (`UserBase`, `UserCreate`, `UserUpdate`, `UserRead`).
- [x] `src/schemas/__init__.py` imports and exposes `TimezoneUpdate`.
- [x] `src/api/routes/settings.py` creates `router = APIRouter(prefix="/api/settings", tags=["settings"])` (or `settings_router`).
- [x] `PATCH /api/settings/timezone` endpoint:
  - Accepts `payload: TimezoneUpdate` in request body.
  - Requires Telegram initData authentication via `current_user: User = Depends(get_current_user)` (REQ-API-01).
  - Injects database session via `session: AsyncSession = Depends(get_session)`.
  - Invokes `update_user_timezone(session, current_user.telegram_id, payload.timezone)` to persist change in database (REQ-USR-02).
  - Returns updated `UserRead` object with HTTP 200 OK.
- [x] `PATCH /api/me/timezone` endpoint is registered as an alias or route returning updated `UserRead` with HTTP 200 OK.
- [x] Passing an invalid timezone string (e.g. `"Mars/Olympus"`, empty string) is rejected with HTTP 422 Unprocessable Entity, leaving existing user timezone unchanged in database (REQ-USR-02).
- [x] Requests without `Authorization` header or with invalid Telegram HMAC-SHA256 signature return HTTP 401 Unauthorized (REQ-API-01).
- [x] Tenant isolation is enforced: endpoint operates strictly on `current_user.telegram_id` and cannot modify any other user's settings (REQ-NFR-02).
- [x] `src/api/routes/__init__.py` imports and exposes `settings_router`.
- [x] `src/api/app.py` registers `settings_router` in `create_app` via `app.include_router(settings_router)`.
- [x] `src/bot/keyboards/settings.py` defines `TimezoneCallback(CallbackData, prefix="tz")` with field `timezone: str`.
- [x] `src/bot/keyboards/settings.py` defines `get_settings_keyboard(current_tz: str, webapp_url: str | None = None) -> InlineKeyboardMarkup`:
  - Arranges quick timezone selection buttons with a maximum of 2 buttons per row per `_docs/design-system.md`.
  - Includes quick timezone presets:
    - `🇺🇦 Київ` (`Europe/Kyiv`)
    - `🇵🇱 Варшава` (`Europe/Warsaw`)
    - `🇬🇧 Лондон` (`Europe/London`)
    - `🇺🇸 Нью-Йорк` (`America/New_York`)
    - `🇯🇵 Токіо` (`Asia/Tokyo`)
  - Displays a visual checkmark (`✓` or `✅`) on the currently active timezone button (e.g. `🇺🇦 Київ ✓`).
  - Includes a button to launch the Mini App Settings:
    - When `webapp_url` is provided, creates `InlineKeyboardButton(text="⚙️ Відкрити в Mini App", web_app=WebAppInfo(url=webapp_url))`.
    - When `webapp_url` is None/empty, creates fallback `InlineKeyboardButton(text="⚙️ Відкрити в Mini App", callback_data="open_settings_app")`.
- [x] `src/bot/keyboards/__init__.py` imports and exposes `TimezoneCallback` and `get_settings_keyboard`.
- [x] `src/bot/handlers/settings.py` creates `router = Router(name="settings")` (or `settings_router`).
- [x] Command handler `@router.message(Command("settings"))`:
  - Retrieves or registers user via `get_or_create_user(session, telegram_id=message.from_user.id)`.
  - Calculates current user local time via `get_user_local_time(user)`.
  - Replies with HTML-formatted message adhering to `_docs/design-system.md`:
    - Header: `⚙️ <b>Налаштування</b>`
    - Current timezone: `🌍 Часовий пояс: <code>{user.timezone}</code>`
    - Current local time: `🕒 Поточний локальний час: <code>{local_time.strftime('%H:%M, %d.%m.%Y')}</code>`
    - Instructional prompt explaining that quick timezones can be picked below or all timezones configured in Mini App.
  - Attaches `get_settings_keyboard(current_tz=user.timezone, webapp_url=webapp_url)`.
  - Safely returns `None` if `message.from_user` is None.
- [x] Callback query handler handling `TimezoneCallback.filter()`:
  - Verifies callback caller: handles callback for `callback_query.from_user.id`.
  - If selected `callback_data.timezone == user.timezone`, answers callback with notification `await callback_query.answer("Цей часовий пояс уже встановлено.")` without redundant database write.
  - If selected `callback_data.timezone != user.timezone`, updates timezone via `update_user_timezone(session, callback_query.from_user.id, callback_data.timezone)`.
  - Calculates new local time via `get_user_local_time(updated_user)`.
  - Edits original message text confirming change (`✅ Часовий пояс оновлено!`) with new timezone and updated local time.
  - Edits message reply markup with updated keyboard reflecting the new checkmark via `get_settings_keyboard(current_tz=updated_user.timezone, webapp_url=webapp_url)`.
  - Acknowledges callback with `await callback_query.answer("Часовий пояс змінено!")`.
- [x] `src/bot/handlers/__init__.py` imports and exposes `settings_router`.
- [x] `src/bot/dispatcher.py` updates `create_dispatcher` to include `settings_router` in the dispatcher.
- [x] `frontend/src/api/types.ts` defines `TimezoneOption` interface with fields `label: string`, `value: string`, and optional `region?: string`.
- [x] `frontend/src/api/client.ts` defines and exports `updateTimezone(timezone: string): Promise<UserProfile>`:
  - Dispatches `PATCH /api/settings/timezone` with body `JSON.stringify({ timezone })`.
  - Uses `apiRequest<UserProfile>` ensuring `Authorization: tma <raw_init_data>` header is attached.
  - Returns updated `UserProfile` on success or throws descriptive Error on failure.
- [x] `frontend/src/components/NavigationTabBar.tsx` enables the "Налаштування" tab:
  - Removes `disabled: true` from the `settings` item in `TABS` array.
  - Clicking "Налаштування" tab triggers `impactOccurred('light')` and invokes `onTabChange('settings')`.
- [x] `frontend/src/components/SettingsView.tsx` creates and exports `SettingsView` component taking props `{ user: UserProfile, onUserUpdated: (updated: UserProfile) => void }`.
- [x] `SettingsView` displays user profile details card:
  - User Telegram ID (`ID: {user.telegram_id}`).
  - Account created date formatted cleanly.
  - Current configured timezone and live/formatted local time clock.
- [x] `SettingsView` provides timezone selection interface:
  - Search input allowing real-time filtering of timezones by city or region name.
  - Curated list / dropdown of major global timezones covering Europe, Americas, Asia, and Pacific (e.g. `Europe/Kyiv`, `Europe/Warsaw`, `Europe/London`, `Europe/Berlin`, `America/New_York`, `America/Los_Angeles`, `Asia/Tokyo`, `Asia/Dubai`, etc.).
  - Visual indicator (checkmark / highlight) on the currently selected timezone.
- [x] `SettingsView` provides save action and user feedback:
  - "Зберегти" button to submit selected timezone via `updateTimezone`.
  - Loading state on button while save request is in flight.
  - Success feedback: invokes Telegram haptic feedback `notificationOccurred('success')`, displays confirmation toast/badge (`✅ Налаштування збережено`), and calls `onUserUpdated` to update global user state in `App.tsx`.
  - Error feedback: on failure, invokes `notificationOccurred('error')` and displays an error alert banner with retry capability.
  - Adheres to `_docs/design-system.md` styling with native Telegram CSS theme variables and dark mode compatibility.
- [x] `frontend/src/App.tsx` conditionally renders `<SettingsView user={user} onUserUpdated={(updated) => setUser(updated)} />` when `activeTab === 'settings'`.
- [x] Running `npm run typecheck` in `frontend/` succeeds with exit code 0 and 0 TypeScript errors.
- [x] Running `npm run build` in `frontend/` succeeds with exit code 0 and outputs production assets in `frontend/dist/`.
- [x] `tests/integration/test_api_settings.py` tests REST API endpoints against in-memory SQLite database:
  - Successful timezone update: authenticated `PATCH /api/settings/timezone` with valid timezone updates database and returns HTTP 200 with updated `UserRead` (REQ-USR-02).
  - Validation rejection: `PATCH /api/settings/timezone` with invalid timezone (e.g., `"Invalid/Timezone"`) returns HTTP 422 Unprocessable Entity and keeps original timezone in database (REQ-USR-02).
  - Authentication check: requests without `Authorization` or with forged HMAC return HTTP 401 Unauthorized (REQ-API-01).
  - Tenant isolation: User A cannot modify User B's timezone settings (REQ-NFR-02).
  - Alias route: `PATCH /api/me/timezone` successfully updates timezone and returns HTTP 200.
- [x] `tests/integration/test_bot_settings.py` tests bot handlers with mocked Telegram Bot:
  - `/settings` command returns formatted message with current timezone, local time, and inline keyboard containing quick timezone buttons and WebApp launcher (REQ-USR-02).
  - Timezone selection callback updates user timezone in database, updates message text to show new timezone and local time, updates inline keyboard checkmark, and answers callback query (REQ-USR-02).
  - Selecting already active timezone performs no database write and answers callback query with already-set notice.
  - Unregistered user calling `/settings` is registered automatically with default `Europe/Kyiv`.
- [x] All test functions contain docstrings referencing requirement IDs (`REQ-USR-02`, `REQ-API-01`, `REQ-NFR-02`).
- [x] Running `uv run pytest tests/integration/test_api_settings.py` passes with exit code 0.
- [x] Running `uv run pytest tests/integration/test_bot_settings.py` passes with exit code 0.
- [x] Full test suite `uv run pytest` passes with 0 errors and 0 failures.

### Out of scope

- End-to-end multi-process startup runner (`main.py`), unified Dockerfile, Docker Compose configuration, and deployment verification, moved to #18
- User-customizable check-in hours (custom morning push / midnight review times) and configurable deadline reminder intervals in database and scheduler, moved to #19
- Manual dark/light theme toggle in Mini App (theme is automatically synchronized with Telegram client theme per `_docs/design-system.md`), moved to future backlog
- Multi-language localization settings (UI is standardized in Ukrainian per system requirements), moved to future backlog

### Constraints

- Files this should stay inside:
  - Backend:
    - `src/schemas/user.py`
    - `src/schemas/__init__.py`
    - `src/api/routes/settings.py`
    - `src/api/routes/__init__.py`
    - `src/api/app.py`
    - `src/bot/keyboards/settings.py`
    - `src/bot/keyboards/__init__.py`
    - `src/bot/handlers/settings.py`
    - `src/bot/handlers/__init__.py`
    - `src/bot/dispatcher.py`
    - `tests/integration/test_api_settings.py`
    - `tests/integration/test_bot_settings.py`
  - Frontend:
    - `frontend/src/api/types.ts`
    - `frontend/src/api/client.ts`
    - `frontend/src/components/NavigationTabBar.tsx`
    - `frontend/src/components/SettingsView.tsx`
    - `frontend/src/App.tsx`
    - `frontend/dist/**`
- Libraries to use:
  - Backend: FastAPI, aiogram 3 (`Router`, `Command`, `CallbackData`, `InlineKeyboardMarkup`, `InlineKeyboardButton`, `WebAppInfo`, `Message`, `CallbackQuery`), SQLAlchemy 2.0 (`AsyncSession`, `select`), Pydantic 2 (`BaseModel`, `field_validator`, `ConfigDict`), Python standard library (`datetime`, `zoneinfo`), pytest, pytest-asyncio, `fastapi.testclient.TestClient`, `unittest.mock` (`AsyncMock`, `MagicMock`)
  - Frontend: React 18, TypeScript, Tailwind CSS, `lucide-react`, `@telegram-apps/sdk-react` / window.Telegram.WebApp
- Dependencies:
  - Python dependencies are strictly defined in `pyproject.toml` — do not add new dependencies without explicit permission per `Agents.md`.
  - Frontend dependencies are defined in `frontend/package.json` — use existing packages (`lucide-react`, Tailwind CSS, etc.).
- Guidelines:
  - Follow Telegram bot formatting and UI guidelines in `_docs/design-system.md`: clean semantic emojis (`⚙️`, `🌍`, `🕒`, `✅`), HTML parse mode, inline keyboards max 2 buttons per row, positive actions first.
  - Follow Mini App UI standards in `_docs/design-system.md`: native Telegram theme variables (`bg-background`, `bg-secondary`, `text-foreground`, `text-muted`, `bg-primary`), mobile safe-area insets, haptic feedback (`impactOccurred('light')` on tab change, `notificationOccurred('success')` on save).
  - Follow testing conventions in `_docs/testing-guidelines.md`: isolated in-memory SQLite fixture `db_session`, `@pytest.mark.asyncio`, zero real network calls to Telegram API, requirement ID docstrings (`REQ-USR-02`, `REQ-API-01`, `REQ-NFR-02`).
  - Strictly enforce tenant isolation per `REQ-NFR-02` by always scoping operations to `current_user.telegram_id`.
  - Do not write implementation code or modify code files in `src/`, `frontend/`, or `tests/`.

## 18. End-to-End Integration, Packaging, and Deployment Verification

### Goal

Connect all backend and frontend components into a production-ready, unified runnable application (`main.py`) that concurrently orchestrates the FastAPI server (serving static Mini App assets), the aiogram Telegram bot polling, and the APScheduler background service with robust lifecycle management and graceful shutdown, packaged via a multi-stage `Dockerfile` and `docker-compose.yml`, accompanied by complete deployment documentation (`README.md`), updated environment configuration (`.env.example`), and 100% automated integration test coverage.

### Acceptance criteria

- [x] `main.py` serves as the single unified entry point for running the complete application stack (FastAPI server, aiogram bot polling, and APScheduler background service).
- [x] `main.py` loads application configuration via `get_settings()` from `src.core.config`.
- [x] `main.py` defines startup initialization functions (e.g. `setup_application()` or `init_app_components()`):
  - Asynchronously initializes database tables via `init_db(engine)` from `src.core.database` (REQ-NFR-01, REQ-NFR-03).
  - Initializes the bot instance via `create_bot(token=settings.BOT_TOKEN)` from `src.bot.dispatcher`.
  - Initializes the dispatcher via `create_dispatcher(sessionmaker=async_session_maker, webapp_url=settings.WEBAPP_URL)` from `src.bot.dispatcher`.
  - Initializes background scheduler via `create_scheduler()`, registers periodic jobs via `setup_scheduler(scheduler, bot, async_session_maker, settings.WEBAPP_URL)`, and starts it via `start_scheduler(scheduler)` from `src.scheduler.manager` (REQ-SCH-01, REQ-SCH-02, REQ-SCH-03).
  - Initializes FastAPI application via `create_app(settings=settings, sessionmaker=async_session_maker, frontend_dist=DEFAULT_FRONTEND_DIST)` from `src.api.app` (REQ-API-01, REQ-API-02).
- [x] `main.py` configures and instantiates `uvicorn.Server(config=uvicorn.Config(app=app, host=settings.HOST, port=settings.PORT, log_level="info" if not settings.DEBUG else "debug"))`.
- [x] `main.py` runs the FastAPI server (`server.serve()`) and Telegram Bot polling (`dp.start_polling(bot)`) concurrently within the same `asyncio` event loop using `asyncio.gather` or structured tasks (`asyncio.create_task` / `asyncio.TaskGroup`).
- [x] `main.py` implements graceful shutdown lifecycle:
  - Catches `KeyboardInterrupt`, `asyncio.CancelledError`, and OS signals (`SIGINT`, `SIGTERM` with cross-platform compatibility checking `hasattr(signal, "SIGTERM")` and `sys.platform != "win32"` to safely operate on Windows).
  - Stops the background scheduler cleanly via `stop_scheduler(scheduler, wait=False)` ensuring no orphaned background jobs continue running.
  - Stops bot polling via `dp.stop_polling()` and closes the bot HTTP session via `await bot.session.close()`.
  - Signals Uvicorn server to exit cleanly via setting `server.should_exit = True`.
  - Closes and disposes the SQLAlchemy async database engine cleanly via `await engine.dispose()`.
  - Exits with returncode 0 on normal termination.
- [x] When `WEBAPP_URL` is omitted or None in settings, `main.py` logs an informational notice and starts up successfully with bot polling and scheduler functioning normally, falling back to local Mini App serving at `http://{HOST}:{PORT}`.
- [x] If database initialization or configuration loading fails at startup, `main.py` logs a descriptive error and exits cleanly without hanging background threads.
- [x] Multi-stage `Dockerfile` is created in the repository root:
  - Stage 1 (`frontend-builder`): Uses Node.js LTS base image (e.g. `node:20-alpine`), copies `frontend/package.json` and `frontend/package-lock.json`, installs dependencies via `npm ci` (or `npm install`), copies source, and builds frontend via `npm run build` to `/app/frontend/dist`.
  - Stage 2 (`python-runtime`): Uses Python 3.11+ slim base image, sets `PYTHONUNBUFFERED=1` and `UV_SYSTEM_PYTHON=1`, installs `uv`, installs dependencies via `uv sync --frozen --no-dev`, copies backend code and built frontend dist, exposes port 8000, and runs `main.py` via `CMD ["uv", "run", "python", "main.py"]`.
- [x] `docker-compose.yml` is created in the repository root:
  - Defines service `app` (or `tasks-bot`) building from `Dockerfile`.
  - Maps port `${PORT:-8000}:8000`.
  - Configures volume mount for persistent SQLite database storage (e.g. `./data:/app/data` with `DATABASE_URL=sqlite+aiosqlite:////app/data/tasks.db` or persistent volume).
  - Loads environment variables from `.env` with fallback defaults.
  - Sets restart policy `restart: unless-stopped`.
- [x] `.dockerignore` is created in the repository root excluding `node_modules`, `frontend/node_modules`, `.venv`, `.git`, `.pytest_cache`, `__pycache__`, `*.pyc`, `*.pyo`, `tests/`, `_docs/`, `.env`, `tasks.db`, and `tasks.db-*`.
- [x] `.env.example` is updated in the repository root documenting all configuration variables (`BOT_TOKEN`, `GEMINI_API_KEY`, `DATABASE_URL`, `WEBAPP_URL`, `HOST`, `PORT`, `DEBUG`).
- [x] `README.md` is created in the repository root providing comprehensive documentation:
  - Project architecture overview and tech stack (`aiogram 3`, `FastAPI`, `APScheduler`, `SQLAlchemy 2.0`, `React 18`, `uv`).
  - Prerequisites (Python 3.11+, uv, Node.js 18+, Docker).
  - Local setup and running instructions (both manual with `uv` + `npm` and Docker Compose).
  - BotFather and Telegram Mini App setup guide (`BOT_TOKEN`, `WEBAPP_URL`).
  - Complete environment variables reference table.
  - Testing and verification guide (`uv run pytest`, `npm run typecheck`, `npm run build`).
- [x] `tests/integration/test_main_runner.py` is created and contains automated tests:
  - Tests application factory wiring: verifies `main.py` functions can initialize and configure bot, dispatcher, scheduler, database, and FastAPI app with mock settings (REQ-NFR-03).
  - Tests concurrent execution: verifies server and bot polling tasks run concurrently without blocking each other.
  - Tests graceful shutdown lifecycle: verifies scheduler is stopped, bot polling stopped, bot session closed, uvicorn signaled, and database engine disposed cleanly (REQ-NFR-03).
  - Tests missing `BOT_TOKEN` validation: verifies error exit when required bot token is missing.
- [x] All tests in `tests/integration/test_main_runner.py` make 0 real network calls to Telegram Bot API or Google Gemini API per `_docs/testing-guidelines.md`.
- [x] All test functions contain docstrings referencing requirement IDs (`REQ-NFR-03`, `REQ-NFR-01`).
- [x] Running `uv run pytest tests/integration/test_main_runner.py` passes with exit code 0.
- [x] Complete test suite `uv run pytest` passes 100% with 0 errors and 0 failures.

### Out of scope

- User-customizable check-in hours (custom morning push / evening review times) and configurable reminder intervals in database and scheduler, moved to #19
- Cloud hosting CI/CD deployment pipelines (GitHub Actions deployment workflows to AWS/GCP/DigitalOcean), moved to future backlog
- Kubernetes Helm charts, Kubernetes manifests, and multi-pod high-availability clustering, moved to future backlog
- Automated SSL certificate provisioning and reverse proxy / ingress controller (e.g. Traefik, Caddy, Nginx SSL termination), moved to future backlog
- Webhook-based Telegram update delivery mode (application runs in long-polling mode for simplified deployment), moved to future backlog

### Constraints

- Files this should stay inside:
  - `main.py`
  - `Dockerfile`
  - `docker-compose.yml`
  - `.dockerignore`
  - `.env.example`
  - `README.md`
  - `tests/integration/test_main_runner.py`
- Libraries to use:
  - Python: `uvicorn`, `aiogram 3`, `fastapi`, `apscheduler`, `sqlalchemy 2.0`, `aiosqlite`, `pydantic-settings`, `pytest`, `pytest-asyncio`, `unittest.mock` (`AsyncMock`, `MagicMock`, `patch`)
  - Node / Frontend: `npm`, `vite`
  - DevOps: Docker, Docker Compose
- Dependencies:
  - Python dependencies are strictly defined in `pyproject.toml` — do not add new dependencies without explicit permission per `Agents.md`.
  - `uvicorn`, `fastapi`, `aiogram`, `apscheduler`, `sqlalchemy`, and `aiosqlite` are already installed and listed in `pyproject.toml`.
- Guidelines:
  - Follow testing conventions in `_docs/testing-guidelines.md`: isolated in-memory SQLite fixture, `@pytest.mark.asyncio`, zero real network calls to Telegram or Gemini API, requirement ID docstrings (`REQ-NFR-03`, `REQ-NFR-01`).
  - Cross-platform signal handling: do not call `loop.add_signal_handler` on Windows (ProactorEventLoop) without platform guards (`if sys.platform != "win32"`).
  - Graceful shutdown handlers must safely handle task cancellation without unhandled exceptions or dangling engine connections (REQ-NFR-03).
  - Follow modular architecture defined in `_docs/schema.md`.
  - Do not write implementation code or modify code files in `src/`, `frontend/`, or `tests/`.
