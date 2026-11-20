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
