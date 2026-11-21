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
