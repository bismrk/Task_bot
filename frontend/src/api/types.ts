/**
 * UserProfile interface matching backend UserRead schema.
 */
export interface UserProfile {
  telegram_id: number;
  timezone: string;
  created_at: string;
}

/**
 * Task lifecycle statuses matching backend TaskStatus enum.
 */
export type TaskStatus = 'todo' | 'done' | 'canceled';

/**
 * Task urgency/importance levels matching backend TaskPriority enum.
 */
export type TaskPriority = 'low' | 'medium' | 'high';

/**
 * Task representation matching backend TaskRead schema.
 */
export interface TaskRead {
  id: number;
  user_id: number;
  title: string;
  status: TaskStatus;
  priority: TaskPriority;
  tag: string | null;
  target_date: string;
  deadline_at: string | null;
  recurrence: string | null;
  reminder_sent_1h: boolean;
  reminder_sent_10m: boolean;
  created_at: string;
}

/**
 * Schema for creating a new task.
 */
export interface TaskCreate {
  title: string;
  target_date: string;
  deadline_at?: string | null;
  priority?: TaskPriority;
  tag?: string | null;
  recurrence?: string | null;
}

/**
 * Schema for updating an existing task.
 */
export interface TaskUpdate {
  title?: string;
  target_date?: string;
  deadline_at?: string | null;
  priority?: TaskPriority;
  tag?: string | null;
  status?: TaskStatus;
  recurrence?: string | null;
}

/**
 * Daily aggregation summary for calendar view matching backend CalendarDaySummary.
 */
export interface CalendarDaySummary {
  date: string;
  total_tasks: number;
  completed_tasks: number;
  status: 'all_done' | 'partial' | 'todo_only';
}

/**
 * Navigation tabs for the Mini App.
 */
export type AppTab = 'today' | 'calendar' | 'analytics' | 'settings';

/**
 * Daily productivity aggregation item for charts and trend tracking.
 */
export interface DailyTrendItem {
  date: string;
  completed_tasks: number;
  total_tasks: number;
  completion_rate: number;
}

/**
 * Category tag aggregation breakdown item.
 */
export interface TagBreakdownItem {
  tag: string;
  count: number;
  completed_count: number;
  percentage: number;
}

/**
 * Productivity analytics dashboard response matching backend AnalyticsResponse schema.
 */
export interface AnalyticsResponse {
  streak_current: number;
  streak_longest: number;
  total_tasks: number;
  completed_tasks: number;
  completion_rate: number;
  daily_trends: DailyTrendItem[];
  tag_breakdown: TagBreakdownItem[];
}

/**
 * Timezone option interface for settings dropdown/search selector.
 */
export interface TimezoneOption {
  label: string;
  value: string;
  region?: string;
}



