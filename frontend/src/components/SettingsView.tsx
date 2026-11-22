import React, { useState, useEffect, useMemo, useCallback } from 'react';
import type { TimezoneOption, UserProfile } from '../api/types';
import { updateReminderInterval, updateTimezone } from '../api/client';
import {
  User,
  Clock,
  Calendar,
  Globe,
  Search,
  Check,
  Save,
  AlertCircle,
  CheckCircle2,
  Loader2,
  RefreshCw,
  X,
  Bell,
  BellOff,
  Minus,
  Plus,
  Info,
} from 'lucide-react';

interface SettingsViewProps {
  user: UserProfile;
  onUserUpdated: (updated: UserProfile) => void;
}

export const CURATED_TIMEZONES: TimezoneOption[] = [
  { label: '🇺🇦 Київ (UTC+2 / UTC+3)', value: 'Europe/Kyiv', region: 'Європа' },
  { label: '🇵🇱 Варшава (UTC+1 / UTC+2)', value: 'Europe/Warsaw', region: 'Європа' },
  { label: '🇬🇧 Лондон (UTC+0 / UTC+1)', value: 'Europe/London', region: 'Європа' },
  { label: '🇩🇪 Берлін (UTC+1 / UTC+2)', value: 'Europe/Berlin', region: 'Європа' },
  { label: '🇫🇷 Париж (UTC+1 / UTC+2)', value: 'Europe/Paris', region: 'Європа' },
  { label: '🇮🇹 Рим (UTC+1 / UTC+2)', value: 'Europe/Rome', region: 'Європа' },
  { label: '🇪🇸 Мадрид (UTC+1 / UTC+2)', value: 'Europe/Madrid', region: 'Європа' },
  { label: '🇨🇿 Прага (UTC+1 / UTC+2)', value: 'Europe/Prague', region: 'Європа' },
  { label: '🇺🇸 Нью-Йорк (UTC-5 / UTC-4)', value: 'America/New_York', region: 'Америка' },
  { label: '🇺🇸 Чикаго (UTC-6 / UTC-5)', value: 'America/Chicago', region: 'Америка' },
  { label: '🇺🇸 Лос-Анджелес (UTC-8 / UTC-7)', value: 'America/Los_Angeles', region: 'Америка' },
  { label: '🇨🇦 Торонто (UTC-5 / UTC-4)', value: 'America/Toronto', region: 'Америка' },
  { label: '🇧🇷 Сан-Паулу (UTC-3)', value: 'America/Sao_Paulo', region: 'Америка' },
  { label: '🇯🇵 Токіо (UTC+9)', value: 'Asia/Tokyo', region: 'Азія' },
  { label: '🇦🇪 Дубай (UTC+4)', value: 'Asia/Dubai', region: 'Азія' },
  { label: '🇸🇬 Сінгапур (UTC+8)', value: 'Asia/Singapore', region: 'Азія' },
  { label: '🇨🇳 Шанхай (UTC+8)', value: 'Asia/Shanghai', region: 'Азія' },
  { label: '🇬🇪 Тбілісі (UTC+4)', value: 'Asia/Tbilisi', region: 'Азія' },
  { label: '🇰🇿 Алмати (UTC+5)', value: 'Asia/Almaty', region: 'Азія' },
  { label: '🇦🇺 Сідней (UTC+10 / UTC+11)', value: 'Australia/Sydney', region: 'Океанія' },
  { label: '🇳🇿 Окленд (UTC+12 / UTC+13)', value: 'Pacific/Auckland', region: 'Океанія' },
  { label: '🌐 UTC (UTC+0)', value: 'UTC', region: 'Загальний' },
];

function formatLocalTime(tz: string): string {
  try {
    return new Intl.DateTimeFormat('uk-UA', {
      timeZone: tz,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
    }).format(new Date());
  } catch {
    return new Date().toLocaleTimeString('uk-UA');
  }
}

function formatAccountCreation(dateStr: string): string {
  try {
    const d = new Date(dateStr);
    return new Intl.DateTimeFormat('uk-UA', {
      day: 'numeric',
      month: 'long',
      year: 'numeric',
    }).format(d);
  } catch {
    return dateStr;
  }
}

