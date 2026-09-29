import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import type { User as SupabaseUser } from '@supabase/supabase-js';
import { api, CHAT_URL, type AuthUser } from '../lib/api';
import { supabase } from '../lib/supabase';

export type AuthMode = 'signin' | 'signup';

export interface FormResult {
  ok: boolean;
  errors?: Record<string, string>;
}

interface AuthContextValue {
  user: AuthUser | null;
  loading: boolean;
  authOpen: boolean;
  authMode: AuthMode;
  openAuth: (mode?: AuthMode) => void;
  closeAuth: () => void;
  signIn: (email: string, password: string) => Promise<FormResult>;
  signUp: (email: string, username: string, password: string) => Promise<FormResult>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function mapSupabaseUser(user: SupabaseUser): AuthUser {
  const metadata = user.user_metadata as { username?: string } | undefined;
  return {
    id: user.id,
    username: metadata?.username || user.email || user.id,
    email: user.email || '',
    date_joined: null,
  };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [authOpen, setAuthOpen] = useState(false);
  const [authMode, setAuthMode] = useState<AuthMode>('signup');

  useEffect(() => {
    let active = true;

    if (!supabase) {
      api.me().then(({ data }) => {
        if (active) {
          setUser(data.user ?? null);
          setLoading(false);
        }
      });
      return () => {
        active = false;
      };
    }

    supabase.auth.getSession().then(({ data }) => {
      if (!active) return;
      setUser(data.session?.user ? mapSupabaseUser(data.session.user) : null);
      setLoading(false);
    });

    const { data: listener } = supabase.auth.onAuthStateChange((_event, session) => {
      if (!active) return;
      setUser(session?.user ? mapSupabaseUser(session.user) : null);
      setLoading(false);
    });

    return () => {
      active = false;
      listener.subscription.unsubscribe();
    };
  }, []);

  const openAuth = useCallback((mode: AuthMode = 'signup') => {
    setAuthMode(mode);
    setAuthOpen(true);
  }, []);

  const closeAuth = useCallback(() => setAuthOpen(false), []);

  const signIn = useCallback(async (email: string, password: string): Promise<FormResult> => {
    if (!supabase) {
      const { ok, data } = await api.login(email, password);
      if (ok && data.user) {
        setUser(data.user);
        setAuthOpen(false);
        window.location.assign(CHAT_URL);
        return { ok: true };
      }
      return { ok: false, errors: data.errors ?? { detail: 'Unable to sign in.' } };
    }

    const { data, error } = await supabase.auth.signInWithPassword({ email, password });
    if (error || !data.user) {
      return { ok: false, errors: { detail: error?.message || 'Unable to sign in.' } };
    }

    setUser(mapSupabaseUser(data.user));
    setAuthOpen(false);
    window.location.assign(CHAT_URL);
    return { ok: true };
  }, []);

  const signUp = useCallback(
    async (email: string, username: string, password: string): Promise<FormResult> => {
      if (!supabase) {
        const { ok, data } = await api.register(email, username, password);
        if (ok && data.user) {
          setUser(data.user);
          setAuthOpen(false);
          window.location.assign(CHAT_URL);
          return { ok: true };
        }
        return { ok: false, errors: data.errors ?? { detail: 'Unable to register.' } };
      }

      const { data, error } = await supabase.auth.signUp({
        email,
        password,
        options: { data: { username } },
      });
      if (error || !data.user) {
        return { ok: false, errors: { detail: error?.message || 'Unable to register.' } };
      }
      if (!data.session) {
        return { ok: false, errors: { detail: 'Check your email to confirm your account.' } };
      }

      setUser(mapSupabaseUser(data.user));
      setAuthOpen(false);
      window.location.assign(CHAT_URL);
      return { ok: true };
    },
    [],
  );

  const signOut = useCallback(async () => {
    if (supabase) await supabase.auth.signOut();
    else await api.logout();
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({ user, loading, authOpen, authMode, openAuth, closeAuth, signIn, signUp, signOut }),
    [user, loading, authOpen, authMode, openAuth, closeAuth, signIn, signUp, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
}
