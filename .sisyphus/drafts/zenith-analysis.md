# Draft: Zenith Landing — Deep Analysis

## Repo Identity
- **Name**: zenith-landing
- **Purpose**: Marketing/landing page for Zenith — AI trade compliance assistant for Indian exporters (HS codes, duty rates, export procedures). Grounded in DGFT, CBIC, EU customs docs with live web verification.
- **Brand**: Customs-form / ledger / rubber-stamp editorial luxury. Ink #050505, paper #f5f1e8, gold #e8a23a. Fonts: DM Serif Display (display italic), IBM Plex Sans (body), JetBrains Mono (mono labels/tokens).
- **Stack**: Vite 5.4.11 + React 18.3.1 + TypeScript 5.6 strict + Tailwind 3.4.17 + lucide-react 0.469. No router, no state lib beyond React Context, no tests, no CI.

## Tech Stack & Tooling
- **Build**: `tsc && vite build` -> `dist/` (assets hashed). Dev: `vite` with proxy `/api -> http://127.0.0.1:8000` (same-origin cookie flow, no CORS).
- **TS**: ES2020, bundler resolution, strict, noUnusedLocals/Params, allowImportingTsExtensions.
- **Styling**: Tailwind with content globs index.html + src/**/*.{ts,tsx}, no plugins. All brand styling via index.css custom CSS (265 lines) + Tailwind utilities. PostCSS: tailwind + autoprefixer.
- **Deps**: Minimal — react, react-dom, lucide-react. Dev: @types/react, vite plugin, tailwind, ts. No zod, no router, no testing.
- **Fonts**: Self-hosted woff2 in public/fonts (3 files), mirrored from Django app. Loaded via @font-face with font-display: swap.
- **Not git repo?**: `Is directory a git repo: no` per env — but has .gitignore (node_modules, dist, *.local, .DS_Store). Possibly git not initialized or detached.

## File Tree (17 source files)
```
index.html
vite.config.ts (proxy)
tailwind.config.js
tsconfig.json
postcss.config.js
public/favicon.svg + public/fonts/*.woff2 (3)
src/
  main.tsx (ReactDOM.createRoot -> App)
  App.tsx (AuthProvider wrapper, 8 sections stacked)
  index.css (design system)
  vite-env.d.ts
  auth/AuthContext.tsx (session restore, signIn/Up/Out, modal state)
  lib/api.ts (minimal Django session-auth client, CSRF)
  hooks/useInView.ts (IntersectionObserver one-shot + clamp01/smoothstep)
  components/
    Nav.tsx (masthead, scroll-aware, operator state)
    Hero.tsx (spotlight reveal + Ken Burns + CTAs)
    Ticker.tsx (corpus marquee 12 docs x2, 42s linear)
    BeforeAfter.tsx (340vh pinned scroll transition)
    Pipeline.tsx (5 nodes on dashed flowing line)
    Stats.tsx (manifest ruled table)
    Regions.tsx (3 regimes asymmetric cards)
    Closing.tsx (ledger-lines CTA + footer)
    Reveal.tsx (wrapper around useInView, blur+translate reveal)
    AuthModal.tsx (Box 00 form, signin/signup tabs)
```

