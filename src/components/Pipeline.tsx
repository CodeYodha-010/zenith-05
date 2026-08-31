import Reveal from './Reveal';

/**
 * BOX 02 — The Clearance Pipeline.
 * Replaces the generic feature-grid + numbered-steps pattern with an
 * asymmetric shipping-route schematic: nodes on a flowing dashed line.
 */

const SOURCES = [
  { k: 'DocumentMetadata', v: 'topic & commodity' },
  { k: 'FactIndex', v: 'structured facts' },
  { k: 'SearchIndex chunks', v: 'FAISS dense' },
  { k: 'Page summaries', v: 'BM25 sparse' },
];

const NODES = [
  {
    code: 'N-1',
    tag: 'UNDERSTAND',
    title: 'The query is decoded first',
    body: 'Intent, commodity, region and expected fact-type are detected in milliseconds, before a single search runs. No model calls are burned on understanding you.',
  },
  {
    code: 'N-2',
    tag: 'FUSE',
    title: 'Four sources, one ranking',
    body: 'FAISS dense vectors and BM25 sparse scores are fused with Reciprocal Rank Fusion, so an exact HS code and a fuzzy paraphrase both surface.',
  },
  {
    code: 'N-3',
    tag: 'EXTRACT',
    title: 'Facts, not paragraphs',
    body: 'Quantities, deadlines, fees and penalties live in a structured index. Hard questions query a table; they never go digging through prose.',
  },
  {
    code: 'N-4',
    tag: 'VERIFY',
    title: 'Numbers get a second pass',
    body: 'Duty rates and quotas are re-checked in parallel against dgft.gov.in, cbic.gov.in and ec.europa.eu while live web results are pulled alongside the local base.',
  },
  {
    code: 'N-5',
    tag: 'ANSWER',
    title: 'Streamed with receipts',
    body: 'One grounded synthesis, token by token over SSE. Every figure carries a citation to the exact document and page it came from.',
  },
];

export default function Pipeline() {
  return (
    <section id="pipeline" className="relative bg-[#050505] py-28 sm:py-36 overflow-hidden">
      <div className="max-w-6xl mx-auto px-5 grid lg:grid-cols-12 gap-12 lg:gap-16">
        {/* Left: sticky manifest header */}
        <div className="lg:col-span-4">
          <div className="lg:sticky lg:top-28">
            <Reveal>
              <p className="eyebrow">Box 02 · The pipeline</p>
              <h2 className="mt-4 font-display italic text-4xl sm:text-5xl leading-[1.05] text-[#f5f1e8]">
                Retrieval is the product.
              </h2>
              <h2 className="mt-1 text-4xl sm:text-5xl leading-[1.05] text-gold-grad">
                Generation is the last step.
              </h2>
              <p className="mt-6 text-sm leading-relaxed text-white/65 max-w-sm">
                Zenith clears your question through four retrieval sources and a verification pass before a single
                word is generated. Here is the route it takes.
              </p>
            </Reveal>

            <Reveal delay={120}>
              <div className="mt-10 rule-double pb-4">
                <p className="font-mono-j text-[10px] tracking-[0.25em] uppercase text-white/40">
                  Retrieval sources on file
                </p>
              </div>
              <ul className="mt-4 flex flex-col gap-3">
                {SOURCES.map((s) => (
                  <li key={s.k} className="flex items-baseline text-xs">
                    <span className="font-mono-j text-white/70">{s.k}</span>
                    <span className="flex-1 mx-2 border-b border-dotted border-white/25 translate-y-[-3px]" />
                    <span className="font-mono-j text-[#e8a23a]">{s.v}</span>
                  </li>
                ))}
              </ul>
            </Reveal>
          </div>
        </div>

        {/* Right: route nodes on a flowing dashed line */}
        <div className="lg:col-span-8 relative">
          <div className="route-line absolute left-[7px] sm:left-[9px] top-3 bottom-3" />
          <div className="flex flex-col gap-14 sm:gap-16">
            {NODES.map((n, i) => (
              <Reveal key={n.code} delay={i * 90}>
                <div className="relative pl-10 sm:pl-14">
                  {/* node marker */}
                  <div className="absolute left-0 top-1.5 w-[15px] h-[15px] sm:w-[19px] sm:h-[19px] rounded-full border-2 border-[#e8a23a] bg-[#050505] shadow-[0_0_0_4px_rgba(232,162,58,0.12)]" />
                  <div className="flex items-center gap-3">
                    <span className="font-mono-j text-[11px] text-[#e8a23a]">{n.code}</span>
                    <span className="font-mono-j text-[10px] tracking-[0.25em] uppercase text-white/40 border border-white/15 rounded-full px-3 py-1">
                      {n.tag}
                    </span>
                  </div>
                  <h3 className="mt-3 text-xl sm:text-2xl font-semibold text-[#f5f1e8]">{n.title}</h3>
                  <p className="mt-3 text-sm sm:text-base leading-relaxed text-white/65 max-w-xl">{n.body}</p>

                  {/* inline artifact: FactIndex row mock */}
                  {n.code === 'N-3' && (
                    <div className="mt-5 rounded-lg border border-white/10 bg-[#0a0906] px-4 py-3 font-mono-j text-[11px] text-white/60 overflow-x-auto whitespace-nowrap">
                      subject=<span className="text-[#e8a23a]">wheat_export</span> · fact_type=
                      <span className="text-[#e8a23a]">quantity_limit</span> · value=
                      <span className="text-[#e8a23a]">&quot;10,000 MT&quot;</span> · confidence=
                      <span className="text-[#e8a23a]">0.92</span> · src=<span>DGFT Notif. 62, p.2</span>
                    </div>
                  )}
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
