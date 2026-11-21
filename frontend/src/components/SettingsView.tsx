import React, { useState, useEffect, useMemo, useCallback } from 'react';
import type { TimezoneOption, UserProfile } from '../api/types';
import { updateTimezone } from '../api/client';
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

export const SettingsView: React.FC<SettingsViewProps> = ({
  user,
  onUserUpdated,
}) => {
  const [selectedTz, setSelectedTz] = useState<string>(user.timezone);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [savedSuccess, setSavedSuccess] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [currentTime, setCurrentTime] = useState<string>(() =>
    formatLocalTime(user.timezone)
  );

  // Synchronize internal selected timezone when external user prop updates
  useEffect(() => {
    setSelectedTz(user.timezone);
  }, [user.timezone]);

  // Live clock tick in user's current timezone
  useEffect(() => {
    const interval = setInterval(() => {
      setCurrentTime(formatLocalTime(user.timezone));
    }, 1000);
    return () => clearInterval(interval);
  }, [user.timezone]);

  // Reset success message when user chooses a different timezone
  const handleSelectTimezone = (tz: string) => {
    setSelectedTz(tz);
    setSavedSuccess(false);
    setError(null);
    try {
      window.Telegram?.WebApp?.HapticFeedback?.impactOccurred?.('light');
    } catch {
      // ignore outside Telegram environment
    }
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

  return (
    <div className="space-y-5 animate-fade-in pb-4">
      {/* View Title */}
      <div>
        <h2 className="text-lg font-bold tracking-tight">Налаштування</h2>
        <p className="text-xs text-muted mt-0.5">
          Керуйте своїм профілем та часовим поясом
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
