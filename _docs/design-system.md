# Design System & UI Guidelines

This document defines the UI/UX standards, component rules, and design tokens for the Telegram Mini App (TMA) and Telegram Bot messages.
All agents and developers touching the UI must read and follow this document, as mandated by `Agents.md`.

---

## 1. Telegram Mini App (TMA) Core Rules

1. **Native Telegram Theme Integration:**
   - The UI must adapt dynamically to Telegram's native theme (dark mode, light mode, custom accent colors).
   - Use Telegram theme CSS variables or extract them via `@telegram-apps/sdk-react`:
     - `--tg-theme-bg-color` / `bg-background`
     - `--tg-theme-secondary-bg-color` / `bg-muted`
     - `--tg-theme-text-color` / `text-foreground`
     - `--tg-theme-hint-color` / `text-muted-foreground`
     - `--tg-theme-button-color` / `bg-primary`
     - `--tg-theme-button-text-color` / `text-primary-foreground`

2. **Viewport and Mobile Adaptation:**
   - Always expand the Mini App immediately on mount:
     ```typescript
     window.Telegram?.WebApp?.ready();
     window.Telegram?.WebApp?.expand();
     ```
   - Respect mobile safe-area insets (`env(safe-area-inset-top)` and `env(safe-area-inset-bottom)`).
   - Disable bounce effect on pull-down where supported to feel like a native app.

3. **Haptic Feedback:**
   - Use Telegram's native haptics for interactive tactile response:
     - `impactOccurred('light')` when toggling a task checkbox.
     - `impactOccurred('medium')` when deleting or rolling over a task.
     - `notificationOccurred('success')` upon saving a batch of tasks or reaching a daily streak.

---

## 2. Component Guidelines

### A. Task Checklist Item (`TaskCard`)
* **State: Active (`todo`)**
  - Crisp text with primary color.
  - Interactive circular checkbox.
  - Badges visible: Priority, Tag, Deadline countdown.
* **State: Completed (`done`)**
  - Checked circular checkbox with accent fill.
  - Strikethrough text (`line-through`) with muted opacity (`opacity-60`).
  - Seamless animated transition between states.
* **Priority Color Tokens:**
  - **High:** `bg-red-500/10 text-red-500 border-red-500/20`
  - **Medium:** `bg-amber-500/10 text-amber-500 border-amber-500/20`
  - **Low:** `bg-slate-500/10 text-slate-400 border-slate-500/20`

### B. Calendar View
* Clean grid layout (7 days per row, starting Monday).
* Current selected date highlighted with a rounded accent pill.
* Status indicators:
  - **Green dot:** All tasks for that date completed (100%).
  - **Amber dot:** Partially completed tasks.
  - **Gray dot:** Tasks scheduled with 0% completed.

### C. Dashboard & Analytics (`Recharts`)
* Charts must use a theme-aware palette (no harsh hardcoded hex colors).
* Tooltips must match Telegram secondary background (`--tg-theme-secondary-bg-color`).
* Daily streak card must feature a prominent flame icon (`🔥`), bold number, and celebratory micro-copy.

---

## 3. Telegram Bot Message Formatting

All bot chat messages must follow a unified structure and semantic emoji palette:

1. **Header:** Short, bold status (e.g., `📋 План на сьогодні (19.11.2026)`).
2. **List Items:**
   - `[ ]` or `⏳` for pending tasks.
   - `[x]` or `✅` for completed tasks.
   - Format: `• [Назва задачі] — ⚠️ Високий | 🏷️ #робота | 🕒 до 18:00`.
3. **Buttons / Keyboards:**
   - Maximum 2 buttons per row.
   - Positive/confirmation actions first (`[✅ Зберегти]`), followed by modifications (`[✏️ Виправити]`).
   - WebApp buttons: clearly labeled with a rocket or notebook icon (`[🚀 Відкрити план]`).
