import Reveal from './Reveal';
import { useAuth } from '../auth/AuthContext';
import { APP_URL } from '../lib/api';

/**
 * BOX 05 — Final clearance. Ledger ruling replaces the glow orb;
 * the CTA is the stamp.
 */
export default function Closing() {
  const { user, openAuth } = useAuth();
  return (
    <>
      <section id="cta" className="relative bg-[#050505] ledger-lines py-32 sm:py-44 overflow-hidden">
        <div className="relative max-w-4xl mx-auto px-5 text-center">
          <Reveal>
            <p className="eyebrow">Box 05 · Final clearance</p>
            <h2
              className="mt-6 font-display italic text-5xl sm:text-7xl md:text-8xl leading-[0.95] text-[#f5f1e8]"
              style={{ letterSpacing: '-0.05em' }}
            >
              Stop digging.
            </h2>
            <h2
              className="text-5xl sm:text-7xl md:text-8xl leading-[0.95] text-gold-grad"
              style={{ letterSpacing: '-0.08em' }}
            >
              Start shipping.
            </h2>
          </Reveal>

          <Reveal delay={150}>
            <p className="mt-8 text-white/65 text-sm sm:text-base max-w-lg mx-auto leading-relaxed">
              Zenith answers in seconds what used to take an afternoon inside a 610-page handbook.
            </p>
            {user ? (
              <a
                href={APP_URL}
                target="_blank"
                rel="noreferrer"
                className="inline-block mt-10 stamp text-[#e8a23a] hover:text-black hover:bg-[#e8a23a] hover:-rotate-2 text-sm font-medium px-10 py-4 transition-all duration-200"
              >
                Launch Zenith
              </a>
            ) : (
              <button
                onClick={() => openAuth('signup')}
                className="inline-block mt-10 stamp text-[#e8a23a] hover:text-black hover:bg-[#e8a23a] hover:-rotate-2 text-sm font-medium px-10 py-4 transition-all duration-200"
              >
                Ask Zenith · Free
              </button>
            )}
            <p className="font-mono-j text-[10px] tracking-[0.25em] uppercase text-white/35 mt-6">
              No card · no setup · just ask
            </p>
          </Reveal>
        </div>
      </section>

      <footer className="bg-[#050505] border-t border-white/10 py-10">
        <div className="max-w-6xl mx-auto px-5 flex flex-col sm:flex-row items-center justify-between gap-6">
          <div className="flex items-center gap-2">
            <svg width="20" height="20" viewBox="0 0 256 256" fill="#e8a23a">
              <path d="M 128 0 L 256 256 L 192 256 L 128 96 L 64 256 L 0 256 Z" />
            </svg>
            <span className="font-display italic text-lg text-[#f5f1e8]">Zenith</span>
          </div>

          <p className="font-mono-j text-[10px] tracking-[0.2em] uppercase text-white/35 text-center">
            © 2026 Zenith · AI trade compliance · answers are guidance, not legal advice
          </p>

          <p className="font-mono-j text-[10px] tracking-[0.15em] uppercase text-white/35">
            Django · FAISS · RRF · Tavily · OpenRouter
          </p>
        </div>
      </footer>
    </>
  );
}
