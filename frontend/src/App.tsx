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

export default function App() {
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
