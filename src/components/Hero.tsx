import { useEffect, useRef, useState } from 'react';
import { useAuth } from '../auth/AuthContext';
import { CHAT_URL } from '../lib/api';

/**
 * Zenith hero — cursor-following spotlight that reveals a second image.
 * Swap BG_IMAGE_1 / BG_IMAGE_2 for your own trade/customs imagery.
 */
const BG_IMAGE_1 =
  'https://images.higgs.ai/?default=1&output=webp&url=https%3A%2F%2Fd8j0ntlcm91z4.cloudfront.net%2Fuser_38xzZboKViGWJOttwIXH07lWA1P%2Fhf_20260609_195923_b0ba8ace-1d1d-4f2c-9a28-1ab84b330680.png&w=1280&q=85';
const BG_IMAGE_2 =
  'https://images.higgs.ai/?default=1&output=webp&url=https%3A%2F%2Fd8j0ntlcm91z4.cloudfront.net%2Fuser_38xzZboKViGWJOttwIXH07lWA1P%2Fhf_20260609_201152_bba90a12-bf12-459f-91f0-51f237dbaf3b.png&w=1280&q=85';

const SPOTLIGHT_R = 260;

function RevealLayer({ image, cursorX, cursorY }: { image: string; cursorX: number; cursorY: number }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const revealRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const resize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };
    resize();
    window.addEventListener('resize', resize);
    return () => window.removeEventListener('resize', resize);
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    const reveal = revealRef.current;
    if (!canvas || !reveal) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const gradient = ctx.createRadialGradient(cursorX, cursorY, 0, cursorX, cursorY, SPOTLIGHT_R);
    gradient.addColorStop(0, 'rgba(255,255,255,1)');
    gradient.addColorStop(0.4, 'rgba(255,255,255,1)');
    gradient.addColorStop(0.6, 'rgba(255,255,255,0.75)');
    gradient.addColorStop(0.75, 'rgba(255,255,255,0.4)');
    gradient.addColorStop(0.88, 'rgba(255,255,255,0.12)');
    gradient.addColorStop(1, 'rgba(255,255,255,0)');
    ctx.fillStyle = gradient;
    ctx.beginPath();
    ctx.arc(cursorX, cursorY, SPOTLIGHT_R, 0, Math.PI * 2);
    ctx.fill();

    const maskUrl = canvas.toDataURL();
    reveal.style.maskImage = `url(${maskUrl})`;
    reveal.style.webkitMaskImage = `url(${maskUrl})`;
    reveal.style.maskSize = '100% 100%';
    reveal.style.webkitMaskSize = '100% 100%';
  }, [cursorX, cursorY]);

  return (
    <>
      <canvas ref={canvasRef} className="absolute inset-0 pointer-events-none" style={{ display: 'none' }} />
      <div
        ref={revealRef}
        className="absolute inset-0 bg-center bg-cover bg-no-repeat z-30 pointer-events-none"
        style={{ backgroundImage: `url(${image})` }}
      />
    </>
  );
}

