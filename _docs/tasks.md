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
Goal: Configure asynchronous SQLite with WAL mode and define declarative SQLAlchemy models.
Description: Implement an asynchronous SQLAlchemy 2.0 database engine using `aiosqlite` with connection event listeners enforcing SQLite `PRAGMA journal_mode=WAL`, `busy_timeout=5000`, and `foreign_keys=ON`. Define declarative models for `User` and `Task` with fields for task status, priority, tags, target date, deadlines, recurrence rules, and user timezones. Create a helper utility or database initialization script to create tables asynchronously, accompanied by a test verifying table creation.

## 3. User Service and Timezone Management
Goal: Implement business logic to create, retrieve, and update user preferences and timezones.
Description: Create a user service layer providing async functions to register new Telegram users and retrieve existing user profiles with default settings. Add functions to update user timezones (such as `Europe/Berlin` or `Europe/Kyiv`) and custom notification preferences. Write isolated unit tests using an in-memory SQLite database to confirm user creation and timezone modification.

## 4. Gemini AI Voice and Text Parser Service
Goal: Build a service that extracts structured task definitions from voice audio or text using Gemini.
Description: Integrate Google Gemini 2.5 Flash via the `google-genai` SDK using Pydantic structured output models to extract task title, target date, deadline, priority, and tag. Support direct ingestion of Telegram `.ogg` Opus audio bytes and plain text in a single unified parsing method. Write automated unit tests with mock responses or sample inputs to verify that parsed results conform to the target Pydantic schema.

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
