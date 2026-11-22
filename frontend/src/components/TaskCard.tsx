import React from 'react';
import type { TaskPriority, TaskRead } from '../api/types';
import { Check, Trash2 } from 'lucide-react';

interface TaskCardProps {
  task: TaskRead;
  onToggle: (taskId: number) => void;
  onDelete: (taskId: number) => void;
}

export const TaskCard: React.FC<TaskCardProps> = ({ task, onToggle, onDelete }) => {
  const isDone = task.status === 'done';

  const handleToggleClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      window.Telegram?.WebApp?.HapticFeedback?.impactOccurred('light');
    } catch {
      // ignore
    }
    onToggle(task.id);
  };

  const handleDeleteClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      window.Telegram?.WebApp?.HapticFeedback?.impactOccurred('medium');
    } catch {
      // ignore
    }
    onDelete(task.id);
  };

  const getPriorityClasses = (priority: TaskPriority): string => {
    switch (priority) {
      case 'high':
        return 'bg-red-500/10 text-red-500 border-red-500/20';
      case 'medium':
        return 'bg-amber-500/10 text-amber-500 border-amber-500/20';
      case 'low':
        return 'bg-slate-500/10 text-slate-400 border-slate-500/20';
      default:
        return 'bg-slate-500/10 text-slate-400 border-slate-500/20';
    }
  };

  const getPriorityLabel = (priority: TaskPriority): string => {
    switch (priority) {
      case 'high':
        return 'Високий';
      case 'medium':
        return 'Середній';
      case 'low':
        return 'Низький';
      default:
        return priority;
    }
  };

  const formatDeadline = (isoString: string | null): string | null => {
    if (!isoString) return null;
    try {
      const d = new Date(isoString);
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });
    } catch {
      return null;
    }
  };

  const formatRecurrence = (rec: string | null): string | null => {
    if (!rec) return null;
    const clean = rec.trim().toLowerCase();
    if (!clean) return null;

    if (clean === 'daily' || clean === 'weekdays:[0,1,2,3,4,5,6]') {
      return '🔁 Щодня';
    }
    if (clean === 'weekdays' || clean === 'weekdays:[0,1,2,3,4]') {
      return '🔁 Будні';
    }
    if (clean === 'weekdays:[5,6]') {
      return '🔁 Вихідні';
    }

    const match = clean.match(/^weekdays:\[([0-9,\s]*)\]$/);
    if (match) {
      const parts = match[1]
        .split(',')
        .map((s) => s.trim())
        .filter((s) => s.length > 0 && !isNaN(Number(s)))
        .map(Number);

      if (parts.length === 0) return null;

      const uniqueDays = Array.from(new Set(parts)).sort((a, b) => a - b);
      const key = uniqueDays.join(',');

      if (key === '0,1,2,3,4,5,6') {
        return '🔁 Щодня';
      }
      if (key === '0,1,2,3,4') {
        return '🔁 Будні';
      }
      if (key === '5,6') {
        return '🔁 Вихідні';
      }

      const DAY_NAMES: Record<number, string> = {
        0: 'Пн',
        1: 'Вт',
        2: 'Ср',
        3: 'Чт',
        4: 'Пт',
        5: 'Сб',
        6: 'Нд',
      };

      const formattedDays = uniqueDays
        .map((d) => DAY_NAMES[d])
        .filter(Boolean)
        .join(', ');

      if (formattedDays) {
        return `🔁 ${formattedDays}`;
      }
    }

    return `🔁 ${rec}`;
  };

  const formattedDeadline = formatDeadline(task.deadline_at);
  const formattedRecurrence = formatRecurrence(task.recurrence);

  return (
    <div
      className={`group relative p-3.5 rounded-2xl bg-secondary/70 hover:bg-secondary border border-black/5 dark:border-white/5 transition-all duration-200 flex items-start gap-3 shadow-sm ${
        isDone ? 'bg-secondary/40' : ''
      }`}
    >
      {/* Animated Circular Checkbox */}
      <button
        type="button"
        role="checkbox"
        aria-checked={isDone}
        aria-label={isDone ? 'Позначити як невиконане' : 'Позначити як виконане'}
        onClick={handleToggleClick}
        className={`w-6 h-6 rounded-full flex items-center justify-center shrink-0 mt-0.5 transition-all duration-200 cursor-pointer border ${
          isDone
            ? 'bg-primary border-primary text-primary-foreground shadow-sm scale-100 ring-2 ring-primary/20'
            : 'border-muted hover:border-primary/70 bg-background/50 hover:scale-105'
        }`}
      >
        {isDone && <Check className="w-3.5 h-3.5 stroke-[2.5] animate-in zoom-in-75 duration-150" />}
      </button>

      {/* Task Content */}
      <div className="flex-1 min-w-0 flex flex-col gap-1.5 cursor-pointer" onClick={handleToggleClick}>
        <p
          className={`text-sm font-medium leading-snug break-words transition-all duration-200 ${
            isDone ? 'line-through opacity-60 text-muted' : 'text-foreground'
          }`}
        >
          {task.title}
        </p>

        {/* Badges row */}
        <div className="flex flex-wrap items-center gap-1.5">
          {/* Priority Badge */}
          <span
            className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium border ${getPriorityClasses(
              task.priority
            )}`}
          >
            {getPriorityLabel(task.priority)}
          </span>

          {/* Tag Chip */}
          {task.tag && (
            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium bg-background/70 text-muted border border-black/5 dark:border-white/5">
              #{task.tag}
            </span>
          )}

          {/* Deadline Countdown/Indicator */}
          {formattedDeadline && (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-background/70 text-muted border border-black/5 dark:border-white/5">
              🕒 {formattedDeadline}
            </span>
          )}

          {/* Recurrence Badge */}
          {formattedRecurrence && (
            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium bg-primary/10 text-primary border border-primary/20">
              {formattedRecurrence}
            </span>
          )}
        </div>
      </div>

      {/* Quick Delete Action Button */}
      <button
        type="button"
        aria-label="Видалити завдання"
        onClick={handleDeleteClick}
        className="p-1.5 rounded-lg text-muted/60 hover:text-red-500 hover:bg-red-500/10 transition-colors shrink-0 -mr-1 -mt-0.5 opacity-70 group-hover:opacity-100"
      >
        <Trash2 className="w-4 h-4" />
      </button>
    </div>
  );
};
