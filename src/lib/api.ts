/**
 * Minimal API client for the Django session-auth backend.
 * In dev, Vite proxies /api -> http://127.0.0.1:8000 so cookies
 * flow same-origin. In prod, serve this build from Django itself.
 */

export interface AuthUser {
  id: number;
  username: string;
  email: string;
  date_joined: string | null;
}

export interface ApiResult<T = unknown> {
  ok: boolean;
  status: number;
  data: T;
}

export const APP_URL: string =
  (import.meta.env.VITE_APP_URL as string | undefined) || 'http://localhost:8000';

function getCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp('(?:^|; )' + name + '=([^;]*)'));
  return match ? decodeURIComponent(match[1]) : null;
}

/** Read the csrftoken cookie, requesting one first if absent. */
async function ensureCsrf(): Promise<string> {
  let token = getCookie('csrftoken');
  if (!token) {
    await fetch('/api/auth/csrf/', { credentials: 'include' });
    token = getCookie('csrftoken');
  }
  return token ?? '';
}

async function post<T = unknown>(path: string, body?: unknown): Promise<ApiResult<T>> {
  const csrfToken = await ensureCsrf();
  const res = await fetch(path, {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': csrfToken,
    },
    body: JSON.stringify(body ?? {}),
  });
  const data = (await res.json().catch(() => ({}))) as T;
  return { ok: res.ok, status: res.status, data };
}

async function get<T = unknown>(path: string): Promise<ApiResult<T>> {
  const res = await fetch(path, { credentials: 'include' });
  const data = (await res.json().catch(() => ({}))) as T;
  return { ok: res.ok, status: res.status, data };
}

export interface FieldErrors {
  errors?: Record<string, string>;
}

export const api = {
  me: () => get<{ user: AuthUser | null }>('/api/auth/me/'),
  register: (email: string, username: string, password: string) =>
    post<{ success?: boolean; user?: AuthUser } & FieldErrors>('/api/auth/register/', {
      email,
      username,
      password,
    }),
  login: (email: string, password: string) =>
    post<{ success?: boolean; user?: AuthUser } & FieldErrors>('/api/auth/login/', {
      email,
      password,
    }),
  logout: () => post<{ success?: boolean }>('/api/auth/logout/'),
};
