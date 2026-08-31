import { useEffect, useRef, useState } from 'react';

export function useInView<T extends HTMLElement>(threshold = 0.2) {
  const ref = useRef<T>(null);
  const [inView, setInView] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setInView(true);
          obs.disconnect();
        }
      },
      { threshold }
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [threshold]);

  return { ref, inView };
}

export function clamp01(v: number) {
  return Math.min(1, Math.max(0, v));
}

export function smoothstep(v: number) {
  const x = clamp01(v);
  return x * x * (3 - 2 * x);
}
