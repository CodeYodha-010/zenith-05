import Reveal from './Reveal';

/**
 * BOX 03 — Ports of call.
 * Asymmetric layout breaks the equal-3-card rhythm: the flagship India
 * card spans wide while EU / US stack beside it.
 */

const REGIONS = [
  {
    code: 'IN',
    port: 'Nhava Sheva · Delhi Cargo',
    name: 'India',
    flagship: true,
    span: 'lg:col-span-7',
    docs: ['DGFT · FTP 2023 + Handbook of Procedures', 'CBIC Customs Manual 2023', 'RoDTEP Appendix 4R schedule', 'eSANCHIT · Certificate of Origin', 'Notification and circular watch'],
  },
  {
    code: 'EU',
    port: 'Rotterdam · Antwerp',
    name: 'European Union',
    flagship: false,
    span: 'lg:col-span-5',
    docs: ['Union Customs Code 952/2013', 'REACH 1907/2006', 'Food Safety 178/2002', 'EORI · REX guidance', 'EUR.1 movement handbook'],
  },
  {
    code: 'US',
    port: 'Los Angeles · Newark',
    name: 'United States',
    flagship: false,
    span: 'lg:col-span-5',
    docs: ['CBP entry procedures', 'HTS tariff schedule', 'FDA · FSVP rules', 'USDA · APHIS import', 'CTPAT trusted trader'],
  },
];

export default function Regions() {
  return (
    <section id="coverage" className="relative bg-[#050505] py-28 sm:py-36">
      <div className="max-w-6xl mx-auto px-5">
        <Reveal>
          <p className="eyebrow">Box 03 · Ports of call</p>
          <h2 className="mt-4 font-display italic text-4xl sm:text-6xl leading-[1.02] text-[#f5f1e8]">
            One assistant.
          </h2>
          <h2 className="text-4xl sm:text-6xl leading-[1.02] text-gold-grad">Three regimes.</h2>
        </Reveal>

        <div className="mt-14 sm:mt-20 grid lg:grid-cols-12 gap-6">
          {REGIONS.map((r, i) => (
            <Reveal key={r.code} delay={i * 110} className={r.span}>
              <div
                className={`h-full rounded-2xl border overflow-hidden transition-transform duration-500 hover:-translate-y-1.5 ${
                  r.flagship
                    ? 'border-[#e8a23a]/40 bg-gradient-to-b from-[#171105] to-[#0d0b08] shadow-[0_30px_80px_-30px_rgba(232,162,58,0.25)]'
                    : 'border-white/10 bg-[#0a0906]'
                }`}
              >
                {/* form-box header strip */}
                <div className="flex items-center justify-between px-7 py-3 border-b border-white/10 bg-white/[0.02]">
                  <span className="font-mono-j text-[10px] tracking-[0.25em] uppercase text-white/50">
                    Port of loading · {r.port}
                  </span>
                  {r.flagship ? (
                    <span className="stamp text-[9px] text-[#e8a23a] px-2.5 py-1 -rotate-3">Cleared</span>
                  ) : (
                    <span className="font-mono-j text-[10px] tracking-[0.3em] text-white/40">{r.code}</span>
                  )}
                </div>

                <div className="p-7 sm:p-8">
                  <h3 className="text-2xl font-semibold text-[#f5f1e8]">{r.name}</h3>
                  <ul className="mt-6 flex flex-col gap-3">
                    {r.docs.map((d) => (
                      <li key={d} className="font-mono-j text-[11px] leading-relaxed text-white/60 flex items-start gap-2">
                        <span className="text-[#e8a23a] mt-0.5">—</span>
                        {d}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}
