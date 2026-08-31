import { useEffect, useRef, useState } from 'react';
import { clamp01, smoothstep } from '../hooks/useInView';

/**
 * Signature scroll transition — a 340vh section pinned for its middle.
 * Scroll progress drives three phases:
 *   0.00–0.40  BEFORE — scattered customs PDFs drift & blur in chaos
 *   0.40–0.62  SHIFT  — gold scan-line sweeps, chaos collapses
 *   0.62–1.00  AFTER  — the clean Zenith answer card rises, grounded
 */

const DOCS = [
  { name: 'CBIC_Customs_Manual_2023.pdf', meta: '8.6 MB · 470 pages', rotate: -8, x: '2%', y: '2%', stamp: 'Ctrl+F "quota" — 0 results' },
  { name: 'DGFT_HBP_2023.pdf', meta: '13.9 MB · 610 pages', rotate: 5, x: '56%', y: '0%', stamp: 'Reading page 312 of 610…' },
  { name: 'FTP2023_Full_Document.pdf', meta: 'Chapters 1–11', rotate: -3, x: '18%', y: '36%', stamp: 'Which corrigendum applies?' },
  { name: 'Appendix_4R_RoDTEP_Schedule.pdf', meta: '6.2 MB · rate tables', rotate: 9, x: '64%', y: '34%', stamp: 'Rate changed last week' },
  { name: '02_UCC_952-2013.pdf', meta: 'EU · 502 pages', rotate: -12, x: '40%', y: '66%', stamp: 'English version where?' },
  { name: 'Public_Notice_49.pdf', meta: 'Procedure circular', rotate: 13, x: '-2%', y: '64%', stamp: 'Superseded — or not?' },
];

