import React, { useState, useEffect, useMemo, useCallback } from 'react';
import type { CalendarDaySummary, TaskCreate, TaskPriority, TaskRead } from '../api/types';
import { fetchCalendarSummary, fetchTasks, createTask, deleteTask, toggleTask } from '../api/client';
import { TaskCard } from './TaskCard';
import { TaskCreationModal } from './TaskCreationModal';
import {
  ChevronLeft,
  ChevronRight,
  Calendar as CalendarIcon,
  Plus,
  Loader2,
  AlertCircle,
  RefreshCw,
  CheckCircle2,
} from 'lucide-react';

const UKRAINIAN_MONTHS = [
  'Січень',
  'Лютий',
  'Березень',
  'Квітень',
  'Травень',
  'Червень',
  'Липень',
  'Серпень',
  'Вересень',
  'Жовтень',
  'Листопад',
  'Грудень',
];

const UKRAINIAN_MONTHS_GENITIVE = [
  'січня',
  'лютого',
  'березня',
  'квітня',
  'травня',
  'червня',
  'липня',
  'серпня',
  'вересня',
  'жовтня',
  'листопада',
  'грудня',
];

const WEEKDAY_NAMES = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Нд'];

const PRIORITY_ORDER: Record<TaskPriority, number> = {
  high: 0,
  medium: 1,
  low: 2,
};

function formatUkrainianDate(dateStr: string): string {
  const parts = dateStr.split('-');
  if (parts.length !== 3) return dateStr;
  const year = parseInt(parts[0], 10);
  const month = parseInt(parts[1], 10);
  const day = parseInt(parts[2], 10);
  const monthName = UKRAINIAN_MONTHS_GENITIVE[month - 1] || '';
  return `${day} ${monthName} ${year}`;
}

interface CalendarViewProps {
  userTimezone?: string;
}

