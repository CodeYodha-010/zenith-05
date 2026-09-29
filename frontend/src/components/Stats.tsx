import Reveal from './Reveal';

/**
 * BOX 04 — The Manifest.
 * Replaces the big-counter stat row with a ruled customs-invoice table.
 */

const ROWS = [
  { label: 'Documents ingested', value: '41', note: 'PDF · DOCX · MD' },
  { label: 'Regimes covered', value: 'IN · EU · US', note: 'one index' },
  { label: 'LLM calls per answer', value: '1', note: 'by design' },
  { label: 'Median first token', value: '1.4 s', note: 'SSE stream' },
  { label: 'Citation coverage', value: '1:1', note: 'every number' },
];

export default function Stats() {
  return (
    <section className="relative bg-[#0b0a08] border-y border-white/10 py-24 sm:py-32">
      <div className="max-w-4xl mx-auto px-5">
        <Reveal>
          <p className="eyebrow">Box 04 · The manifest</p>
          <h2 className="mt-4 font-display italic text-3xl sm:text-5xl text-[#f5f1e8]">
            We count everything.
          </h2>
        </Reveal>

        <Reveal delay={120}>
          <div className="mt-12 rule-double pb-3 flex items-baseline justify-between">
            <span className="font-mono-j text-[10px] tracking-[0.25em] uppercase text-white/40">Item</span>
            <span className="font-mono-j text-[10px] tracking-[0.25em] uppercase text-white/40">Declared value</span>
          </div>

          <ul>
            {ROWS.map((r) => (
              <li
                key={r.label}
                className="group flex items-baseline gap-4 py-5 border-b border-white/10 hover:bg-white/[0.02] transition-colors px-2 -mx-2"
              >
                <span className="font-mono-j text-xs sm:text-sm text-white/70 shrink-0">{r.label}</span>
                <span className="flex-1 border-b border-dotted border-white/25 translate-y-[-4px]" />
                <span className="hidden sm:block font-mono-j text-[10px] text-white/35 shrink-0 mr-2">{r.note}</span>
                <span className="font-display italic text-2xl sm:text-3xl text-[#e8a23a] shrink-0 group-hover:underline decoration-1 underline-offset-8 decoration-[#e8a23a]/60">
                  {r.value}
                </span>
              </li>
            ))}
          </ul>

          <p className="font-mono-j text-[10px] tracking-[0.2em] uppercase text-white/30 mt-6">
            Declared under Form Z-1 · figures audited against the live index
          </p>
        </Reveal>
      </div>
    </section>
  );
}
