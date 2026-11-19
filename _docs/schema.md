Tasks_bot/
├── _docs/
│   ├── plan.md
│   ├── process.md               # Правила організації роботи та GitHub Issues
│   ├── requirements.md          # Специфікація вимог (SRS) та Acceptance Criteria
│   ├── tasks.md                 # Беклог завдань
│   ├── testing-guidelines.md    # Інструкції та правила тестування
│   ├── design-system.md         # Дизайн-система та правила Telegram Mini App
│   └── schema.md                # Архітектурна структура проєкту
│
├── src/
│   ├── core/                    # Загальна конфігурація та ініціалізація
│   │   ├── config.py            # Pydantic Settings (.env, токени)
│   │   ├── database.py          # SQLAlchemy async engine, sessionmaker, WAL pragma
│   │   └── ai_client.py         # Клієнт Gemini 2.5 Flash
│   │
│   ├── models/                  # База даних (SQLAlchemy Declarative Models)
│   │   ├── user.py              # Користувач, таймзона, налаштування
│   │   ├── task.py              # Задачі (статус, пріоритет, теги, дедлайн, повторюваність)
│   │   └── base.py
│   │
│   ├── schemas/                 # Pydantic моделі
│   │   ├── task.py              # Валідація задач, Gemini Structured Output
│   │   └── user.py
│   │
│   ├── services/                # Бізнес-логіка (спільна для Бота, API та Планувальника)
│   │   ├── task_service.py      # CRUD, перенесення "хвостів", фільтрація на сьогодні
│   │   ├── user_service.py      # Створення/отримання юзера, налаштування
│   │   └── ai_parser.py         # Обробка тексту та аудіо через Gemini
│   │
│   ├── bot/                     # Логіка Telegram-бота (aiogram 3)
│   │   ├── handlers/            # Обробники команд, тексту, аудіо
│   │   │   ├── start.py
│   │   │   ├── voice_text.py    # Прийом ГС та тексту, підтвердження
│   │   │   └── callbacks.py     # Кнопки підтвердження / редагування
│   │   ├── keyboards/           # Інлайн-клавіатури
│   │   └── middlewares/         # Перевірка користувача в БД, обробка сесій
│   │
│   ├── scheduler/               # Планувальник (APScheduler)
│   │   ├── manager.py           # Ініціалізація джобів
│   │   └── jobs.py              # 00:00 рев'ю, 09:00 ранковий пуш, перевірка дедлайнів
│   │
│   └── api/                     # FastAPI бекенд (для Mini App, Етап 2)
│       ├── auth.py              # Валідація Telegram initData
│       └── routes/              # Ендпоінти для списку задач, календаря, дашборду
│
├── tests/                       # Автоматизовані тести (pytest)
│   ├── conftest.py              # Fixtures (in-memory SQLite, async client, mocks)
│   └── test_smoke.py
│
├── frontend/                    # Telegram Mini App (React + Vite + Tailwind, Етап 2)
├── .env.example
├── .gitignore
├── pyproject.toml               # Залежності проєкту (uv)
├── uv.lock
├── Agents.md                    # Інструкції та команди для агентів
└── main.py                      # Точка входу для запуску
