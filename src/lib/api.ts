/** API client with optional Supabase bearer authentication. */
import { supabase } from './supabase';

export interface AuthUser {
  id: string | number;
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
  (import.meta.env.VITE_APP_URL as string | undefined) ?? 'http://localhost:8000';
export const CHAT_URL: string = APP_URL || '/';

function getCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}

async function getSupabaseToken(): Promise<string | null> {
  if (!supabase) return null;
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? null;
}

async function ensureCsrf(): Promise<string> {
  let token = getCookie('csrftoken');
  if (!token) {
    await fetch('/api/auth/csrf/', { credentials: 'include' });
    token = getCookie('csrftoken');
  }
  return token ?? '';
}

async function authHeaders(): Promise<Record<string, string>> {
  const token = await getSupabaseToken();
  const csrfToken = token ? getCookie('csrftoken') : await ensureCsrf();
  return {
    ...(csrfToken ? { 'X-CSRFToken': csrfToken } : {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

async function post<T = unknown>(path: string, body?: unknown): Promise<ApiResult<T>> {
  const headers = { 'Content-Type': 'application/json', ...(await authHeaders()) };
  const res = await fetch(path, {
    method: 'POST',
    credentials: 'include',
    headers,
    body: JSON.stringify(body ?? {}),
  });
  const data = (await res.json().catch(() => ({}))) as T;
  return { ok: res.ok, status: res.status, data };
}

async function get<T = unknown>(path: string): Promise<ApiResult<T>> {
  const res = await fetch(path, {
    credentials: 'include',
    headers: await authHeaders(),
  });
  const data = (await res.json().catch(() => ({}))) as T;
  return { ok: res.ok, status: res.status, data };
}

export interface FieldErrors {
  errors?: Record<string, string>;
}

// Legacy Django-auth helpers remain available for AUTH_MODE=django rollback.
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
