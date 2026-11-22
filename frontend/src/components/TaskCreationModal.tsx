import React, { useState, useEffect } from 'react';
import type { TaskCreate, TaskPriority } from '../api/types';
import { X, Clock, Tag as TagIcon, Repeat, Flag } from 'lucide-react';

interface TaskCreationModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (payload: TaskCreate) => Promise<void> | void;
  targetDate?: string;
}

type RecurrenceMode = 'none' | 'daily' | 'weekdays' | 'custom';

const WEEKDAY_PILLS = [
  { label: 'Пн', day: 0 },
  { label: 'Вт', day: 1 },
  { label: 'Ср', day: 2 },
  { label: 'Чт', day: 3 },
  { label: 'Пт', day: 4 },
  { label: 'Сб', day: 5 },
  { label: 'Нд', day: 6 },
];

export const TaskCreationModal: React.FC<TaskCreationModalProps> = ({
  isOpen,
  onClose,
  onSubmit,
  targetDate,
}) => {
  const [title, setTitle] = useState('');
  const [priority, setPriority] = useState<TaskPriority>('medium');
  const [tag, setTag] = useState('');
  const [deadlineTime, setDeadlineTime] = useState('');
  const [recurrenceMode, setRecurrenceMode] = useState<RecurrenceMode>('none');
  const [customDays, setCustomDays] = useState<number[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Reset form whenever modal opens
  useEffect(() => {
    if (isOpen) {
      setTitle('');
      setPriority('medium');
      setTag('');
      setDeadlineTime('');
      setRecurrenceMode('none');
      setCustomDays([]);
      setIsSubmitting(false);
    }
  }, [isOpen]);

  if (!isOpen) {
    return null;
  }

  const effectiveDate = targetDate || new Date().toISOString().split('T')[0];

  const triggerHaptic = (style: 'light' | 'medium' = 'light') => {
    try {
      window.Telegram?.WebApp?.HapticFeedback?.impactOccurred(style);
    } catch {
      // ignore
    }
  };

  const handleCustomModeSelect = () => {
    triggerHaptic('light');
    setRecurrenceMode('custom');
    if (customDays.length === 0) {
      const [y, m, d] = effectiveDate.split('-').map(Number);
      const dateObj = new Date(y, m - 1, d);
      const defaultWeekday = (dateObj.getDay() + 6) % 7;
      setCustomDays([defaultWeekday]);
    }
  };

  const toggleDay = (day: number) => {
    triggerHaptic('light');
    setCustomDays((prev) => {
      if (prev.includes(day)) {
        return prev.filter((d) => d !== day);
      }
      return [...prev, day].sort((a, b) => a - b);
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const cleanTitle = title.trim();
    if (!cleanTitle || isSubmitting) return;
    if (recurrenceMode === 'custom' && customDays.length === 0) return;

    setIsSubmitting(true);
    try {
      let deadlineAt: string | null = null;
      if (deadlineTime.trim()) {
        const d = new Date(`${effectiveDate}T${deadlineTime.trim()}:00`);
        if (!isNaN(d.getTime())) {
          deadlineAt = d.toISOString();
        }
      }

      const cleanTag = tag.trim().replace(/^#+/, '').slice(0, 50);

      let recurrencePayload: string | null = null;
      if (recurrenceMode === 'daily') {
        recurrencePayload = 'daily';
      } else if (recurrenceMode === 'weekdays') {
        recurrencePayload = 'weekdays:[0,1,2,3,4]';
      } else if (recurrenceMode === 'custom') {
        const sorted = Array.from(new Set(customDays)).sort((a, b) => a - b);
        recurrencePayload = `weekdays:[${sorted.join(',')}]`;
      }

      const payload: TaskCreate = {
        title: cleanTitle.slice(0, 255),
        target_date: effectiveDate,
        priority,
        tag: cleanTag || null,
        deadline_at: deadlineAt,
        recurrence: recurrencePayload,
      };

      await onSubmit(payload);
      onClose();
    } finally {
      setIsSubmitting(false);
    }
  };

  const isCustomEmpty = recurrenceMode === 'custom' && customDays.length === 0;
  const isSubmitDisabled = !title.trim() || isSubmitting || isCustomEmpty;

  return (
    <div
      className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/60 backdrop-blur-xs p-0 sm:p-4 animate-in fade-in duration-200"
      onClick={onClose}
    >
      <div
        className="w-full max-w-lg bg-background rounded-t-3xl sm:rounded-3xl p-5 sm:p-6 shadow-2xl border border-black/10 dark:border-white/10 space-y-5 animate-in slide-in-from-bottom duration-250 max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between pb-3 border-b border-secondary">
          <h2 className="text-lg font-bold">Нове завдання</h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Закрити"
            className="p-1 rounded-full text-muted hover:text-foreground hover:bg-secondary transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Title Input */}
          <div className="space-y-1.5">
            <label htmlFor="task-title" className="text-xs font-semibold text-muted uppercase tracking-wider">
              Назва завдання <span className="text-red-500">*</span>
            </label>
            <input
              id="task-title"
              type="text"
              required
              maxLength={255}
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Що потрібно зробити?"
              autoFocus
              className="w-full px-3.5 py-2.5 rounded-xl bg-secondary border border-transparent focus:border-primary focus:bg-background outline-hidden text-sm text-foreground transition-all"
            />
          </div>

          {/* Priority Selector */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-muted uppercase tracking-wider flex items-center gap-1">
              <Flag className="w-3.5 h-3.5 text-primary" />
              <span>Пріоритет</span>
            </label>
            <div className="grid grid-cols-3 gap-2">
              <button
                type="button"
                onClick={() => setPriority('low')}
                className={`py-2 px-3 rounded-xl text-xs font-medium border transition-all ${
                  priority === 'low'
                    ? 'bg-slate-500/20 text-slate-300 border-slate-500/50 shadow-xs'
                    : 'bg-secondary text-muted border-transparent hover:border-black/10 dark:hover:border-white/10'
                }`}
              >
                Низький
              </button>
              <button
                type="button"
                onClick={() => setPriority('medium')}
                className={`py-2 px-3 rounded-xl text-xs font-medium border transition-all ${
                  priority === 'medium'
                    ? 'bg-amber-500/20 text-amber-500 border-amber-500/50 shadow-xs'
                    : 'bg-secondary text-muted border-transparent hover:border-black/10 dark:hover:border-white/10'
                }`}
              >
                Середній
              </button>
              <button
                type="button"
                onClick={() => setPriority('high')}
                className={`py-2 px-3 rounded-xl text-xs font-medium border transition-all ${
                  priority === 'high'
                    ? 'bg-red-500/20 text-red-500 border-red-500/50 shadow-xs'
                    : 'bg-secondary text-muted border-transparent hover:border-black/10 dark:hover:border-white/10'
                }`}
              >
                Високий
              </button>
            </div>
          </div>

          {/* Tag & Deadline row */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {/* Tag Input */}
            <div className="space-y-1.5">
              <label htmlFor="task-tag" className="text-xs font-semibold text-muted uppercase tracking-wider flex items-center gap-1">
                <TagIcon className="w-3.5 h-3.5 text-primary" />
                <span>Тег</span>
              </label>
              <input
                id="task-tag"
                type="text"
                maxLength={50}
                value={tag}
                onChange={(e) => setTag(e.target.value.replace(/^#+/, ''))}
                placeholder="напр. робота, дім"
                className="w-full px-3.5 py-2 rounded-xl bg-secondary border border-transparent focus:border-primary focus:bg-background outline-hidden text-sm text-foreground transition-all"
              />
            </div>

            {/* Deadline Time Input */}
            <div className="space-y-1.5">
              <label htmlFor="task-deadline" className="text-xs font-semibold text-muted uppercase tracking-wider flex items-center gap-1">
                <Clock className="w-3.5 h-3.5 text-primary" />
                <span>Дедлайн (необов&apos;язково)</span>
              </label>
              <div className="flex items-center gap-1.5">
                <input
                  id="task-deadline"
                  type="time"
                  value={deadlineTime}
                  onChange={(e) => setDeadlineTime(e.target.value)}
                  className="flex-1 min-w-0 w-full px-3.5 py-2 rounded-xl bg-secondary border border-transparent focus:border-primary focus:bg-background outline-hidden text-sm text-foreground transition-all"
                />
                {deadlineTime && (
                  <button
                    type="button"
                    aria-label="Очистити дедлайн"
                    onClick={() => {
                      triggerHaptic('light');
                      setDeadlineTime('');
                    }}
                    className="shrink-0 px-2.5 py-2 rounded-xl bg-secondary text-muted hover:text-red-500 hover:bg-red-500/10 border border-transparent transition-colors text-xs font-semibold cursor-pointer"
                  >
                    ✕
                  </button>
                )}
              </div>
            </div>
          </div>

          {/* Recurrence Selector */}
          <div className="space-y-2">
            <label className="text-xs font-semibold text-muted uppercase tracking-wider flex items-center gap-1">
              <Repeat className="w-3.5 h-3.5 text-primary" />
              <span>Повторення</span>
            </label>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              <button
                type="button"
                onClick={() => {
                  triggerHaptic('light');
                  setRecurrenceMode('none');
                }}
                className={`py-2 px-2.5 rounded-xl text-xs font-medium border text-center transition-all ${
                  recurrenceMode === 'none'
                    ? 'bg-primary/15 text-primary border-primary/40 font-semibold shadow-xs'
                    : 'bg-secondary text-muted border-transparent hover:border-black/10 dark:hover:border-white/10'
                }`}
              >
                Немає
              </button>
              <button
                type="button"
                onClick={() => {
                  triggerHaptic('light');
                  setRecurrenceMode('daily');
                }}
                className={`py-2 px-2.5 rounded-xl text-xs font-medium border text-center transition-all ${
                  recurrenceMode === 'daily'
                    ? 'bg-primary/15 text-primary border-primary/40 font-semibold shadow-xs'
                    : 'bg-secondary text-muted border-transparent hover:border-black/10 dark:hover:border-white/10'
                }`}
              >
                🔁 Щодня
              </button>
              <button
                type="button"
                onClick={() => {
                  triggerHaptic('light');
                  setRecurrenceMode('weekdays');
                }}
                className={`py-2 px-2.5 rounded-xl text-xs font-medium border text-center transition-all ${
                  recurrenceMode === 'weekdays'
                    ? 'bg-primary/15 text-primary border-primary/40 font-semibold shadow-xs'
                    : 'bg-secondary text-muted border-transparent hover:border-black/10 dark:hover:border-white/10'
                }`}
              >
                🔁 Будні
              </button>
              <button
                type="button"
                onClick={handleCustomModeSelect}
                className={`py-2 px-2.5 rounded-xl text-xs font-medium border text-center transition-all ${
                  recurrenceMode === 'custom'
                    ? 'bg-primary/15 text-primary border-primary/40 font-semibold shadow-xs'
                    : 'bg-secondary text-muted border-transparent hover:border-black/10 dark:hover:border-white/10'
                }`}
              >
                📅 Вибрати дні
              </button>
            </div>

            {/* Custom Day Pills sub-row */}
            {recurrenceMode === 'custom' && (
              <div className="pt-1 space-y-1.5 animate-in fade-in duration-150">
                <div className="grid grid-cols-7 gap-1.5">
                  {WEEKDAY_PILLS.map(({ label, day }) => {
                    const isSelected = customDays.includes(day);
                    return (
                      <button
                        key={day}
                        type="button"
                        onClick={() => toggleDay(day)}
                        className={`py-2 rounded-xl text-xs font-semibold text-center transition-all cursor-pointer ${
                          isSelected
                            ? 'bg-primary text-primary-foreground shadow-xs'
                            : 'bg-secondary text-muted hover:text-foreground border border-transparent'
                        }`}
                      >
                        {label}
                      </button>
                    );
                  })}
                </div>
                {isCustomEmpty && (
                  <p className="text-xs text-amber-500 font-medium">
                    Оберіть хоча б один день
                  </p>
                )}
              </div>
            )}
          </div>

          {/* Actions */}
          <div className="pt-2 flex items-center gap-3">
            <button
              type="button"
              onClick={onClose}
              disabled={isSubmitting}
              className="flex-1 py-3 px-4 rounded-xl bg-secondary text-muted hover:text-foreground font-semibold text-sm transition-colors text-center"
            >
              Скасувати
            </button>
            <button
              type="submit"
              disabled={isSubmitDisabled}
              className="flex-1 py-3 px-4 rounded-xl bg-primary text-primary-foreground font-semibold text-sm transition-all hover:opacity-90 active:scale-[0.98] disabled:opacity-40 disabled:cursor-not-allowed text-center shadow-lg shadow-primary/20"
            >
              {isSubmitting ? 'Збереження...' : 'Створити'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
