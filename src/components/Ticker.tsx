const DOCS = [
  'CBIC Customs Manual 2023',
  'DGFT FTP 2023',
  'Handbook of Procedures',
  'RoDTEP Appendix 4R',
  'UCC 952/2013',
  'REACH 1907/2006',
  'EU Food Safety 178/2002',
  'EORI Implementation',
  'eSANCHIT Guide',
  'Certificate of Origin Manual',
  'DGFT Notification 62',
  'EUR.1 Handbook',
];

export default function Ticker() {
  const row = [...DOCS, ...DOCS];
  return (
    <div className="relative border-y border-white/10 bg-[#0b0a08] py-5 overflow-hidden">
      <div className="ticker-track flex w-max items-center gap-10 whitespace-nowrap">
        {row.map((d, i) => (
          <span key={i} className="flex items-center gap-10">
            <span className="font-mono-j text-xs tracking-[0.25em] uppercase text-white/45">{d}</span>
            <span className="text-[#e8a23a]/70 text-xs">✦</span>
          </span>
        ))}
      </div>
      <p className="relative text-center font-mono-j text-[10px] tracking-[0.2em] uppercase text-white/30 mt-4 px-5">
        Every document on this tape is in the index. Page numbers are real. Ask it what page 312 says.
      </p>
    </div>
  );
}
