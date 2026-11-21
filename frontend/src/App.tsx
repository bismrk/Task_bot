import { useEffect, useState, useCallback } from 'react';
import { fetchCurrentUser, fetchTasks } from './api/client';
import type { TaskRead, UserProfile } from './api/types';
import { TodayChecklist } from './components/TodayChecklist';
import {
  User,
  Clock,
  Sparkles,
  Loader2,
  AlertCircle,
  RefreshCw,
} from 'lucide-react';

export default function App() {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [tasks, setTasks] = useState<TaskRead[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Initialize Telegram WebApp viewport and theme
  const updateTheme = useCallback(() => {
    if (typeof window !== 'undefined') {
      try {
        window.Telegram?.WebApp?.ready?.();
        window.Telegram?.WebApp?.expand?.();
      } catch {
        // ignore outside Telegram environment
      }

      let isDark = false;
      if (window.Telegram?.WebApp?.colorScheme) {
        isDark = window.Telegram.WebApp.colorScheme === 'dark';
      } else if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
        isDark = true;
      }

      if (isDark) {
        document.documentElement.classList.add('dark');
      } else {
        document.documentElement.classList.remove('dark');
      }
    }
  }, []);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [userData, tasksData] = await Promise.all([
        fetchCurrentUser(),
        fetchTasks(),
      ]);
      setUser(userData);
      setTasks(tasksData);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Не вдалося завантажити дані';
      setError(message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    updateTheme();
    loadData();

    // Listen to theme changes from Telegram WebApp
    const handleThemeChange = () => updateTheme();
    if (typeof window !== 'undefined' && window.Telegram?.WebApp?.onEvent) {
      window.Telegram.WebApp.onEvent('themeChanged', handleThemeChange);
      return () => {
        window.Telegram?.WebApp?.offEvent?.('themeChanged', handleThemeChange);
      };
    }
  }, [updateTheme, loadData]);

  const telegramUser =
    typeof window !== 'undefined' ? window.Telegram?.WebApp?.initDataUnsafe?.user : undefined;
  const usernameDisplay = telegramUser?.username
    ? `@${telegramUser.username}`
    : telegramUser?.first_name || (user ? `ID: ${user.telegram_id}` : null);

  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col justify-between p-4 sm:p-6 max-w-lg mx-auto">
      {/* App Header */}
      <header className="flex items-center justify-between pb-4 border-b border-secondary">
        <div>
          <h1 className="text-xl font-bold tracking-tight">Daily Tasks</h1>
          <p className="text-xs text-muted mt-0.5">
            {usernameDisplay ? `Привіт, ${usernameDisplay}` : 'Ваш персональний трекер завдань'}
          </p>
        </div>
        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-secondary text-xs font-medium">
          <Sparkles className="w-3.5 h-3.5 text-primary" />
          <span>Mini App</span>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 py-4">
        {/* Loading Skeleton / Indicator */}
        {loading && (
          <div className="space-y-4 py-8">
            <div className="flex flex-col items-center justify-center py-6 space-y-3">
              <Loader2 className="w-8 h-8 animate-spin text-primary" />
              <p className="text-sm text-muted">Завантаження завдань...</p>
            </div>
            {/* Skeleton items */}
            <div className="space-y-2.5 animate-pulse opacity-60">
              <div className="h-16 rounded-2xl bg-secondary" />
              <div className="h-16 rounded-2xl bg-secondary" />
              <div className="h-16 rounded-2xl bg-secondary" />
            </div>
          </div>
        )}

        {/* Error Banner with Retry Action */}
        {!loading && error && (
          <div className="p-5 rounded-2xl bg-secondary border border-red-500/30 flex flex-col items-center text-center space-y-3 my-6">
            <AlertCircle className="w-10 h-10 text-red-500" />
            <div className="space-y-1">
              <h3 className="font-semibold text-sm">Помилка завантаження</h3>
              <p className="text-xs text-muted max-w-xs">{error}</p>
            </div>
            <button
              type="button"
              onClick={loadData}
              className="mt-2 inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-primary text-primary-foreground text-xs font-semibold hover:opacity-90 transition active:scale-95 cursor-pointer shadow-md shadow-primary/20"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              <span>Повторити спробу</span>
            </button>
          </div>
        )}

        {/* Today Checklist Primary View */}
        {!loading && !error && (
          <div className="space-y-5">
            {/* User Info Micro-bar */}
            {user && (
              <div className="flex items-center justify-between text-xs text-muted px-1">
                <div className="flex items-center gap-1.5">
                  <User className="w-3.5 h-3.5" />
                  <span>Користувач: {user.telegram_id}</span>
                </div>
                <div className="flex items-center gap-1">
                  <Clock className="w-3 h-3" />
                  <span>{user.timezone}</span>
                </div>
              </div>
            )}

            {/* Checklist Component */}
            <TodayChecklist
              initialTasks={tasks}
              onTasksChanged={(updated) => setTasks(updated)}
            />
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="pt-4 border-t border-secondary text-center">
        <p className="text-[11px] text-muted">
          Telegram Task Tracker &bull; Telegram Mini App
        </p>
      </footer>
    </div>
  );
}