export default function BeforeAfter() {
  const sectionRef = useRef<HTMLElement>(null);
  const [reduced, setReduced] = useState(false);
  const [p, setP] = useState(0);

  useEffect(() => {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    setReduced(mq.matches);
    const fn = (e: MediaQueryListEvent) => setReduced(e.matches);
    mq.addEventListener('change', fn);
    return () => mq.removeEventListener('change', fn);
  }, []);


  useEffect(() => {
    let raf = 0;
    let last = -1;
    const loop = () => {
      const el = sectionRef.current;
      if (el) {
        const rect = el.getBoundingClientRect();
        const total = el.offsetHeight - window.innerHeight;
        const prog = clamp01(-rect.top / Math.max(1, total));
        if (Math.abs(prog - last) > 0.001) {
          last = prog;
          setP(prog);
        }
      }
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, []);

  const t = smoothstep((p - 0.4) / 0.22); // transition blend 0→1
  const chaos = clamp01(p / 0.4); // before-phase drift
  const after = smoothstep((p - 0.62) / 0.32); // after-phase rise
  const sweep = Math.sin(Math.PI * clamp01((p - 0.34) / 0.36)); // scan-line glow

  if (reduced) {
    // Static, un-pinned fallback: both stages shown plainly.
    return (
      <section id="shift" className="relative bg-[#050505] py-24">
        <div className="max-w-6xl mx-auto px-5">
          <div className="text-center">
            <p className="eyebrow">The shift</p>
            <h2 className="mt-4 font-display italic text-3xl sm:text-5xl text-[#f5f1e8]">
              Four hundred pages. One number.
            </h2>
            <h2 className="text-3xl sm:text-5xl text-gold-grad">One question. One answer.</h2>
          </div>
          <div className="relative h-[400px] mt-12">
            <BeforeStage chaos={0} t={0} />
          </div>
          <div className="relative h-[560px] mt-10">
            <AfterStage after={1} />
          </div>
        </div>
      </section>
    );
  }

  return (
    <section id="shift" ref={sectionRef} className="relative bg-[#050505]" style={{ height: '340vh' }}>
      <div className="sticky top-0 h-screen overflow-hidden flex flex-col items-center justify-center">
        {/* Gold scan line riding the scroll position */}
        <div
          className="absolute left-0 right-0 h-px pointer-events-none"
          style={{
            top: `${p * 100}%`,
            background: 'linear-gradient(90deg, transparent, #e8a23a, transparent)',
            opacity: 0.12 + 0.88 * sweep,
          }}
        />

        {/* Progress rail (desktop) */}
        <div className="hidden lg:flex absolute left-10 top-1/2 -translate-y-1/2 flex-col items-center gap-4">
          <span className={`font-mono-j text-[10px] tracking-[0.3em] transition-opacity duration-300 ${p < 0.5 ? 'text-white/80' : 'text-white/25'}`}>
            BEFORE
          </span>
          <div className="h-36 w-px bg-white/15 overflow-hidden">
            <div className="w-full bg-[#e8a23a] transition-none" style={{ height: `${p * 100}%` }} />
          </div>
          <span className={`font-mono-j text-[10px] tracking-[0.3em] transition-opacity duration-300 ${p >= 0.5 ? 'text-[#e8a23a]' : 'text-white/25'}`}>
            AFTER
          </span>
        </div>

        {/* Crossfading headlines */}
        <div className="relative grid text-center px-5 mb-6 sm:mb-10 pointer-events-none">
          <h2 className="[grid-area:1/1] transition-none" style={{ opacity: 1 - t, transform: `translateY(${-26 * t}px)`, filter: `blur(${6 * t}px)` }}>
            <span className="eyebrow block mb-4 text-white/50">The old way</span>
            <span className="block font-display italic text-4xl sm:text-6xl md:text-7xl text-[#f5f1e8]">
              Four hundred pages.
            </span>
            <span className="block font-normal text-4xl sm:text-6xl md:text-7xl -mt-1 text-[#f5f1e8]">
              One number.
            </span>
          </h2>
          <h2 className="[grid-area:1/1] transition-none" style={{ opacity: t, transform: `translateY(${26 * (1 - t)}px)`, filter: `blur(${6 * (1 - t)}px)` }}>
            <span className="eyebrow block mb-4">With Zenith</span>
            <span className="block font-display italic text-4xl sm:text-6xl md:text-7xl text-gold-grad">
              One question.
            </span>
            <span className="block font-normal text-4xl sm:text-6xl md:text-7xl -mt-1 text-gold-grad">
              One answer.
            </span>
          </h2>
        </div>

        {/* Stage */}
        <div className="relative w-[min(960px,94vw)] h-[380px] sm:h-[420px]">
          <BeforeStage chaos={chaos} t={t} />
          <AfterStage after={after} />
        </div>

        {/* Phase caption */}
        <div className="relative grid mt-6 sm:mt-8 text-center pointer-events-none">
          <p
            className="[grid-area:1/1] font-mono-j text-[11px] tracking-[0.25em] uppercase text-white/40 transition-none"
            style={{ opacity: 1 - t }}
          >
            avg. 22 minutes lost per rate lookup
          </p>
          <p
            className="[grid-area:1/1] font-mono-j text-[11px] tracking-[0.25em] uppercase text-[#e8a23a] transition-none"
            style={{ opacity: t }}
          >
            grounded · cited · verified
          </p>
        </div>
      </div>
    </section>
  );
}



/* ── BEFORE: scattered customs documents, drifting in chaos ── */
function BeforeStage({ chaos, t }: { chaos: number; t: number }) {
  return (
    <div
      className="absolute inset-0"
      style={{
        opacity: 1 - t,
        filter: `blur(${t * 12}px)`,
        transform: `scale(${1 - 0.1 * t})`,
      }}
    >
      {DOCS.map((d, i) => (
        <div
          key={d.name}
          className="absolute w-52 sm:w-64 rounded-lg border border-white/10 bg-[#12100c]/90 p-4 shadow-[0_24px_60px_-12px_rgba(0,0,0,0.8)]"
          style={{
            left: d.x,
            top: d.y,
            transform: `rotate(${d.rotate * (1 + chaos * 0.7)}deg) translate(${chaos * (i % 2 === 0 ? -14 : 14)}px, ${-chaos * 10}px)`,
            opacity: 0.9 - chaos * 0.35,
          }}
        >
          <div className="flex items-start justify-between gap-2">
            <p className="font-mono-j text-[11px] text-white/80 truncate">{d.name}</p>
            <span className="font-mono-j text-[9px] text-white/30 shrink-0 mt-0.5">PDF</span>
          </div>
          <p className="font-mono-j text-[10px] text-white/40 mt-1">{d.meta}</p>
          <div className="mt-3 border-t border-dashed border-red-400/30 pt-2">
            <p className="font-mono-j text-[10px] text-red-300/80">✕ {d.stamp}</p>
          </div>
        </div>
      ))}
    </div>
  );
}

/* ── AFTER: the clean, grounded Zenith answer card ── */
function AfterStage({ after }: { after: number }) {
  const stampT = smoothstep((after - 0.82) / 0.18);
  return (
    <div
      className="absolute inset-0 flex items-center justify-center"
      style={{
        opacity: after,
        transform: `translateY(${(1 - after) * 64}px) scale(${0.95 + 0.05 * after})`,
      }}
    >
      <div className="relative w-[min(680px,94vw)] rounded-lg border border-[#e8a23a]/25 bg-[#0d0b08] p-6 sm:p-8 text-left shadow-[0_40px_120px_-20px_rgba(232,162,58,0.28)]">
        {/* Card header */}
        <div className="flex items-center justify-between gap-3 pb-4 rule-double">
          <div className="flex items-center gap-2">
            <svg width="18" height="18" viewBox="0 0 256 256" fill="#e8a23a">
              <path d="M 128 0 L 256 256 L 192 256 L 128 96 L 64 256 L 0 256 Z" />
            </svg>
            <span className="font-display italic text-lg text-[#f5f1e8]">Zenith</span>
          </div>
          <span className="font-mono-j text-[9px] tracking-[0.2em] uppercase text-[#e8a23a] border border-[#e8a23a]/30 rounded-full px-3 py-1">
            KB + Live Web
          </span>
        </div>

        {/* Question */}
        <p className="font-mono-j text-xs text-white/50 mt-5">Q: What is the minimum export quantity for wheat under the quota?</p>

        {/* Answer */}
        <p className="text-sm sm:text-[15px] leading-relaxed text-[#f5f1e8]/90 mt-3">
          Exports of wheat are permitted only for quantities{' '}
          <strong className="text-[#e8a23a]">above 10,000 MT</strong> per exporter, subject to allocation through the
          special EFC. Applications below this threshold are not considered{' '}
          <sup className="text-[#e8a23a] font-mono-j">[1]</sup>, and re-allocation of unshipped quantities follows the
          procedure in the Handbook of Procedures{' '}
          <sup className="text-[#e8a23a] font-mono-j">[2]</sup>.
        </p>

        {/* Citations */}
        <div className="flex flex-wrap gap-2 mt-5">
          <span className="font-mono-j text-[10px] text-white/70 border border-white/15 rounded-full px-3 py-1.5">
            [1] DGFT Notification 62 — p.2
          </span>
          <span className="font-mono-j text-[10px] text-white/70 border border-white/15 rounded-full px-3 py-1.5">
            [2] CBIC Customs Manual 2023 — p.312
          </span>
          <span className="font-mono-j text-[10px] text-white/70 border border-white/15 rounded-full px-3 py-1.5">
            [3] dgft.gov.in — live
          </span>
        </div>

        {/* Footer meta */}
        <p className="font-mono-j text-[10px] tracking-[0.2em] uppercase text-[#e8a23a]/80 mt-5 pt-4 border-t border-white/10">
          1 LLM call · 1.4s · every number cited
        </p>

        {/* Clearance stamp — slams in as the scroll completes */}
        <div
          className="stamp absolute top-6 right-5 sm:right-8 px-4 py-2 text-[#e8a23a] text-[10px] sm:text-xs pointer-events-none"
          style={{
            opacity: stampT,
            transform: `rotate(-8deg) scale(${1.8 - 0.8 * stampT})`,
          }}
        >
          Cleared · Zenith · 1.4s
        </div>
      </div>
    </div>
  );
}
