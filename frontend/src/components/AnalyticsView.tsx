import React, { useState, useEffect, useCallback, useMemo } from 'react';
import type { AnalyticsResponse } from '../api/types';
import { fetchAnalytics } from '../api/client';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from 'recharts';
import {
  ListTodo,
  CheckCircle2,
  TrendingUp,
  AlertCircle,
  RefreshCw,
  Award,
} from 'lucide-react';

interface TimeWindowOption {
  days: number;
  label: string;
}

const TIME_WINDOWS: TimeWindowOption[] = [
  { days: 7, label: '7 днів' },
  { days: 14, label: '14 днів' },
  { days: 30, label: '30 днів' },
];

export const AnalyticsView: React.FC = () => {
  const [days, setDays] = useState<number>(14);
  const [data, setData] = useState<AnalyticsResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const loadAnalytics = useCallback(async (selectedDays: number) => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetchAnalytics(selectedDays);
      setData(response);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : 'Не вдалося завантажити аналітику';
      setError(message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAnalytics(days);
  }, [days, loadAnalytics]);

  const handleWindowChange = (newDays: number) => {
    if (newDays === days) return;
    try {
      window.Telegram?.WebApp?.HapticFeedback?.impactOccurred('light');
    } catch {
      // ignore outside Telegram environment
    }
    setDays(newDays);
  };

  // Micro-copy for daily streak
  const streakInfo = useMemo(() => {
    if (!data) {
      return {
        microCopy: 'Почніть свій перший стрік сьогодні!',
        isActiveToday: false,
      };
    }
    const todayTrend =
      data.daily_trends.length > 0
        ? data.daily_trends[data.daily_trends.length - 1]
        : null;
    const todayCompleted = (todayTrend?.completed_tasks ?? 0) > 0;

    if (data.streak_current > 0 && todayCompleted) {
      return {
        microCopy: 'Днів поспіль! Продовжуйте в тому ж дусі!',
        isActiveToday: true,
      };
    }
    if (data.streak_current > 0 && !todayCompleted) {
      return {
        microCopy: 'Стрік тримається! Виконайте завдання сьогодні 🔥',
        isActiveToday: false,
      };
    }
    return {
      microCopy: 'Почніть свій перший стрік сьогодні!',
      isActiveToday: false,
    };
  }, [data]);

  // Formatted chart data
  const chartData = useMemo(() => {
    if (!data?.daily_trends) return [];
    return data.daily_trends.map((item) => {
      const parts = item.date.split('-');
      const shortDate =
        parts.length === 3 ? `${parts[2]}.${parts[1]}` : item.date;
      return {
        date: item.date,
        shortDate,
        completed: item.completed_tasks,
        total: item.total_tasks,
        rate: item.completion_rate,
      };
    });
  }, [data?.daily_trends]);

  return (
    <div className="space-y-5">
      {/* Time Window Selector */}
      <div className="flex items-center justify-center p-1 rounded-2xl bg-secondary/80 border border-black/5 dark:border-white/5 backdrop-blur-md shadow-xs">
        {TIME_WINDOWS.map((windowOption) => {
          const isSelected = days === windowOption.days;
          return (
            <button
              key={windowOption.days}
              type="button"
              onClick={() => handleWindowChange(windowOption.days)}
              className={`flex-1 py-1.5 px-3 rounded-xl text-xs font-semibold transition-all duration-200 cursor-pointer ${
                isSelected
                  ? 'bg-background text-primary shadow-xs font-bold'
                  : 'text-muted hover:text-foreground'
              }`}
            >
              {windowOption.label}
            </button>
          );
        })}
      </div>

      {/* Loading Skeleton */}
      {loading && (
        <div className="space-y-4 animate-pulse">
          {/* Streak skeleton */}
          <div className="h-32 rounded-3xl bg-secondary" />
          {/* Metrics skeleton */}
          <div className="grid grid-cols-3 gap-2.5">
            <div className="h-24 rounded-2xl bg-secondary" />
            <div className="h-24 rounded-2xl bg-secondary" />
            <div className="h-24 rounded-2xl bg-secondary" />
          </div>
          {/* Chart skeleton */}
          <div className="h-64 rounded-3xl bg-secondary" />
          {/* Tag breakdown skeleton */}
          <div className="h-36 rounded-3xl bg-secondary" />
        </div>
      )}

      {/* Error Banner with Retry */}
      {!loading && error && (
        <div className="p-5 rounded-2xl bg-secondary border border-red-500/30 flex flex-col items-center text-center space-y-3 my-4">
          <AlertCircle className="w-10 h-10 text-red-500" />
          <div className="space-y-1">
            <h3 className="font-semibold text-sm">Помилка завантаження</h3>
            <p className="text-xs text-muted max-w-xs">{error}</p>
          </div>
          <button
            type="button"
            onClick={() => loadAnalytics(days)}
            className="mt-2 inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-primary text-primary-foreground text-xs font-semibold hover:opacity-90 transition active:scale-95 cursor-pointer shadow-md shadow-primary/20"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Спробувати знову</span>
          </button>
        </div>
      )}

      {/* Analytics Dashboard Content */}
      {!loading && !error && data && (
        <div className="space-y-5">
          {/* Daily Streak Card */}
          <div className="relative overflow-hidden p-5 rounded-3xl bg-linear-to-br from-amber-500/10 via-secondary to-secondary border border-amber-500/20 shadow-xs">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3.5">
                <div className="flex items-center justify-center w-14 h-14 rounded-2xl bg-amber-500/15 border border-amber-500/30 shadow-inner">
                  <span className="text-3xl select-none" role="img" aria-label="flame">
                    🔥
                  </span>
                </div>
                <div>
                  <div className="flex items-baseline gap-1.5">
                    <span className="text-3xl font-extrabold tracking-tight">
                      {data.streak_current}
                    </span>
                    <span className="text-sm font-semibold text-muted">
                      {data.streak_current === 1 ? 'день' : 'днів'}
                    </span>
                  </div>
                  <p className="text-xs text-muted mt-0.5">{streakInfo.microCopy}</p>
                </div>
              </div>

              {/* Best streak badge */}
              <div className="flex flex-col items-end">
                <div className="flex items-center gap-1 px-2.5 py-1 rounded-full bg-amber-500/15 border border-amber-500/25 text-amber-600 dark:text-amber-400 text-[11px] font-semibold">
                  <Award className="w-3 h-3" />
                  <span>Рекорд: {data.streak_longest} дн.</span>
                </div>
              </div>
            </div>
          </div>

          {/* Metric Cards Grid */}
          <div className="grid grid-cols-3 gap-2.5">
            {/* Total Tasks Card */}
            <div className="p-3.5 rounded-2xl bg-secondary/80 border border-black/5 dark:border-white/5 flex flex-col justify-between space-y-2">
              <div className="flex items-center justify-between text-muted">
                <span className="text-[11px] font-medium truncate">Всього</span>
                <ListTodo className="w-3.5 h-3.5 text-muted shrink-0" />
              </div>
              <div>
                <span className="text-xl font-bold tracking-tight">
                  {data.total_tasks}
                </span>
                <p className="text-[10px] text-muted truncate mt-0.5">завдань</p>
              </div>
            </div>

            {/* Completed Tasks Card */}
            <div className="p-3.5 rounded-2xl bg-secondary/80 border border-black/5 dark:border-white/5 flex flex-col justify-between space-y-2">
              <div className="flex items-center justify-between text-muted">
                <span className="text-[11px] font-medium truncate">Виконано</span>
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500 shrink-0" />
              </div>
              <div>
                <span className="text-xl font-bold tracking-tight text-emerald-600 dark:text-emerald-400">
                  {data.completed_tasks}
                </span>
                <p className="text-[10px] text-muted truncate mt-0.5">закритих</p>
              </div>
            </div>

            {/* Completion Rate Card */}
            <div className="p-3.5 rounded-2xl bg-secondary/80 border border-black/5 dark:border-white/5 flex flex-col justify-between space-y-2">
              <div className="flex items-center justify-between text-muted">
                <span className="text-[11px] font-medium truncate">Успішність</span>
                <TrendingUp className="w-3.5 h-3.5 text-primary shrink-0" />
              </div>
              <div className="space-y-1.5">
                <span className="text-xl font-bold tracking-tight text-primary">
                  {data.completion_rate}%
                </span>
                <div className="w-full h-1.5 rounded-full bg-black/10 dark:bg-white/10 overflow-hidden">
                  <div
                    className="h-full rounded-full bg-primary transition-all duration-500"
                    style={{ width: `${Math.min(data.completion_rate, 100)}%` }}
                  />
                </div>
              </div>
            </div>
          </div>

          {/* Empty State when 0 tasks across the window */}
          {data.total_tasks === 0 ? (
            <div className="p-8 rounded-3xl bg-secondary/50 border border-black/5 dark:border-white/5 flex flex-col items-center text-center space-y-3">
              <div className="w-12 h-12 rounded-2xl bg-secondary flex items-center justify-center text-2xl select-none">
                📊
              </div>
              <div className="space-y-1">
                <h3 className="font-semibold text-sm">
                  Ще немає даних для аналітики
                </h3>
                <p className="text-xs text-muted max-w-xs">
                  За обраний період ({days} днів) немає запланованих завдань. Створіть завдання, щоб побачити графік та динаміку!
                </p>
              </div>
            </div>
          ) : (
            <>
              {/* Productivity Trend Chart */}
              <div className="p-4 rounded-3xl bg-secondary/70 border border-black/5 dark:border-white/5 space-y-3">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-xs font-semibold uppercase tracking-wider text-muted">
                      Динаміка продуктивності
                    </h3>
                    <p className="text-[11px] text-muted">
                      Кількість виконаних та загальних завдань
                    </p>
                  </div>
                  <div className="flex items-center gap-3 text-[10px] text-muted">
                    <span className="flex items-center gap-1">
                      <span className="w-2 h-2 rounded-full bg-primary" />
                      Виконано
                    </span>
                    <span className="flex items-center gap-1">
                      <span className="w-2 h-2 rounded-full bg-muted/40" />
                      Всього
                    </span>
                  </div>
                </div>

                <div className="w-full h-56 pt-2">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={chartData}
                      margin={{ top: 10, right: 6, left: -22, bottom: 0 }}
                      barGap={2}
                    >
                      <CartesianGrid
                        strokeDasharray="3 3"
                        vertical={false}
                        stroke="rgba(128, 128, 128, 0.15)"
                      />
                      <XAxis
                        dataKey="shortDate"
                        stroke="var(--tg-theme-hint-color, #71717a)"
                        fontSize={10}
                        tickLine={false}
                        axisLine={false}
                      />
                      <YAxis
                        allowDecimals={false}
                        stroke="var(--tg-theme-hint-color, #71717a)"
                        fontSize={10}
                        tickLine={false}
                        axisLine={false}
                      />
                      <Tooltip
                        contentStyle={{
                          backgroundColor:
                            'var(--tg-theme-secondary-bg-color, #f4f4f5)',
                          borderColor: 'rgba(128, 128, 128, 0.2)',
                          borderRadius: '12px',
                          color: 'var(--tg-theme-text-color, #000000)',
                          fontSize: '11px',
                          boxShadow: '0 4px 14px rgba(0, 0, 0, 0.1)',
                        }}
                        labelFormatter={(label) => `Дата: ${label}`}
                        formatter={(val: any, name: any) => {
                          const n = Number(val) || 0;
                          if (name === 'completed') return [n, 'Виконано'];
                          if (name === 'total') return [n, 'Всього'];
                          return [n, String(name ?? '')];
                        }}
                      />
                      <Bar
                        dataKey="total"
                        name="total"
                        fill="var(--tg-theme-hint-color, #71717a)"
                        opacity={0.35}
                        radius={[4, 4, 0, 0]}
                      />
                      <Bar
                        dataKey="completed"
                        name="completed"
                        fill="var(--tg-theme-button-color, #2481cc)"
                        radius={[4, 4, 0, 0]}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Tag Breakdown Section */}
              {data.tag_breakdown.length > 0 && (
                <div className="p-4 rounded-3xl bg-secondary/70 border border-black/5 dark:border-white/5 space-y-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="text-xs font-semibold uppercase tracking-wider text-muted">
                        Розподіл за категоріями
                      </h3>
                      <p className="text-[11px] text-muted">
                        Частка та завершеність завдань по тегах
                      </p>
                    </div>
                    <span className="text-[11px] text-muted font-medium">
                      {data.tag_breakdown.length}{' '}
                      {data.tag_breakdown.length === 1 ? 'тег' : 'тегів'}
                    </span>
                  </div>

                  <div className="space-y-2 pt-1">
                    {data.tag_breakdown.map((item) => {
                      const isUntagged = item.tag === 'Без тегу';
                      return (
                        <div
                          key={item.tag}
                          className="p-3 rounded-2xl bg-background/60 border border-black/5 dark:border-white/5 space-y-1.5"
                        >
                          <div className="flex items-center justify-between text-xs">
                            <span className="font-semibold">
                              {isUntagged ? (
                                <span className="px-2 py-0.5 rounded-md bg-secondary text-muted text-[11px] font-normal">
                                  Без тегу
                                </span>
                              ) : (
                                <span className="text-primary font-medium">
                                  #{item.tag}
                                </span>
                              )}
                            </span>
                            <div className="flex items-center gap-2 text-muted text-[11px]">
                              <span>
                                {item.completed_count} з {item.count} викон.
                              </span>
                              <span className="font-bold text-foreground">
                                {item.percentage}%
                              </span>
                            </div>
                          </div>
                          <div className="w-full h-2 rounded-full bg-black/10 dark:bg-white/10 overflow-hidden">
                            <div
                              className="h-full rounded-full bg-primary transition-all duration-500"
                              style={{
                                width: `${Math.min(item.percentage, 100)}%`,
                              }}
                            />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
};
