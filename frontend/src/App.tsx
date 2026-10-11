import { useEffect } from 'react';
import Nav from './components/Nav';
import Hero from './components/Hero';
import Ticker from './components/Ticker';
import BeforeAfter from './components/BeforeAfter';
import Pipeline from './components/Pipeline';
import Stats from './components/Stats';
import Regions from './components/Regions';
import Closing from './components/Closing';
import AuthModal from './components/AuthModal';
import { AuthProvider } from './auth/AuthContext';
import { APP_URL } from './lib/api';

export default function App() {
  useEffect(() => {
    // Warm the chat backend while the visitor reads this page. Render's free
    // tier sleeps after ~15 idle minutes; this fire-and-forget request starts
    // the instance now, so the post-login jump to the chat does not sit
    // through a cold start. mode no-cors: the request only needs to ARRIVE
    // (opaque response, never read); wake-up failures are expected, ignored.
    const base = /^https?:\/\//i.test(APP_URL) ? APP_URL : '';
    fetch(`${base}/healthz/`, { mode: 'no-cors', cache: 'no-store' }).catch(() => {});
  }, []);

  return (
    <AuthProvider>
      <div
        className="grain min-h-screen bg-[#050505] text-[#f5f1e8] tracking-[-0.02em]"
        style={{ fontFamily: "'IBM Plex Sans', sans-serif" }}
      >
        <Nav />
        <Hero />
        <Ticker />
        <BeforeAfter />
        <Pipeline />
        <Stats />
        <Regions />
        <Closing />
        <AuthModal />
      </div>
    </AuthProvider>
  );
}