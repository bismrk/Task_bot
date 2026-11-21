# 🚀 Telegram Task Tracker Bot & Mini App

A modern, full-stack personal task tracker combining a **Telegram Bot** (powered by `aiogram 3` and Google Gemini AI) and an interactive **Telegram Mini App** (built with React 18, TypeScript, and Tailwind CSS), orchestrated by a high-performance **FastAPI** backend and **APScheduler** background service.

---

## 📑 Table of Contents

- [Overview & Architecture](#overview--architecture)
- [Tech Stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [Local Setup & Running](#local-setup--running)
  - [1. Backend Setup](#1-backend-setup)
  - [2. Frontend Setup & Build](#2-frontend-setup--build)
  - [3. Running the Unified Stack](#3-running-the-unified-stack)
- [Docker & Containerized Deployment](#docker--containerized-deployment)
- [Telegram Bot & Mini App Setup Guide](#telegram-bot--mini-app-setup-guide)
- [Environment Variables Reference](#environment-variables-reference)
- [Testing & Quality Assurance](#testing--quality-assurance)

---

## 🌟 Overview & Architecture

The application provides an integrated task management experience directly within Telegram:
- **Intelligent Task Ingestion**: Add single or multiple tasks using text or voice messages, automatically parsed by Google Gemini AI with priority, tags, target dates, and deadlines.
- **Proactive Routines**: Timezone-aware morning plan pushes (08:00) and midnight rollover interactive dialogues (00:00).
- **Deadline Reminders**: Automated notifications at -1 hour and -10 minutes before task deadlines with quick action buttons (`[✅ Done]` and `[⏰ +15m]`).
- **Telegram Mini App**:
  - **Today Checklist**: Fast task completion, creation, and filtering.
  - **Calendar View**: Monthly task density dots and day selection.
  - **Productivity Analytics**: Daily streaks (`🔥`), completion rates, trend charts, and category breakdowns.
  - **Settings**: Timezone configuration with live local time calculation.

### System Architecture Diagram

```mermaid
flowchart TD
    User([Telegram User])
    TGClient[Telegram Mobile / Desktop App]

    subgraph Telegram_Platform [Telegram Platform]
        BotAPI[Telegram Bot API]
        TMAWeb[Telegram WebApp Container]
    end

    subgraph Task_Tracker_App [Task Tracker Container (main.py)]
        subgraph FastAPI_Backend [FastAPI Server (Uvicorn)]
            API[REST Endpoints /api/*]
            SPA[Static Files / SPA Fallback]
        end

        subgraph Bot_Dispatcher [aiogram 3 Dispatcher]
            Handlers[Command & Callback Handlers]
            Middleware[DbSessionMiddleware]
        end

        subgraph Background_Service [APScheduler]
            TZJob[Timezone Checks (00:00 & 08:00)]
            DLJob[Deadline Proximity Checks (-1h, -10m)]
        end

        DB[(SQLite aiosqlite)]
    end

    Gemini[Google Gemini AI API]

    User --> TGClient
    TGClient -->|Commands & Voice/Text| BotAPI
    TGClient -->|Mini App Webview| TMAWeb
    TMAWeb -->|Static Assets & API Requests| FastAPI_Backend

    BotAPI <-->|Long Polling| Bot_Dispatcher
    Bot_Dispatcher -->|Session Context| Middleware
    Middleware --> DB
    Handlers -->|NLP Task Extraction| Gemini
    Handlers --> DB

    API --> DB
    Background_Service -->|Queries Tasks & Users| DB
    Background_Service -->|Proactive Alerts| BotAPI
```

---

## 🛠 Tech Stack

- **Backend**:
  - **Python 3.11+**
  - **aiogram 3**: Asynchronous Telegram Bot framework
  - **FastAPI**: High-performance REST API and static asset hosting
  - **APScheduler**: Asynchronous background cron and interval job manager
  - **SQLAlchemy 2.0 & aiosqlite**: Asynchronous SQLite ORM with WAL mode and foreign key enforcement
  - **Pydantic 2 & pydantic-settings**: Data validation and typed settings
  - **Google GenAI SDK**: NLP parsing for task extraction
- **Frontend (Mini App)**:
  - **React 18 & TypeScript**
  - **Vite**: Ultra-fast build tool
  - **Tailwind CSS**: Modern utility-first styling
  - **Recharts**: Responsive productivity analytics charts
  - **@telegram-apps/sdk-react**: Native Telegram WebApp integration and haptic feedback
- **DevOps & Tooling**:
  - **uv**: Fast Python package and environment manager
  - **Docker & Docker Compose**: Multi-stage build and persistent volume containerization

---

## 📋 Prerequisites

- **Python 3.11+**
- **uv** (recommended: `curl -LsSf https://astral.sh/uv/install.sh | sh` or via `pip install uv`)
- **Node.js 20+** (or 18 LTS) & **npm**
- **Docker & Docker Compose** (for containerized deployment)
- A **Telegram Bot Token** from [@BotFather](https://t.me/BotFather)

---

## 🚀 Local Setup & Running

### 1. Backend Setup

Clone the repository and install dependencies using `uv`:

```bash
git clone https://github.com/your-username/Tasks_bot.git
cd Tasks_bot

# Install all Python dependencies
uv sync
```

Create your `.env` configuration file from the template:

```bash
cp .env.example .env
```

Edit `.env` and fill in your `BOT_TOKEN` and optionally `GEMINI_API_KEY`:

```ini
BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
GEMINI_API_KEY=your_gemini_api_key
DATABASE_URL=sqlite+aiosqlite:///tasks.db
WEBAPP_URL=https://your-mini-app-domain.com
HOST=0.0.0.0
PORT=8000
DEBUG=True
```

### 2. Frontend Setup & Build

Navigate to the `frontend/` directory, install packages, and build the static assets:

```bash
cd frontend
npm ci
npm run build
cd ..
```

This compiles production static files into `frontend/dist/`, which FastAPI serves at the root path `/`.

### 3. Running the Unified Stack

Start the entire application stack (FastAPI server, aiogram bot polling, and APScheduler) with a single command:

```bash
uv run python main.py
```

The application will initialize database tables, start the scheduler, launch the HTTP server on `http://0.0.0.0:8000`, and start polling Telegram for updates.

---

## 🐳 Docker & Containerized Deployment

Deploy with a single command using Docker Compose:

### 1. Prepare Environment

Ensure your `.env` file contains your production credentials:

```bash
cp .env.example .env
# Edit .env with your BOT_TOKEN, GEMINI_API_KEY, and public WEBAPP_URL
```

### 2. Build and Start Container

```bash
docker compose up --build -d
```

### 3. Monitor and Manage

```bash
# View live application logs
docker compose logs -f

# Check container status
docker compose ps

# Stop container
docker compose down
```

> **Data Persistence:** Database files are automatically persisted in `./data` on the host machine via Docker volume mapping (`./data:/app/data`), preserving all user tasks and settings across container rebuilds.

---

## 🤖 Telegram Bot & Mini App Setup Guide

### 1. Create Bot via @BotFather

1. Open Telegram and search for [@BotFather](https://t.me/BotFather).
2. Send `/newbot` and follow the prompts to choose a name and username (must end in `bot`).
3. Copy the HTTP API token provided and set it as `BOT_TOKEN` in your `.env`.

### 2. Configure Bot Commands

Send `/setcommands` to [@BotFather] and enter:

```text
start - Запустити бота та головне меню
today - Список завдань на сьогодні
plan - Ранкове планування
settings - Налаштування часового поясу
```

### 3. Configure Mini App (Menu Button)

To enable the WebApp menu button inside Telegram:
1. In [@BotFather](https://t.me/BotFather), send `/setmenubutton`.
2. Select your bot.
3. Provide your public HTTPS URL (e.g. `https://your-domain.com` or Cloudflare Tunnel / ngrok URL).
4. Set the button title to `🚀 Відкрити план`.
5. Set `WEBAPP_URL` in your `.env` to match this URL.

---

## ⚙️ Environment Variables Reference

| Variable | Description | Required | Default |
| :--- | :--- | :---: | :--- |
| `BOT_TOKEN` | Telegram Bot token obtained from `@BotFather` | **Yes** | `""` |
| `GEMINI_API_KEY` | Google Gemini API key for natural language task parsing | Optional | `""` |
| `DATABASE_URL` | SQLAlchemy SQLite database connection string | No | `sqlite+aiosqlite:///tasks.db` |
| `WEBAPP_URL` | Public HTTPS URL for Telegram Mini App | Optional | `None` (falls back to local URL) |
| `HOST` | Server network host binding address | No | `0.0.0.0` |
| `PORT` | Server HTTP port | No | `8000` |
| `DEBUG` | Enable debug mode and verbose log output | No | `False` |

---

## 🧪 Testing & Quality Assurance

### Run Backend Pytest Suite

Execute the complete test suite against an isolated in-memory SQLite database (zero external network requests):

```bash
uv run pytest
```

Run a specific test suite or test file:

```bash
# Integration test for main runner lifecycle and wiring
uv run pytest tests/integration/test_main_runner.py

# Run with verbose output
uv run pytest -v
```

### Run Frontend Typecheck & Build Verification

Ensure TypeScript types and Vite production builds compile cleanly:

```bash
cd frontend
npm run typecheck
npm run build
cd ..
```