export const CalendarView: React.FC<CalendarViewProps> = ({ userTimezone }) => {
  const todayStr = useMemo(() => new Date().toISOString().split('T')[0], []);
  const [currentYear, setCurrentYear] = useState<number>(() => new Date().getFullYear());
  const [currentMonth, setCurrentMonth] = useState<number>(() => new Date().getMonth() + 1);
  const [selectedDate, setSelectedDate] = useState<string>(todayStr);

  const [summaries, setSummaries] = useState<CalendarDaySummary[]>([]);
  const [summaryLoading, setSummaryLoading] = useState<boolean>(false);
  const [summaryError, setSummaryError] = useState<string | null>(null);

  const [tasks, setTasks] = useState<TaskRead[]>([]);
  const [tasksLoading, setTasksLoading] = useState<boolean>(false);
  const [tasksError, setTasksError] = useState<string | null>(null);

  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);
  const [errorToast, setErrorToast] = useState<string | null>(null);

  // Map of daily summaries keyed by 'YYYY-MM-DD'
  const summaryMap = useMemo(() => {
    const map = new Map<string, CalendarDaySummary>();
    for (const item of summaries) {
      map.set(item.date, item);
    }
    return map;
  }, [summaries]);

  // Load calendar monthly summary
  const loadSummary = useCallback(async (year: number, month: number) => {
    setSummaryLoading(true);
    setSummaryError(null);
    try {
      const data = await fetchCalendarSummary(year, month);
      setSummaries(data);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Не вдалося завантажити календар';
      setSummaryError(msg);
    } finally {
      setSummaryLoading(false);
    }
  }, []);

  // Load tasks for the selected date
  const loadTasksForDate = useCallback(async (dateToFetch: string) => {
    setTasksLoading(true);
    setTasksError(null);
    try {
      const data = await fetchTasks(dateToFetch);
      setTasks(data);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Не вдалося завантажити завдання';
      setTasksError(msg);
    } finally {
      setTasksLoading(false);
    }
  }, []);

  // Initial and reactive load for monthly summary
  useEffect(() => {
    loadSummary(currentYear, currentMonth);
  }, [currentYear, currentMonth, loadSummary]);

  // Reactive load for selected date tasks
  useEffect(() => {
    loadTasksForDate(selectedDate);
  }, [selectedDate, loadTasksForDate]);

  // Month navigation handlers
  const handlePrevMonth = () => {
    try {
      window.Telegram?.WebApp?.HapticFeedback?.impactOccurred('light');
    } catch {
      // ignore
    }
    if (currentMonth === 1) {
      setCurrentYear((y) => y - 1);
      setCurrentMonth(12);
    } else {
      setCurrentMonth((m) => m - 1);
    }
  };

  const handleNextMonth = () => {
    try {
      window.Telegram?.WebApp?.HapticFeedback?.impactOccurred('light');
    } catch {
      // ignore
    }
    if (currentMonth === 12) {
      setCurrentYear((y) => y + 1);
      setCurrentMonth(1);
    } else {
      setCurrentMonth((m) => m + 1);
    }
  };

  const handleTodayShortcut = () => {
    try {
      window.Telegram?.WebApp?.HapticFeedback?.impactOccurred('light');
    } catch {
      // ignore
    }
    const now = new Date();
    const nowYear = now.getFullYear();
    const nowMonth = now.getMonth() + 1;
    setCurrentYear(nowYear);
    setCurrentMonth(nowMonth);
    setSelectedDate(todayStr);
  };

  const handleSelectDay = (dateStr: string) => {
    try {
      window.Telegram?.WebApp?.HapticFeedback?.impactOccurred('light');
    } catch {
      // ignore
    }
    setSelectedDate(dateStr);
  };

  // Helper to recompute and update local summary dot after task changes
  const updateSummaryForDate = (dateStr: string, updatedTasks: TaskRead[]) => {
    const total = updatedTasks.length;
    const completed = updatedTasks.filter((t) => t.status === 'done').length;

    setSummaries((prev) => {
      const filtered = prev.filter((s) => s.date !== dateStr);
      if (total === 0) {
        return filtered;
      }
      let status: 'all_done' | 'partial' | 'todo_only';
      if (completed === total && total > 0) {
        status = 'all_done';
      } else if (completed > 0 && completed < total) {
        status = 'partial';
      } else {
        status = 'todo_only';
      }
      return [...filtered, { date: dateStr, total_tasks: total, completed_tasks: completed, status }];
    });
  };

  // Optimistic Toggle
  const handleToggle = async (taskId: number) => {
    const previous = [...tasks];
    const optimistic = tasks.map((t) =>
      t.id === taskId
        ? { ...t, status: (t.status === 'done' ? 'todo' : 'done') as TaskRead['status'] }
        : t
    );
    setTasks(optimistic);
    updateSummaryForDate(selectedDate, optimistic);

    try {
      const serverUpdated = await toggleTask(taskId);
      const synced = tasks.map((t) => (t.id === taskId ? serverUpdated : t));
      setTasks(synced);
      updateSummaryForDate(selectedDate, synced);
    } catch {
      setTasks(previous);
      updateSummaryForDate(selectedDate, previous);
      setErrorToast('Не вдалося змінити статус завдання.');
      setTimeout(() => setErrorToast(null), 4000);
    }
  };

  // Optimistic Delete
  const handleDelete = async (taskId: number) => {
    const previous = [...tasks];
    const optimistic = tasks.filter((t) => t.id !== taskId);
    setTasks(optimistic);
    updateSummaryForDate(selectedDate, optimistic);

    try {
      await deleteTask(taskId);
    } catch {
      setTasks(previous);
      updateSummaryForDate(selectedDate, previous);
      setErrorToast('Не вдалося видалити завдання.');
      setTimeout(() => setErrorToast(null), 4000);
    }
  };

  // Create Task
  const handleCreateTask = async (payload: TaskCreate) => {
    const created = await createTask(payload);
    const updated = [...tasks, created];
    setTasks(updated);
    updateSummaryForDate(selectedDate, updated);
  };

  // Sort tasks: `todo` tasks first by priority, then `done` tasks
  const sortedTasks = useMemo(() => {
    return [...tasks].sort((a, b) => {
      if (a.status !== b.status) {
        if (a.status === 'todo') return -1;
        if (b.status === 'todo') return 1;
      }
      const pDiff = (PRIORITY_ORDER[a.priority] ?? 1) - (PRIORITY_ORDER[b.priority] ?? 1);
      if (pDiff !== 0) return pDiff;
      return a.id - b.id;
    });
  }, [tasks]);

  // Calendar Grid Calculation
  const { prevPaddingDays, currentDays, nextPaddingDays } = useMemo(() => {
    // 0 is Sunday in JS, so (getDay() + 6) % 7 yields 0 for Monday ... 6 for Sunday
    const firstDayOfWeek = (new Date(currentYear, currentMonth - 1, 1).getDay() + 6) % 7;
    const daysInMonth = new Date(currentYear, currentMonth, 0).getDate();
    const daysInPrevMonth = new Date(currentYear, currentMonth - 1, 0).getDate();

    const prevDays: number[] = [];
    for (let i = firstDayOfWeek - 1; i >= 0; i--) {
      prevDays.push(daysInPrevMonth - i);
    }

    const currDays: number[] = [];
    for (let i = 1; i <= daysInMonth; i++) {
      currDays.push(i);
    }

    const totalCells = prevDays.length + currDays.length;
    const nextCount = (7 - (totalCells % 7)) % 7;
    const nextDays: number[] = [];
    for (let i = 1; i <= nextCount; i++) {
      nextDays.push(i);
    }

    return {
      prevPaddingDays: prevDays,
      currentDays: currDays,
      nextPaddingDays: nextDays,
    };
  }, [currentYear, currentMonth]);

  const monthLabel = `${UKRAINIAN_MONTHS[currentMonth - 1]} ${currentYear}`;
  const totalCount = tasks.length;
  const doneCount = tasks.filter((t) => t.status === 'done').length;

  return (
    <div className="space-y-5 animate-in fade-in duration-200">
      {/* Month Header Navigation */}
      <div className="p-4 rounded-2xl bg-secondary/70 border border-black/5 dark:border-white/5 space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CalendarIcon className="w-5 h-5 text-primary" />
            <span className="font-bold text-base">{monthLabel}</span>
          </div>

          <div className="flex items-center gap-1.5">
            <button
              type="button"
              onClick={handleTodayShortcut}
              className="text-xs font-medium px-2.5 py-1 rounded-lg bg-background hover:bg-secondary text-primary border border-black/5 dark:border-white/5 transition-colors cursor-pointer"
            >
              Сьогодні
            </button>
            <div className="flex items-center">
              <button
                type="button"
                onClick={handlePrevMonth}
                aria-label="Попередній місяць"
                className="p-1.5 rounded-lg text-muted hover:text-foreground hover:bg-background transition-colors cursor-pointer"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <button
                type="button"
                onClick={handleNextMonth}
                aria-label="Наступний місяць"
                className="p-1.5 rounded-lg text-muted hover:text-foreground hover:bg-background transition-colors cursor-pointer"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>

        {/* Calendar Error Banner with Retry */}
        {summaryError && (
          <div className="p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-500 text-xs flex items-center justify-between">
            <div className="flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{summaryError}</span>
            </div>
            <button
              type="button"
              onClick={() => loadSummary(currentYear, currentMonth)}
              className="inline-flex items-center gap-1 text-xs font-semibold underline hover:opacity-80"
            >
              <RefreshCw className="w-3 h-3" />
              <span>Спробувати знову</span>
            </button>
          </div>
        )}

        {/* Weekday Headers (Monday to Sunday) */}
        <div className="grid grid-cols-7 text-center font-medium text-xs text-muted pt-1">
          {WEEKDAY_NAMES.map((name) => (
            <div key={name} className="py-1">
              {name}
            </div>
          ))}
        </div>

        {/* Calendar Grid or Loading State */}
        {summaryLoading ? (
          <div className="py-10 flex flex-col items-center justify-center space-y-2.5">
            <Loader2 className="w-6 h-6 animate-spin text-primary" />
            <p className="text-xs text-muted">Завантаження календаря...</p>
          </div>
        ) : (
          <div className="grid grid-cols-7 gap-1">
            {/* Previous month padding */}
            {prevPaddingDays.map((day) => (
              <div
                key={`prev-${day}`}
                className="h-10 sm:h-12 flex flex-col items-center justify-center rounded-xl text-muted/30 text-xs select-none"
              >
                <span>{day}</span>
              </div>
            ))}

            {/* Current month days */}
            {currentDays.map((day) => {
              const dateStr = `${currentYear}-${String(currentMonth).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
              const isSelected = selectedDate === dateStr;
              const isToday = todayStr === dateStr;
              const daySummary = summaryMap.get(dateStr);

              return (
                <button
                  key={`curr-${day}`}
                  type="button"
                  onClick={() => handleSelectDay(dateStr)}
                  className={`h-10 sm:h-12 flex flex-col items-center justify-center relative rounded-xl text-xs font-medium transition-all duration-150 cursor-pointer ${
                    isSelected
                      ? 'bg-primary text-primary-foreground font-bold shadow-md shadow-primary/25 scale-105 z-10'
                      : isToday
                      ? 'border-2 border-primary text-primary font-bold bg-background'
                      : 'hover:bg-background/80 text-foreground'
                  }`}
                >
                  <span>{day}</span>

                  {/* Status Indicator Dot (REQ-TMA-03) */}
                  {daySummary && daySummary.total_tasks > 0 && (
                    <span
                      className={`w-1.5 h-1.5 rounded-full mt-0.5 transition-colors ${
                        daySummary.status === 'all_done'
                          ? isSelected
                            ? 'bg-emerald-300 ring-1 ring-white/50'
                            : 'bg-emerald-500'
                          : daySummary.status === 'partial'
                          ? isSelected
                            ? 'bg-amber-300 ring-1 ring-white/50'
                            : 'bg-amber-500'
                          : isSelected
                          ? 'bg-slate-300 ring-1 ring-white/50'
                          : 'bg-slate-400'
                      }`}
                    />
                  )}
                </button>
              );
            })}

            {/* Next month padding */}
            {nextPaddingDays.map((day) => (
              <div
                key={`next-${day}`}
                className="h-10 sm:h-12 flex flex-col items-center justify-center rounded-xl text-muted/30 text-xs select-none"
              >
                <span>{day}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Error notification banner / toast on rollback */}
      {errorToast && (
        <div className="p-3 rounded-xl bg-red-500/15 border border-red-500/30 text-red-500 text-xs flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{errorToast}</span>
          </div>
          <button
            type="button"
            onClick={() => setErrorToast(null)}
            className="p-1 hover:opacity-80 text-sm font-bold"
          >
            ×
          </button>
        </div>
      )}

      {/* Selected Date Tasks Section */}
      <div className="space-y-3">
        {/* Section Header */}
        <div className="flex items-center justify-between px-1">
          <div>
            <h3 className="font-semibold text-sm">
              Завдання на {formatUkrainianDate(selectedDate)}
            </h3>
          </div>
          <span className="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-primary/10 text-primary">
            {doneCount} з {totalCount} виконано
          </span>
        </div>

        {/* Loading Spinner for Selected Date Tasks */}
        {tasksLoading ? (
          <div className="py-8 flex flex-col items-center justify-center space-y-2">
            <Loader2 className="w-6 h-6 animate-spin text-primary" />
            <p className="text-xs text-muted">Завантаження завдань...</p>
          </div>
        ) : tasksError ? (
          <div className="p-4 rounded-2xl bg-secondary/60 border border-red-500/20 text-center space-y-2">
            <p className="text-xs text-red-500">{tasksError}</p>
            <button
              type="button"
              onClick={() => loadTasksForDate(selectedDate)}
              className="text-xs text-primary font-semibold underline"
            >
              Спробувати знову
            </button>
          </div>
        ) : totalCount === 0 ? (
          /* Empty State */
          <div className="py-10 px-4 rounded-2xl bg-secondary/40 border border-dashed border-black/10 dark:border-white/10 flex flex-col items-center justify-center text-center space-y-2.5">
            <div className="w-10 h-10 rounded-full bg-primary/10 text-primary flex items-center justify-center">
              <CheckCircle2 className="w-5 h-5" />
            </div>
            <div className="space-y-1 max-w-xs">
              <h4 className="font-semibold text-xs text-foreground">На цей день завдань немає</h4>
              <p className="text-[11px] text-muted">
                Натисніть кнопку нижче, щоб додати перше завдання на цей день.
              </p>
            </div>
          </div>
        ) : (
          /* Task List */
          <div className="space-y-2">
            {sortedTasks.map((task) => (
              <TaskCard
                key={task.id}
                task={task}
                onToggle={handleToggle}
                onDelete={handleDelete}
                userTimezone={userTimezone}
              />
            ))}
          </div>
        )}

        {/* Add Task Button */}
        <div className="pt-2">
          <button
            type="button"
            onClick={() => setIsModalOpen(true)}
            className="w-full py-3.5 px-4 rounded-2xl bg-primary text-primary-foreground font-semibold text-sm flex items-center justify-center gap-2 shadow-lg shadow-primary/25 hover:opacity-95 active:scale-[0.98] transition-all cursor-pointer"
          >
            <Plus className="w-4 h-4 stroke-[2.5]" />
            <span>+ Додати завдання</span>
          </button>
        </div>
      </div>

      {/* Task Creation Modal */}
      <TaskCreationModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSubmit={handleCreateTask}
        targetDate={selectedDate}
        userTimezone={userTimezone}
      />
    </div>
  );
};
