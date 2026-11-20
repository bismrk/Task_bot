import { useEffect, useState, useCallback } from 'react';
import { fetchCurrentUser } from './api/client';
import type { UserProfile } from './api/types';
import {
  User,
  Clock,
  Moon,
  Sun,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  Loader2,
  Sparkles,
} from 'lucide-react';

export default function App() {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [themeMode, setThemeMode] = useState<'Dark' | 'Light'>('Light');

  // Detect and apply Telegram or system theme
  const updateTheme = useCallback(() => {
    let detectedTheme: 'Dark' | 'Light' = 'Light';
    if (typeof window !== 'undefined') {
      if (window.Telegram?.WebApp?.colorScheme) {
        detectedTheme = window.Telegram.WebApp.colorScheme === 'dark' ? 'Dark' : 'Light';
      } else if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
        detectedTheme = 'Dark';
      }
    }
    setThemeMode(detectedTheme);
    if (detectedTheme === 'Dark') {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, []);

  const loadUser = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchCurrentUser();
      setUser(data);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to connect to backend';
      setError(message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    updateTheme();
    loadUser();

    // Listen to theme changes from Telegram WebApp
    const handleThemeChange = () => updateTheme();
    if (typeof window !== 'undefined' && window.Telegram?.WebApp?.onEvent) {
      window.Telegram.WebApp.onEvent('themeChanged', handleThemeChange);
      return () => {
        window.Telegram?.WebApp?.offEvent?.('themeChanged', handleThemeChange);
      };
    }
  }, [updateTheme, loadUser]);

  const telegramUser = typeof window !== 'undefined' ? window.Telegram?.WebApp?.initDataUnsafe?.user : undefined;
  const usernameDisplay = telegramUser?.username ? `@${telegramUser.username}` : null;

  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col justify-between p-4 sm:p-6 max-w-lg mx-auto">
      {/* Header */}
      <header className="flex items-center justify-between pb-4 border-b border-secondary">
        <div>
          <h1 className="text-xl font-bold tracking-tight">Telegram Task Tracker</h1>
          <p className="text-xs text-muted mt-0.5">Focus on what matters today</p>
        </div>
        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-secondary text-xs font-medium">
          <Sparkles className="w-3.5 h-3.5 text-primary" />
          <span>Mini App</span>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col justify-center py-6">
        {loading && (
          <div className="flex flex-col items-center justify-center py-12 space-y-4">
            <Loader2 className="w-8 h-8 animate-spin text-primary" />
            <p className="text-sm text-muted">Loading user profile...</p>
          </div>
        )}

        {!loading && error && (
          <div className="p-4 rounded-xl bg-secondary border border-red-500/30 flex flex-col items-center text-center space-y-3">
            <AlertCircle className="w-10 h-10 text-red-500" />
            <div className="space-y-1">
              <h3 className="font-semibold text-sm">Connection Error</h3>
              <p className="text-xs text-muted max-w-xs">{error}</p>
            </div>
            <button
              onClick={loadUser}
              className="mt-2 inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-primary text-primary-foreground text-xs font-semibold hover:opacity-90 transition active:scale-95"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              <span>Retry</span>
            </button>
          </div>
        )}

        {!loading && !error && user && (
          <div className="space-y-4">
            {/* User Identifier Card */}
            <div className="p-4 rounded-2xl bg-secondary border border-black/5 dark:border-white/5 space-y-3">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-primary/10 text-primary flex items-center justify-center font-bold">
                  <User className="w-5 h-5" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-xs text-muted">Telegram User</p>
                  <p className="text-base font-semibold truncate">
                    {usernameDisplay ? `${usernameDisplay} (${user.telegram_id})` : `ID: ${user.telegram_id}`}
                  </p>
                </div>
              </div>
              <div className="pt-2 border-t border-black/5 dark:border-white/5 flex items-center justify-between text-xs text-muted">
                <span>Account Created</span>
                <span>{new Date(user.created_at).toLocaleDateString()}</span>
              </div>
            </div>

            {/* Badges Grid */}
            <div className="grid grid-cols-3 gap-2">
              {/* Timezone Badge */}
              <div className="p-3 rounded-xl bg-secondary flex flex-col items-center justify-center text-center">
                <Clock className="w-4 h-4 text-primary mb-1" />
                <span className="text-[10px] text-muted uppercase tracking-wider">Timezone</span>
                <span className="text-xs font-medium truncate w-full mt-0.5" title={user.timezone}>
                  {user.timezone}
                </span>
              </div>

              {/* Theme Mode Indicator Badge */}
              <div className="p-3 rounded-xl bg-secondary flex flex-col items-center justify-center text-center">
                {themeMode === 'Dark' ? (
                  <Moon className="w-4 h-4 text-indigo-400 mb-1" />
                ) : (
                  <Sun className="w-4 h-4 text-amber-500 mb-1" />
                )}
                <span className="text-[10px] text-muted uppercase tracking-wider">Theme</span>
                <span className="text-xs font-medium mt-0.5">{themeMode}</span>
              </div>

              {/* Connection Status Indicator Badge */}
              <div className="p-3 rounded-xl bg-secondary flex flex-col items-center justify-center text-center">
                <div className="flex items-center gap-1 mb-1">
                  <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                  <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                </div>
                <span className="text-[10px] text-muted uppercase tracking-wider">Status</span>
                <span className="text-xs font-medium text-emerald-600 dark:text-emerald-400 mt-0.5">
                  Connected
                </span>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="pt-4 border-t border-secondary text-center">
        <p className="text-[11px] text-muted">
          Telegram Mini App ready &bull; Daily task tracker
        </p>
      </footer>
    </div>
  );
}
