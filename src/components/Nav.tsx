import { useEffect, useState } from 'react';
import { Menu, LogOut } from 'lucide-react';
import { useAuth } from '../auth/AuthContext';
import { APP_URL } from '../lib/api';

const LINKS = [
  { n: '01', label: 'The Shift', href: '#shift' },
  { n: '02', label: 'Pipeline', href: '#pipeline' },
  { n: '03', label: 'Coverage', href: '#coverage' },
];

/** Document header bar: the masthead of a customs form, not a glass pill. */
export default function Nav() {
  const [scrolled, setScrolled] = useState(false);
  const { user, openAuth, signOut } = useAuth();

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 40);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  return (
    <nav
      className={`fixed top-0 left-0 right-0 z-[100] flex items-center justify-between px-4 sm:px-6 py-3 transition-all duration-500 ${
        scrolled ? 'bg-[#0b0a08]/95 border-b border-white/10' : ''
      }`}
    >
      {/* Masthead */}
      <a href="#top" className="flex items-center gap-2.5">
        <svg width="24" height="24" viewBox="0 0 256 256" fill="#e8a23a" xmlns="http://www.w3.org/2000/svg">
          <path d="M 128 0 L 256 256 L 192 256 L 128 96 L 64 256 L 0 256 Z" />
        </svg>
        <span className="leading-none">
          <span className="block text-white text-xl font-display italic">Zenith</span>
          <span className="block font-mono-j text-[8px] tracking-[0.3em] uppercase text-white/40 mt-0.5">
            Clearance assistant · Form Z-1
          </span>
        </span>
      </a>

      {/* Form-field references */}
      <div className="hidden md:flex items-center gap-8">
        {LINKS.map((l) => (
          <a key={l.href} href={l.href} className="group relative flex items-baseline gap-1.5 py-1">
            <span className="font-mono-j text-[9px] text-[#e8a23a]/70">{l.n}</span>
            <span className="text-sm font-medium text-white/75 group-hover:text-white transition-colors">{l.label}</span>
            <span className="absolute left-0 -bottom-0.5 h-px w-0 bg-[#e8a23a] transition-all duration-300 group-hover:w-full" />
          </a>
        ))}
      </div>

      {/* Operator state */}
      <div className="flex items-center gap-3">
        {user ? (
          <>
            <span className="hidden sm:inline-flex items-center gap-2 font-mono-j text-[10px] tracking-[0.15em] uppercase text-[#e8a23a] border border-[#e8a23a]/30 rounded-full px-3.5 py-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-[#e8a23a] animate-pulse" />
              Operator: {user.username}
            </span>
            <a
              href={APP_URL}
              target="_blank"
              rel="noreferrer"
              className="stamp text-[#e8a23a] hover:text-black hover:bg-[#e8a23a] hover:-rotate-2 text-xs font-medium px-5 py-2.5 transition-all duration-200"
            >
              Launch App
            </a>
            <button
              onClick={() => void signOut()}
              className="text-white/40 hover:text-white transition-colors p-2"
              aria-label="Sign out"
              title="Sign out"
            >
              <LogOut size={16} />
            </button>
          </>
        ) : (
          <>
            <a
              href="#cta"
              className="hidden md:block text-sm font-medium text-white/75 hover:text-white transition-colors px-2"
            >
              Ask Zenith
            </a>
            <button
              onClick={() => openAuth('signup')}
              className="stamp text-[#e8a23a] hover:text-black hover:bg-[#e8a23a] hover:-rotate-2 text-xs font-medium px-5 py-2.5 transition-all duration-200"
            >
              Sign in
            </button>
          </>
        )}
        <button className="md:hidden text-white p-2" aria-label="Open menu">
          <Menu size={22} />
        </button>
      </div>
    </nav>
  );
}
