# Project Backlog: Telegram Task Tracker Bot & Mini App

## 1. Project Setup and Test Harness
Goal: Set up the project foundation, dependency management, and a passing automated test.
Description: Initialize the project structure using `uv` with dependencies specified in `pyproject.toml` (including `aiogram`, `fastapi`, `sqlalchemy`, `aiosqlite`, `pytest`, `pytest-asyncio`, and `pydantic`). Create a minimal smoke test using `pytest` that runs via `uv run pytest` and passes. Ensure the directory structure is prepared for modular application components per `_docs/schema.md` without adding business logic yet. Refer to acceptance criteria in `_docs/requirements.md` (REQ-NFR-01).

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
