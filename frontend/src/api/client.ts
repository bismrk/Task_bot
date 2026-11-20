import type { UserProfile } from './types';

declare global {
  interface Window {
    Telegram?: {
      WebApp?: {
        initData?: string;
        initDataUnsafe?: {
          user?: {
            id: number;
            first_name?: string;
            last_name?: string;
            username?: string;
            language_code?: string;
          };
          [key: string]: unknown;
        };
        colorScheme?: 'light' | 'dark';
        themeParams?: Record<string, string>;
        isExpanded?: boolean;
        ready: () => void;
        expand: () => void;
        close: () => void;
        onEvent?: (eventType: string, eventHandler: () => void) => void;
        offEvent?: (eventType: string, eventHandler: () => void) => void;
        [key: string]: unknown;
      };
    };
  }
}

/**
 * Extracts raw Telegram initData or falls back to mock/dev credentials.
 */
export function getInitData(): string {
  // 1. Try window.Telegram?.WebApp?.initData
  if (typeof window !== 'undefined' && window.Telegram?.WebApp?.initData) {
    const raw = window.Telegram.WebApp.initData.trim();
    if (raw.length > 0) {
      return raw;
    }
  }

  // 2. Try environment variable fallback for local browser development
  const envInitData = import.meta.env.VITE_DEV_INIT_DATA as string | undefined;
  if (envInitData && envInitData.trim().length > 0) {
    return envInitData.trim();
  }

  // 3. Fallback mock credentials for browser development outside Telegram
  return 'query_id=mock_query_id&user=%7B%22id%22%3A123456789%2C%22first_name%22%3A%22DevUser%22%2C%22username%22%3A%22devuser%22%7D&auth_date=1700000000&hash=mock_dev_hash';
}

/**
 * Centralized API request helper attaching Authorization: tma <raw_init_data>.
 */
export async function apiRequest<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const initData = getInitData();
  const headers = new Headers(options.headers || {});

  if (initData) {
    headers.set('Authorization', `tma ${initData}`);
  }

  if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }

  const response = await fetch(endpoint, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const data = await response.json();
      if (data && typeof data === 'object' && 'detail' in data) {
        detail = String(data.detail);
      }
    } catch {
      // ignore JSON parse errors
    }
    throw new Error(`API Error ${response.status}: ${detail}`);
  }

  return (await response.json()) as T;
}

/**
 * Fetch the authenticated user's profile from GET /api/me.
 */
export async function fetchCurrentUser(): Promise<UserProfile> {
  return apiRequest<UserProfile>('/api/me');
}