export const REMINDER_PRESETS: Array<{ label: string; value: number | null }> = [
  { label: 'Вимкнено', value: null },
  { label: '1 год', value: 1 },
  { label: '2 год', value: 2 },
  { label: '3 год', value: 3 },
  { label: '4 год', value: 4 },
  { label: '5 год', value: 5 },
  { label: '6 год', value: 6 },
  { label: '8 год', value: 8 },
  { label: '12 год', value: 12 },
];

function formatReminderStatus(interval: number | null): string {
  if (interval === null) {
    return 'Вимкнено';
  }
  return `Кожні ${interval} год`;
}

export const SettingsView: React.FC<SettingsViewProps> = ({
  user,
  onUserUpdated,
}) => {
  const initialReminderInterval =
    user.reminder_interval_hours === undefined ? 4 : user.reminder_interval_hours;

  const [selectedTz, setSelectedTz] = useState<string>(user.timezone);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [savedSuccess, setSavedSuccess] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [currentTime, setCurrentTime] = useState<string>(() =>
    formatLocalTime(user.timezone)
  );

  // Periodic Telegram reminders state
  const [selectedInterval, setSelectedInterval] = useState<number | null>(
    initialReminderInterval
  );
  const [isSavingReminders, setIsSavingReminders] = useState<boolean>(false);
  const [remindersSavedSuccess, setRemindersSavedSuccess] = useState<boolean>(false);
  const [remindersError, setRemindersError] = useState<string | null>(null);

  // Synchronize internal selected timezone when external user prop updates
  useEffect(() => {
    setSelectedTz(user.timezone);
  }, [user.timezone]);

  // Synchronize internal selected reminder interval when external user prop updates
  useEffect(() => {
    setSelectedInterval(
      user.reminder_interval_hours === undefined ? 4 : user.reminder_interval_hours
    );
  }, [user.reminder_interval_hours]);

  // Live clock tick in user's current timezone
  useEffect(() => {
    const interval = setInterval(() => {
      setCurrentTime(formatLocalTime(user.timezone));
    }, 1000);
    return () => clearInterval(interval);
  }, [user.timezone]);

  const triggerLightHaptic = () => {
    try {
      window.Telegram?.WebApp?.HapticFeedback?.impactOccurred?.('light');
    } catch {
      // ignore outside Telegram environment
    }
  };

  const handleSelectInterval = (interval: number | null) => {
    setSelectedInterval(interval);
    setRemindersSavedSuccess(false);
    setRemindersError(null);
    triggerLightHaptic();
  };

  const handleDecrementInterval = () => {
    if (selectedInterval === null || selectedInterval <= 1) {
      return;
    }
    handleSelectInterval(selectedInterval - 1);
  };

  const handleIncrementInterval = () => {
    if (selectedInterval === null) {
      handleSelectInterval(1);
      return;
    }
    if (selectedInterval >= 24) {
      return;
    }
    handleSelectInterval(selectedInterval + 1);
  };

  const handleCustomIntervalInput = (raw: string) => {
    if (raw.trim() === '') {
      return;
    }
    const parsed = Number.parseInt(raw, 10);
    if (Number.isNaN(parsed)) {
      return;
    }
    const clamped = Math.min(24, Math.max(1, parsed));
    handleSelectInterval(clamped);
  };

  const handleSaveReminders = useCallback(async () => {
    setIsSavingReminders(true);
    setRemindersError(null);
    setRemindersSavedSuccess(false);

    try {
      const updatedUser = await updateReminderInterval(selectedInterval);
      try {
        window.Telegram?.WebApp?.HapticFeedback?.notificationOccurred?.('success');
      } catch {
        // ignore
      }
      setRemindersSavedSuccess(true);
      onUserUpdated(updatedUser);
    } catch (err) {
      try {
        window.Telegram?.WebApp?.HapticFeedback?.notificationOccurred?.('error');
      } catch {
        // ignore
      }
      const message =
        err instanceof Error
          ? err.message
          : 'Не вдалося оновити налаштування нагадувань';
      setRemindersError(message);
    } finally {
      setIsSavingReminders(false);
    }
  }, [selectedInterval, onUserUpdated]);

  // Reset success message when user chooses a different timezone
  const handleSelectTimezone = (tz: string) => {
    setSelectedTz(tz);
    setSavedSuccess(false);
    setError(null);
    triggerLightHaptic();
  };

  const handleSave = useCallback(async () => {
    setIsSaving(true);
    setError(null);
    setSavedSuccess(false);

    try {
      const updatedUser = await updateTimezone(selectedTz);
      try {
        window.Telegram?.WebApp?.HapticFeedback?.notificationOccurred?.('success');
      } catch {
        // ignore
      }
      setSavedSuccess(true);
      onUserUpdated(updatedUser);
    } catch (err) {
      try {
        window.Telegram?.WebApp?.HapticFeedback?.notificationOccurred?.('error');
      } catch {
        // ignore
      }
      const message =
        err instanceof Error ? err.message : 'Не вдалося оновити часовий пояс';
      setError(message);
    } finally {
      setIsSaving(false);
    }
  }, [selectedTz, onUserUpdated]);

  // Filter curated timezones by search query
  const filteredTimezones = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) {
      return CURATED_TIMEZONES;
    }
    return CURATED_TIMEZONES.filter(
      (tz) =>
        tz.label.toLowerCase().includes(q) ||
        tz.value.toLowerCase().includes(q) ||
        (tz.region && tz.region.toLowerCase().includes(q))
    );
  }, [searchQuery]);

  const hasUnsavedChanges = selectedTz !== user.timezone;
  const hasUnsavedReminderChanges = selectedInterval !== initialReminderInterval;

  return (
    <div className="space-y-5 animate-fade-in pb-4">
      {/* View Title */}
      <div>
        <h2 className="text-lg font-bold tracking-tight">Налаштування</h2>
        <p className="text-xs text-muted mt-0.5">
          Керуйте своїм профілем, нагадуваннями та часовим поясом
        </p>
      </div>

      {/* Success Badge / Alert */}
      {savedSuccess && (
        <div className="flex items-center gap-2 p-3.5 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-600 dark:text-emerald-400 text-xs font-medium animate-in fade-in slide-in-from-top-1">
          <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-500" />
          <span>✅ Налаштування збережено! Часовий пояс оновлено.</span>
        </div>
      )}

      {/* Error Alert with Retry */}
      {error && (
        <div className="flex flex-col gap-2 p-3.5 rounded-2xl bg-red-500/10 border border-red-500/20 text-red-600 dark:text-red-400 text-xs">
          <div className="flex items-start gap-2">
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
            <div className="space-y-0.5">
              <span className="font-semibold">Помилка збереження</span>
              <p className="text-[11px] opacity-90">{error}</p>
            </div>
          </div>
          <button
            type="button"
            onClick={handleSave}
            className="self-end inline-flex items-center gap-1.5 px-3 py-1 rounded-lg bg-red-500 text-white text-[11px] font-medium hover:bg-red-600 active:scale-95 transition"
          >
            <RefreshCw className="w-3 h-3" />
            <span>Повторити спробу</span>
          </button>
        </div>
      )}

      {/* User Details Card */}
      <div className="p-4 rounded-2xl bg-secondary/80 border border-black/5 dark:border-white/5 backdrop-blur-md shadow-xs space-y-3">
        <div className="flex items-center justify-between pb-2 border-b border-black/5 dark:border-white/5">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-full bg-primary/10 text-primary flex items-center justify-center font-bold text-xs">
              <User className="w-4 h-4" />
            </div>
            <div>
              <p className="text-xs font-semibold">Профіль Telegram</p>
              <p className="text-[11px] text-muted font-mono">
                ID: {user.telegram_id}
              </p>
            </div>
          </div>
          <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-primary/10 text-primary">
            Активний
          </span>
        </div>

        <div className="grid grid-cols-2 gap-2 pt-1 text-xs">
          <div className="p-2.5 rounded-xl bg-background/60 border border-black/5 dark:border-white/5">
            <div className="flex items-center gap-1 text-[11px] text-muted mb-1">
              <Calendar className="w-3 h-3 text-primary" />
              <span>Створено</span>
            </div>
            <p className="font-medium text-[11px] truncate">
              {formatAccountCreation(user.created_at)}
            </p>
          </div>

          <div className="p-2.5 rounded-xl bg-background/60 border border-black/5 dark:border-white/5">
            <div className="flex items-center gap-1 text-[11px] text-muted mb-1">
              <Clock className="w-3 h-3 text-primary" />
              <span>Локальний час</span>
            </div>
            <p className="font-semibold text-[11px] text-primary truncate font-mono">
              {currentTime}
            </p>
          </div>
        </div>

        <div className="flex items-center justify-between p-2.5 rounded-xl bg-background/60 border border-black/5 dark:border-white/5 text-xs">
          <div className="flex items-center gap-1.5 text-muted">
            <Globe className="w-3.5 h-3.5 text-primary" />
            <span>Встановлений пояс:</span>
          </div>
          <code className="px-2 py-0.5 rounded-md bg-secondary text-foreground font-mono text-[11px] font-medium">
            {user.timezone}
          </code>
        </div>
      </div>

      {/* Periodic Telegram Reminders Card */}
      <div
        className="p-4 rounded-2xl bg-secondary/80 border border-black/5 dark:border-white/5 backdrop-blur-md shadow-xs space-y-3.5"
        aria-label="Нагадування в Telegram"
      >
        <div className="flex items-center justify-between gap-2 pb-2 border-b border-black/5 dark:border-white/5">
          <div className="flex items-center gap-2 min-w-0">
            <div className="w-8 h-8 rounded-full bg-primary/10 text-primary flex items-center justify-center shrink-0">
              {selectedInterval === null ? (
                <BellOff className="w-4 h-4" />
              ) : (
                <Bell className="w-4 h-4" />
              )}
            </div>
            <div className="min-w-0">
              <h3 className="text-sm font-semibold truncate">Нагадування в Telegram</h3>
              <p className="text-[11px] text-muted truncate">
                Періодичний список невиконаних завдань
              </p>
            </div>
          </div>
          <div className="flex items-center gap-1.5 shrink-0">
            {hasUnsavedReminderChanges && (
              <span className="text-[10px] font-medium text-amber-500 bg-amber-500/10 px-2 py-0.5 rounded-full">
                Змінено
              </span>
            )}
            <span
              className={`px-2.5 py-0.5 rounded-full text-[11px] font-semibold ${
                selectedInterval === null
                  ? 'bg-background/80 text-muted'
                  : 'bg-primary/15 text-primary'
              }`}
            >
              {formatReminderStatus(selectedInterval)}
            </span>
          </div>
        </div>

        {/* Reminders Success Banner */}
        {remindersSavedSuccess && (
          <div className="flex items-center gap-2 p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-600 dark:text-emerald-400 text-xs font-medium animate-in fade-in slide-in-from-top-1">
            <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-500" />
            <span>
              ✅ Інтервал нагадувань збережено ({formatReminderStatus(initialReminderInterval)}).
            </span>
          </div>
        )}

        {/* Reminders Error Banner with Retry */}
        {remindersError && (
          <div className="flex flex-col gap-2 p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-600 dark:text-red-400 text-xs">
            <div className="flex items-start gap-2">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <div className="space-y-0.5">
                <span className="font-semibold">Помилка збереження нагадувань</span>
                <p className="text-[11px] opacity-90">{remindersError}</p>
              </div>
            </div>
            <button
              type="button"
              onClick={handleSaveReminders}
              disabled={isSavingReminders}
              className="self-end inline-flex items-center gap-1.5 px-3 py-1 rounded-lg bg-red-500 text-white text-[11px] font-medium hover:bg-red-600 active:scale-95 transition cursor-pointer"
            >
              <RefreshCw className="w-3 h-3" />
              <span>Повторити спробу</span>
            </button>
          </div>
        )}

        {/* Quick-select Preset Pills */}
        <div className="space-y-1.5">
          <p className="text-[11px] font-medium text-muted">Швидкий вибір інтервалу</p>
          <div className="flex flex-wrap gap-1.5">
            {REMINDER_PRESETS.map((preset) => {
              const isActive = selectedInterval === preset.value;
              return (
                <button
                  key={preset.label}
                  type="button"
                  onClick={() => handleSelectInterval(preset.value)}
                  aria-pressed={isActive}
                  className={`px-3 py-1.5 rounded-xl text-xs font-medium transition-all cursor-pointer active:scale-95 ${
                    isActive
                      ? 'bg-primary text-primary-foreground shadow-xs shadow-primary/20'
                      : 'bg-background/70 text-foreground border border-black/5 dark:border-white/5 hover:bg-background'
                  }`}
                >
                  {preset.label}
                </button>
              );
            })}
          </div>
        </div>

        {/* Custom Hour Stepper & Numeric Selector (1..24) */}
        <div className="flex items-center justify-between gap-3 p-2.5 rounded-xl bg-background/60 border border-black/5 dark:border-white/5">
          <div className="min-w-0">
            <p className="text-xs font-medium">Власний інтервал</p>
            <p className="text-[10px] text-muted">Від 1 до 24 годин</p>
          </div>
          <div className="flex items-center gap-1.5 shrink-0">
            <button
              type="button"
              onClick={handleDecrementInterval}
              disabled={selectedInterval === null || selectedInterval <= 1}
              aria-label="Зменшити інтервал на 1 годину"
              className="w-8 h-8 rounded-lg flex items-center justify-center bg-secondary text-foreground border border-black/5 dark:border-white/5 transition hover:bg-secondary/80 active:scale-95 disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
            >
              <Minus className="w-3.5 h-3.5" />
            </button>

            <div className="flex items-center gap-1 px-2 py-1 rounded-lg bg-secondary/70 border border-black/5 dark:border-white/5">
              <input
                type="number"
                min={1}
                max={24}
                step={1}
                inputMode="numeric"
                aria-label="Інтервал у годинах"
                value={selectedInterval === null ? '' : selectedInterval}
                placeholder="—"
                onChange={(e) => handleCustomIntervalInput(e.target.value)}
                className="w-9 text-center text-xs font-semibold bg-transparent text-foreground focus:outline-none [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
              />
              <span className="text-[11px] text-muted">год</span>
            </div>

            <button
              type="button"
              onClick={handleIncrementInterval}
              disabled={selectedInterval !== null && selectedInterval >= 24}
              aria-label="Збільшити інтервал на 1 годину"
              className="w-8 h-8 rounded-lg flex items-center justify-center bg-secondary text-foreground border border-black/5 dark:border-white/5 transition hover:bg-secondary/80 active:scale-95 disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
            >
              <Plus className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {/* Informative Callout: Active Hours & Automatic Deadline Alerts */}
        <div className="flex items-start gap-2 p-3 rounded-xl bg-background/60 border border-black/5 dark:border-white/5 text-[11px] text-muted leading-relaxed">
          <Info className="w-4 h-4 shrink-0 text-primary mt-0.5" />
          <div className="space-y-1">
            <p>
              Періодичні нагадування надходять у Telegram-бот лише в активні години{' '}
              <span className="font-medium text-foreground">08:00–22:00</span> і
              автоматично пропускаються, якщо невиконаних завдань на сьогодні не залишилось.
            </p>
            <p>
              Термінові сповіщення про дедлайни (
              <span className="font-medium text-foreground">⏳ за 1 годину</span> та{' '}
              <span className="font-medium text-foreground">🚨 за 10 хвилин</span>)
              працюють автоматично для будь-якого завдання з вказаним часом дедлайну.
            </p>
          </div>
        </div>

        {/* Save Reminders Button */}
        <button
          type="button"
          onClick={handleSaveReminders}
          disabled={isSavingReminders || !hasUnsavedReminderChanges}
          className={`w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl font-semibold text-xs transition-all shadow-sm ${
            isSavingReminders || !hasUnsavedReminderChanges
              ? 'opacity-50 cursor-not-allowed bg-background/60 text-muted shadow-none'
              : 'bg-primary text-primary-foreground hover:opacity-90 active:scale-98 shadow-primary/20 cursor-pointer'
          }`}
        >
          {isSavingReminders ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              <span>Збереження...</span>
            </>
          ) : (
            <>
              <Save className="w-4 h-4" />
              <span>Зберегти нагадування</span>
            </>
          )}
        </button>
      </div>

      {/* Timezone Selection Section */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold flex items-center gap-1.5">
            <Globe className="w-4 h-4 text-primary" />
            <span>Вибір часового поясу</span>
          </h3>
          {hasUnsavedChanges && (
            <span className="text-[10px] font-medium text-amber-500 bg-amber-500/10 px-2 py-0.5 rounded-full">
              Змінено
            </span>
          )}
        </div>

        {/* Search input */}
        <div className="relative">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted pointer-events-none" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Пошук міста або поясу (Київ, Лондон, Варшава...)"
            className="w-full pl-9 pr-9 py-2 text-xs rounded-xl bg-secondary border border-black/5 dark:border-white/5 focus:outline-none focus:ring-1 focus:ring-primary text-foreground placeholder:text-muted transition"
          />
          {searchQuery && (
            <button
              type="button"
              onClick={() => setSearchQuery('')}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted hover:text-foreground p-0.5"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>

        {/* Curated list / dropdown */}
        <div className="max-h-60 overflow-y-auto rounded-2xl bg-secondary/80 border border-black/5 dark:border-white/5 divide-y divide-black/5 dark:divide-white/5 p-1 shadow-xs">
          {filteredTimezones.length === 0 ? (
            <div className="py-6 text-center text-xs text-muted">
              Часових поясів за запитом «{searchQuery}» не знайдено
            </div>
          ) : (
            filteredTimezones.map((tz) => {
              const isSelected = selectedTz === tz.value;
              const isCurrent = user.timezone === tz.value;

              return (
                <button
                  key={tz.value}
                  type="button"
                  onClick={() => handleSelectTimezone(tz.value)}
                  className={`w-full flex items-center justify-between p-2.5 rounded-xl text-left transition-all text-xs cursor-pointer ${
                    isSelected
                      ? 'bg-primary/10 text-primary font-medium'
                      : 'hover:bg-background/50 text-foreground'
                  }`}
                >
                  <div className="flex flex-col pr-2 min-w-0">
                    <span className="truncate">{tz.label}</span>
                    <span className="text-[10px] text-muted font-mono truncate">
                      {tz.value}
                    </span>
                  </div>

                  <div className="flex items-center gap-1.5 shrink-0">
                    {isCurrent && (
                      <span className="text-[9px] px-1.5 py-0.5 rounded bg-secondary text-muted font-medium">
                        Поточний
                      </span>
                    )}
                    {isSelected && (
                      <div className="w-5 h-5 rounded-full bg-primary text-primary-foreground flex items-center justify-center">
                        <Check className="w-3 h-3 stroke-[3]" />
                      </div>
                    )}
                  </div>
                </button>
              );
            })
          )}
        </div>
      </div>

      {/* Save Button */}
      <div className="pt-2">
        <button
          type="button"
          onClick={handleSave}
          disabled={isSaving || !hasUnsavedChanges}
          className={`w-full flex items-center justify-center gap-2 py-3 px-4 rounded-xl font-semibold text-xs transition-all shadow-md ${
            isSaving || !hasUnsavedChanges
              ? 'opacity-50 cursor-not-allowed bg-secondary text-muted shadow-none'
              : 'bg-primary text-primary-foreground hover:opacity-90 active:scale-98 shadow-primary/20 cursor-pointer'
          }`}
        >
          {isSaving ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              <span>Збереження...</span>
            </>
          ) : (
            <>
              <Save className="w-4 h-4" />
              <span>Зберегти налаштування</span>
            </>
          )}
        </button>
        {!hasUnsavedChanges && (
          <p className="text-[10px] text-muted text-center mt-1.5">
            Оберіть інший часовий пояс для активації збереження
          </p>
        )}
      </div>
    </div>
  );
};