## Architecture & Data Flow
- **App shell**: `main.tsx -> App.tsx -> AuthProvider -> [Nav, Hero, Ticker, BeforeAfter, Pipeline, Stats, Regions, Closing, AuthModal]`. No routing, single page with hash anchors (#shift, #pipeline, #coverage, #cta, #top).
- **Auth**: Django session cookie (HttpOnly) + CSRF. Flow: `api.me() GET /api/auth/me/` on mount (restore) -> set user/loading. `api.login/register/logout` POST with `ensureCsrf()` (GET /api/auth/csrf/ if missing cookie, then X-CSRFToken header). Context holds `user`, `loading`, `authOpen`, `authMode`, `openAuth/closeAuth`, `signIn/Up/Out`. Modal controlled centrally, rendered in App. Nav + Hero + Closing branch on `user` (Launch App vs Ask/Sign in). `APP_URL` = VITE_APP_URL || 127.0.0.1:8000.
- **State**: Only AuthContext. No reducers, no persistence beyond cookie. `loading` only seeded once; no error state for me() failure (silently stays loading? actually sets user null but loading false only on success — bug if fetch fails).
- **Hooks**: `useInView` — one-shot observer (disconnect on intersect), threshold param. `Reveal` wraps it, adds `reveal` + `is-in` class + delay style. Used by Pipeline nodes, Stats, Regions, Closing. BeforeAfter uses manual scroll progress (rAF loop, clamp01/smoothstep), not useInView.
- **API client**: `get`/`post` helpers with credentials:include. No interceptors, no retry, no timeout, no typed error handling. Returns `ApiResult<T>` with ok/status/data.

## Design System Deep Dive (index.css)
- **Tokens**: --ink #050505, --ink-2 #0b0a08, --paper #f5f1e8, --gold #e8a23a, --gold-deep #c9821f, --muted rgba(...0.65), --line rgba(...0.12).
- **Classes**: .font-display, .font-mono-j, .eyebrow (mono 11px 0.32em gold), .reveal/.is-in (blur 10px + translateY 46px -> 0, 1s cubic), .text-gold-grad (solid gold, comment says no gradient), .ledger-lines (repeating linear 47px ruling), .rule-double (3px double border), .stamp (double border, uppercase, tracking 0.18em), .route-line (dashed gold, flowing animation), .ticker-track (42s infinite), .scroll-cue-line (cueDrop), .grain (fixed fractalNoise 0.045 opacity, z-90), .hero-anim/.hero-reveal/.hero-zoom, reduced-motion kill-switch.
- **Global**: scroll-behavior smooth, body overflow-x hidden, ::selection gold, :focus-visible gold outline, scrollbar styled #2b251b -> gold-deep.
- **Aesthetic**: Consistently customs-form metaphor — double rules, mono field labels, dossier cards, stamp CTAs, ledger ruling, crop marks, form Z-1 references.

## Component Analysis
- **Nav (101 lines)**: Fixed z100, scroll listener >40px adds bg #0b0a08/95 + border. Masthead SVG triangle + wordmark + mono sub. Desktop links with hover underline. Operator state: signed-in shows pulsing dot + username pill + Launch App stamp + LogOut icon; signed-out shows Ask + Sign in stamp. Mobile Menu button exists but has no drawer logic (dead UI). Uses lucide Menu, LogOut. APP_URL external link target_blank.
- **Hero (190 lines)**: Full viewport (100dvh + 100vh fallback), Ken Burns zoom (1.12->1, 1.8s), spotlight reveal: canvas-generated radial gradient mask driven by lerped mouse (0.1 lerp per frame, rAF loop). Two external higgs.ai images (1280w webp). Headlines with staggered hero-anim delays. Bottom-left/right copy + conditional CTA (Launch vs Ask). Crop marks, scroll cue. Pointer-events-none on text to allow spotlight. Risks: external image CDN dependency, no fallback, no reduced-motion for spotlight, canvas.toDataURL per frame (costly, should use CSS mask).
- **Ticker (33 lines)**: 12 docs duplicated -> w-max flex, gap-10, 42s linear infinite. Static list, no props.
- **BeforeAfter (264 lines)**: Most complex — 340vh section, sticky 100vh stage, scroll progress via rAF reading getBoundingClientRect + offsetHeight. Three phases: BEFORE chaos (6 PDF cards scattered with rotate/x/y, drift via chaos factor), SHIFT (gold scan line + headline crossfade + sweep), AFTER (Zenith answer card, citation pills, stamp slam). Reduced motion fallback renders static stacked version. Uses clamp01/smoothstep for easing. Risks: rAF loop always running even off-screen, no cleanup of computation, heavy inline styles.
- **Pipeline (124 lines)**: Left sticky manifest + sources dotted leaders + right 5 nodes on vertical route-line (flowing dashed). Each Reveal staggered 90ms. N-3 has inline FactIndex row mock (subject, fact_type, value, confidence). Clear, well-structured.
- **Stats (56 lines)**: Ruled invoice table, 5 rows, dotted leader, hover bg [0.02], gold italic values. Max-w 4xl.
- **Regions (88 lines)**: 12-col grid, IN flagship spans 7 cols (gold gradient + shadow + Cleared stamp) vs EU/US 5 cols each. Header strip with port-of-loading + code. Docs list with — marker. Hover lift.
- **Closing (79 lines)**: ledger-lines bg, centered CTA (same branching), footer with 3-col (logo, copyright 2026, stack: Django FAISS RRF Tavily OpenRouter).
- **Reveal (23 lines)**: Thin wrapper, threshold 0.15, delay prop for stagger.
- **AuthModal (175 lines)**: z200, backdrop blur, centered 440px card, gold border, shadow. Header with rule-double, tabs for signin/signup, form with email/username/password + field errors + busy state. Field style: bg #0a0906 border rounded 6px. Submit stamp button rotates -1deg on hover. Close on Escape + backdrop click. No form validation beyond server errors, no password strength, no show/hide.

## Auth & Integration Gaps
- **CSRF**: ensureCsrf does GET /api/auth/csrf/ then reads cookie — correct Django pattern, but assumes cookie readable (not HttpOnly). Missing error handling if fetch fails -> token '' -> POST fails silently.
- **me() on load**: Cancelled flag pattern, but no catch — if network fails, loading stays true forever (spinner missing, but UI not handling loading state anyway). No retry.
- **No error boundary**: Any throw in AuthProvider kills whole app.
- **APP_URL**: Used as href for Launch App in 3 places (Nav, Hero, Closing) — external Django app URL. No validation.
- **No logout feedback**: signOut voids, Nav button has no loading.
- **Proxy only in dev**: Production comment says "serve this build from Django itself" — implies no standalone deploy without Django; no env handling for standalone.
- **Missing**: password reset, email verification, rate limiting UI, form validation (Zod), accessibility for modal focus trap (no focus trap, just close on click).

## Quality, Risks & Improvement Opportunities
- **No tests**: Zero test infrastructure (no vitest/jest, no playwright). Manual QA only.
- **No lint/format**: No eslint, prettier, no husky. Strict TS but no CI.
- **No router**: Hash anchors work but no smooth scroll polyfill needed (has CSS).
- **Performance**: Grain via SVG filter fixed layer + Hero canvas per-frame toDataURL + BeforeAfter rAF loop + ticker infinite animation — could jank on low-end. Hero images from higgs.ai proxied with params — no srcset, no lazy, no preload.
- **Accessibility**: Focus-visible is styled, reduced-motion covered for most but not Hero spotlight mouse tracking. AuthModal has role/dialog + aria-label but no focus trap, no aria-describedby, no form required attributes. Heading hierarchy: multiple h1/h2 mixed — should be h1 only once. Color contrast gold on paper passes? Possibly low on white/25 overlays.
- **SEO**: Meta tags in index.html are good (description, og, twitter, theme-color, title) but no JSON-LD, no sitemap, no robots, no canonical.
- **Security**: No hardcoded secrets. CSRF handled. But document.cookie regex is fragile, no sanitize for api response. XSS risk low (no dangerouslySetInnerHTML).
- **Dead code**: Nav mobile Menu button non-functional; BeforeAfter's isolated reduced path not tested; clamp01/smoothstep exported but only used in BeforeAfter (Hero doesn't use them).
- **Bundle**: No code splitting, all components bundled together. Single chunk dist/assets/index-Cx72ZaMn.js — ok for small landing but could lazy-load BeforeAfter heavy section.
- **Fonts**: 3 woff2 self-hosted correctly with swap — good.
- **Dist**: Already built (index.html + assets). Could be served.

## Intent Inference (what owner might want next)
- Likely paths: (a) wire to real Django backend, (b) improve landing conversion, (c) add analytics/SEO, (d) mobile nav drawer, (e) test infrastructure, (f) deploy standalone.
- Pending user direction — awaiting what work to plan.

## Open Questions for User
- What is the immediate goal? (polish landing, add features, connect backend, deploy, test)?
- Is the Django app at 127.0.0.1:8000 available for contract verification?
- Target deploy: Django-served vs standalone (Vercel/Netlify)?
- Do you want tests/CI added?