export default function Hero() {
  const mouse = useRef({ x: -999, y: -999 });
  const smooth = useRef({ x: -999, y: -999 });
  const rafRef = useRef<number>(0);
  const [cursorPos, setCursorPos] = useState({ x: -999, y: -999 });
  const { user, openAuth } = useAuth();

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      mouse.current.x = e.clientX;
      mouse.current.y = e.clientY;
    };
    window.addEventListener('mousemove', onMove);

    const loop = () => {
      smooth.current.x += (mouse.current.x - smooth.current.x) * 0.1;
      smooth.current.y += (mouse.current.y - smooth.current.y) * 0.1;
      setCursorPos({ x: smooth.current.x, y: smooth.current.y });
      rafRef.current = requestAnimationFrame(loop);
    };
    rafRef.current = requestAnimationFrame(loop);

    return () => {
      window.removeEventListener('mousemove', onMove);
      cancelAnimationFrame(rafRef.current);
    };
  }, []);

  return (
    <section id="top" className="relative w-full overflow-hidden h-screen bg-black" style={{ height: '100dvh' }}>
      {/* Base image — Ken Burns zoom-out */}
      <div
        className="absolute inset-0 bg-center bg-cover bg-no-repeat z-10 hero-zoom"
        style={{ backgroundImage: `url(${BG_IMAGE_1})` }}
      />

      {/* Spotlight reveal layer */}
      <RevealLayer image={BG_IMAGE_2} cursorX={cursorPos.x} cursorY={cursorPos.y} />

      {/* Heading */}
      <div className="z-50 absolute top-[14%] left-0 right-0 flex flex-col items-center text-center px-5 pointer-events-none">
        <h1 className="text-white leading-[0.95]">
          <span
            className="block font-display italic font-normal text-5xl sm:text-7xl md:text-8xl hero-anim hero-reveal"
            style={{ letterSpacing: '-0.05em', animationDelay: '0.25s' }}
          >
            Trade rules,
          </span>
          <span
            className="block font-normal text-5xl sm:text-7xl md:text-8xl -mt-1 hero-anim hero-reveal"
            style={{ letterSpacing: '-0.08em', animationDelay: '0.42s' }}
          >
            made clear.
          </span>
        </h1>
      </div>

      {/* Bottom-left paragraph */}
      <div
        className="hidden sm:block absolute bottom-14 left-10 md:left-14 max-w-[260px] z-50 hero-anim hero-fade"
        style={{ animationDelay: '0.7s' }}
      >
        <p className="text-sm text-white/80 leading-relaxed">
          Forty official sources — DGFT handbooks, CBIC manuals, EU customs codes — distilled into answers you can
          trust, cited page by page.
        </p>
      </div>

      {/* Bottom-right block with CTA */}
      <div
        className="absolute bottom-10 sm:bottom-24 left-5 right-5 sm:left-auto sm:right-10 md:right-14 max-w-full sm:max-w-[260px] flex flex-col items-start gap-4 sm:gap-5 z-50 hero-anim hero-fade"
        style={{ animationDelay: '0.85s' }}
      >
        <p className="text-xs sm:text-sm text-white/80 leading-relaxed">
          Ask anything about HS codes, duty rates, or export procedures. Every answer is grounded in official
          documents, with live web search when the rules change.
        </p>
        {user ? (
          <a
            href={CHAT_URL || '/'}
            target={CHAT_URL ? '_blank' : undefined}
            rel="noreferrer"
            className="bg-[#e8a23a] hover:bg-[#d18f28] text-white text-sm font-medium px-7 py-3 rounded-full transition-all hover:scale-[1.03] active:scale-95 hover:shadow-lg hover:shadow-[#e8a23a]/30"
          >
            Launch Zenith
          </a>
        ) : (
          <button
            onClick={() => openAuth('signup')}
            className="bg-[#e8a23a] hover:bg-[#d18f28] text-white text-sm font-medium px-7 py-3 rounded-full transition-all hover:scale-[1.03] active:scale-95 hover:shadow-lg hover:shadow-[#e8a23a]/30"
          >
            Ask Zenith
          </button>
        )}
      </div>

      {/* Crop marks + field annotations */}
      <div className="absolute top-20 left-5 sm:top-24 sm:left-8 z-40 font-mono-j text-[9px] tracking-[0.25em] uppercase text-white/40 hero-anim hero-fade" style={{ animationDelay: '1.2s' }}>
        Form Z-1 / Exporter copy
      </div>
      <div className="absolute top-20 right-5 sm:top-24 sm:right-8 z-40 font-mono-j text-[9px] tracking-[0.25em] uppercase text-white/40 text-right hero-anim hero-fade" style={{ animationDelay: '1.3s' }}>
        Port of entry: any
      </div>
      <div className="hidden md:block absolute bottom-8 left-8 z-40 font-mono-j text-[9px] tracking-[0.25em] uppercase text-white/40 hero-anim hero-fade" style={{ animationDelay: '1.4s' }}>
        Art. 57 � Verified sources
      </div>

      {/* Scroll cue */}
      <div
        className="hidden sm:flex absolute bottom-8 left-1/2 -translate-x-1/2 z-50 flex-col items-center gap-3 hero-anim hero-fade"
        style={{ animationDelay: '1.1s' }}
      >
        <span className="font-mono-j text-[10px] tracking-[0.4em] text-white/60 uppercase">Scroll</span>
        <div className="h-12 w-px bg-white/20 overflow-hidden">
          <div className="scroll-cue-line h-full w-full bg-[#e8a23a]" />
        </div>
      </div>
    </section>
  );
}
