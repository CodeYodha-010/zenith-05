import { useEffect, useState, type FormEvent } from 'react';
import { X } from 'lucide-react';
import { useAuth, type AuthMode } from '../auth/AuthContext';

/**
 * BOX 00 — Operator registration. Sign in / sign up styled as a
 * Form Z-1 field set: mono labels, ruled inputs, stamp submit.
 */
export default function AuthModal() {
  const { authOpen, authMode, closeAuth, signIn, signUp } = useAuth();
  const [mode, setMode] = useState<AuthMode>(authMode);
  const [email, setEmail] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);

  // Reset whenever the modal opens (mode is seeded by openAuth).
  useEffect(() => {
    if (authOpen) {
      setMode(authMode);
      setEmail('');
      setUsername('');
      setPassword('');
      setErrors({});
      setBusy(false);
    }
  }, [authOpen, authMode]);

  // Close on Escape.
  useEffect(() => {
    if (!authOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') closeAuth();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [authOpen, closeAuth]);

  if (!authOpen) return null;

  const isSignup = mode === 'signup';

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setErrors({});
    const result = isSignup
      ? await signUp(email, username, password)
      : await signIn(email, password);
    if (!result.ok) {
      setErrors(result.errors ?? { detail: 'Something went wrong. Try again.' });
      setBusy(false);
    }
  };

  const field =
    'w-full bg-[#0a0906] border rounded-md px-4 py-3 text-sm text-[#f5f1e8] placeholder-white/25 focus:outline-none focus:border-[#e8a23a] transition-colors';

  return (
    <div
      className="fixed inset-0 z-[200] flex items-center justify-center p-5 bg-black/75 backdrop-blur-sm"
      onClick={closeAuth}
      role="dialog"
      aria-modal="true"
      aria-label={isSignup ? 'Create account' : 'Sign in'}
    >
      <div
        className="w-[min(440px,94vw)] rounded-lg border border-[#e8a23a]/30 bg-[#0d0b08] p-7 sm:p-9 shadow-[0_40px_120px_-20px_rgba(232,162,58,0.3)]"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between pb-5 rule-double">
          <div>
            <div className="flex items-center gap-2">
              <svg width="18" height="18" viewBox="0 0 256 256" fill="#e8a23a">
                <path d="M 128 0 L 256 256 L 192 256 L 128 96 L 64 256 L 0 256 Z" />
              </svg>
              <span className="font-display italic text-xl text-[#f5f1e8]">Zenith</span>
            </div>
            <p className="font-mono-j text-[9px] tracking-[0.3em] uppercase text-white/40 mt-1.5">
              Box 00 · Operator {isSignup ? 'registration' : 'sign-in'}
            </p>
          </div>
          <button onClick={closeAuth} className="text-white/40 hover:text-white transition-colors p-1" aria-label="Close">
            <X size={18} />
          </button>
        </div>

        <div className="flex gap-6 mt-5">
          {(['signin', 'signup'] as AuthMode[]).map((m) => (
            <button
              key={m}
              onClick={() => {
                setMode(m);
                setErrors({});
              }}
              className={`font-mono-j text-[11px] tracking-[0.2em] uppercase pb-2 border-b-2 transition-colors ${
                mode === m ? 'text-[#e8a23a] border-[#e8a23a]' : 'text-white/40 border-transparent hover:text-white/70'
              }`}
            >
              {m === 'signin' ? 'Sign in' : 'Create account'}
            </button>
          ))}
        </div>

        <form onSubmit={onSubmit} className="mt-6 flex flex-col gap-4" noValidate>
          <div>
            <label htmlFor="zenith-email" className="font-mono-j text-[10px] tracking-[0.25em] uppercase text-white/50">
              Email
            </label>
            <input
              id="zenith-email"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@company.com"
              className={`${field} mt-1.5 border-white/15`}
            />
            {errors.email && <p className="mt-1.5 text-xs text-red-300/90">{errors.email}</p>}
          </div>

          {isSignup && (
            <div>
              <label htmlFor="zenith-username" className="font-mono-j text-[10px] tracking-[0.25em] uppercase text-white/50">
                Operator name
              </label>
              <input
                id="zenith-username"
                type="text"
                autoComplete="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="exporter_handle"
                className={`${field} mt-1.5 border-white/15`}
              />
              {errors.username && <p className="mt-1.5 text-xs text-red-300/90">{errors.username}</p>}
            </div>
          )}

          <div>
            <label htmlFor="zenith-password" className="font-mono-j text-[10px] tracking-[0.25em] uppercase text-white/50">
              Passphrase
            </label>
            <input
              id="zenith-password"
              type="password"
              autoComplete={isSignup ? 'new-password' : 'current-password'}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="xxxxxxxxxxxx"
              className={`${field} mt-1.5 border-white/15`}
            />
            {errors.password && <p className="mt-1.5 text-xs text-red-300/90">{errors.password}</p>}
          </div>

          {errors.detail && <p className="text-xs text-red-300/90">{errors.detail}</p>}

          <button
            type="submit"
            disabled={busy}
            className="stamp mt-2 w-full text-[#e8a23a] hover:text-black hover:bg-[#e8a23a] hover:-rotate-1 text-xs font-medium py-3.5 transition-all duration-200 disabled:opacity-50 disabled:pointer-events-none"
          >
            {busy ? 'Filing…' : isSignup ? 'Register operator' : 'Sign in'}
          </button>

          <p className="font-mono-j text-[9px] tracking-[0.2em] uppercase text-white/30 text-center">
            Session secured by Django · HttpOnly cookie
          </p>
        </form>
      </div>
    </div>
  );
}
