import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import { api, APP_URL, type AuthUser } from '../lib/api';

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

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [authOpen, setAuthOpen] = useState(false);
  const [authMode, setAuthMode] = useState<AuthMode>('signup');

  // Restore the session on load (page refreshes keep you signed in).
  useEffect(() => {
    let cancelled = false;
    api.me().then(({ data }) => {
      if (!cancelled) {
        setUser(data.user ?? null);
        setLoading(false);
      }
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const openAuth = useCallback((mode: AuthMode = 'signup') => {
    setAuthMode(mode);
    setAuthOpen(true);
  }, []);

  const closeAuth = useCallback(() => setAuthOpen(false), []);

  const signIn = useCallback(async (email: string, password: string): Promise<FormResult> => {
    const { ok, data } = await api.login(email, password);
    if (ok && data.user) {
      setUser(data.user);
      setAuthOpen(false);
      // Redirect to the chatbot — a full navigation so the session cookie
      // (scoped to localhost) is presented immediately at APP_URL.
      window.location.assign(APP_URL);
      return { ok: true };
    }
    return { ok: false, errors: (data as { errors?: Record<string, string> }).errors };
  }, []);

  const signUp = useCallback(
    async (email: string, username: string, password: string): Promise<FormResult> => {
      const { ok, data } = await api.register(email, username, password);
      if (ok && data.user) {
        setUser(data.user);
        setAuthOpen(false);
        window.location.assign(APP_URL);
        return { ok: true };
      }
      return { ok: false, errors: (data as { errors?: Record<string, string> }).errors };
    },
    []
  );

  const signOut = useCallback(async () => {
    await api.logout();
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({
      user,
      loading,
      authOpen,
      authMode,
      openAuth,
      closeAuth,
      signIn,
      signUp,
      signOut,
    }),
    [user, loading, authOpen, authMode, openAuth, closeAuth, signIn, signUp, signOut]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
}
