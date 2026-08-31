# Zenith Chat — Premium Redesign to Match Landing (Impeccable × Taste × Emil)

## TL;DR

> **Quick Summary**: Redesign the Zenith chatbot UI from generic chat to a premium, ledger-form Operate surface that is visually continuous with the landing — ink #050505, paper #f5f1e8, gold #e8a23a, DM Serif Display + IBM Plex Sans + JetBrains Mono, double-rules, stamp CTAs, grain, ledger lines. Built inside `zenith-landing` as a new `/chat` experience (or as a drop-in that Django can serve), reusing landing tokens with zero new deps, streaming SSE with cited answers.
>
> **Deliverables**:
> - New premium Chat route + shell reusing landing design system (no visual gap vs landing)
> - Message, composer, citations dock, conversation chrome, empty/error/loading states
> - Streaming + citation rendering wired to existing Django API (`/api/...` + APP_URL)
> - Polish pass: motion (Emil framework), a11y, responsive, perf
>
> **Estimated Effort**: Medium (3–4 days solo, 1.5 days with parallel waves)
> **Parallel Execution**: YES - 4 waves (foundation → core chrome → streaming/citations → polish)
> **Critical Path**: Tokens → Shell → Composer → Streaming → Polish → Final Verification

---

## Context

### Original Request
User: "zenith chatbot screen is not according to landing page and theme so you use a impeccable and apple design and taste design and give me detailed plan how can i make that premium and according to theme okay"

### Interview Summary
**Key Discussions**:
- Repo `zenith-landing` is marketing landing only — no chat UI exists here; chat lives at `APP_URL` (Django `127.0.0.1:8000`). Decision: build premium chat inside `zenith-landing` so it can be previewed standalone and optionally served by Django (same `dist/index.html` strategy) — avoids touching Django templates directly while guaranteeing visual parity.
- Design direction: Impeccable **Operate** mode (visitor completes a task, not persuaded) + Taste anti-slop (premium consumer / Apple-y / luxury / editorial) + Emil polish (unseen details compound, motion is motivated, springs for drag). Dials: DESIGN_VARIANCE 8, MOTION_INTENSITY 6, VISUAL_DENSITY 4.
- Ponytail constraint: fewest files, reuse stdlib/Tailwind, no new deps unless proven — Motion is allowed (landing already has custom CSS motion; we reuse it) vs adding framer-motion only if spring physics needed and justified.

**Research Findings**:
- Landing tokens (index.css): --ink #050505, --ink-2 #0b0a08, --paper #f5f1e8, --gold #e8a23a, --gold-deep #c9821f, --muted, --line, .eyebrow, .reveal, .stamp, .rule-double, .ledger-lines, .route-line, .grain, .hero-anim. All typography uses DM Serif Display italic for headlines, JetBrains Mono for field labels. Tailwind 3.4, no config extension needed.
- Auth: session cookie + CSRF via `lib/api.ts` — chat API will reuse same credentials/include path; no token handling needed.
- Missing chat contract: assume SSE stream (`text/event-stream`) with JSON chunks `{delta, citations, done}` — plan validates endpoint first and adapts.

### Metis Review
**Identified Gaps** (addressed):
- Chat code location unknown → Default: build inside `zenith-landing/src/chat/` + `src/pages/Chat.tsx` routed via hash `#chat` or Vite SPA route; Django can serve `dist` as-is (existing pattern). Document fallback: if Django exposes `/api/chat/stream`, use it; else mock local stream for UI polish.
- Streaming contract unconfirmed → Guardrail: Wave 1 validates `GET /api/auth/me/` + probes `POST /api/chat/` shape, captures real response in `docs/api-contract.md` before wiring stream.
- Operate vs Persuade confusion → Locked to **Operate** (Taste + Impeccable §Modes): scanability, consistency, native affordance > expression. No marketing hero inside chat.
- Motion overuse risk (landing has 5+ animations) → Emil framework: only animate occasional (message enter, dock slide, citation reveal) at 150–250ms ease-out, never keyboard input, never infinite loops. Honor `prefers-reduced-motion`.
- Anti-slop violations to prevent inside chat: no 3-equal-card rows, no `border-t+b` on every message row, no neon glows, no Inter, no custom cursors, no scroll cues, no duplicate CTAs. Enforced per-task.

---

## Work Objectives

### Core Objective
Make the Zenith chatbot feel like page 2 of the landing — same dossier, same ink, same stamp — but tuned for the **Operate** task: ask → retrieve → verify → answer with receipts. Premium means restraint, materiality, and invisible correctness, not decoration.

### Concrete Deliverables
- `src/chat/` module (shell, messages, composer, citations, history) + route wiring in `App.tsx`
- `src/chat/theme.ts` or `src/lib/tokens.ts` extension re-exporting landing CSS vars for JS use (if needed)
- Chat API adapter `src/chat/api/chat.ts` reusing `lib/api.ts` patterns (credentials include, CSRF)
- Premium states: empty (Box 00 manifest), loading (skeleton matching final layout), error (inline), streaming (token-by-token with blur mask)
- Citations dock (slide-over / collapsible rail) with page-real citations `[1] DGFT p.2`
- Polish: a11y focus trap, keyboard nav, reduced-motion, responsive (mobile dock → bottom sheet)

### Definition of Done
- [ ] `npm run build` passes (`tsc && vite build`) with zero new warnings
- [ ] Chat route renders at `#chat` or `/chat` (hash or BrowserRouter) and matches landing visually (spot-check via screenshot: header masthead, stamp, rules identical)
- [ ] Streaming demo shows token stream + citations appear and are clickable
- [ ] Playwright QA: send message → see streamed answer + citations; resize mobile → composer stays usable

### Must Have
- Visual continuity: same CSS vars, same fonts, same masthead SVG triangle, same `.stamp`/`.rule-double`/`.eyebrow` / grain treatment — no drift
- Operate discipline: one primary compositor action, one accent (gold), one radius system, no marketing clutter inside chat
- Real API wiring or documented mock that can be swapped by changing one `api` function

### Must NOT Have (Guardrails)
- No new design system (do not recreate landing tokens — import/reuse index.css)
- No 3-equal-card grids, no `border-t+b` on every message row, no AI-purple gradients, no pure #000, no custom cursor, no `window.addEventListener('scroll',…)` or `requestAnimationFrame` state loops — use IntersectionObserver / CSS / Motion values
- No Inter, no placeholder-as-label, no button without `:active scale(0.97)`, no em-dashes in copy
- No `console.log` in production, no hardcoded secrets, no duplicate CTA intent
- No scope creep beyond chat UI (do not refactor landing sections unless needed for shared tokens)

---

## Verification Strategy (MANDATORY)

> **ZERO HUMAN INTERVENTION** - ALL verification is agent-executed. No exceptions.

### Test Decision
- **Infrastructure exists**: NO (no vitest/jest, no playwright in package.json)
- **Automated tests**: NO (Ponytail: one runnable check per non-trivial logic, not full suite)
- **Framework**: none — add single `demo()` self-check in `src/chat/api/chat.ts` for parse logic if streaming added; otherwise evidence via Playwright-style manual QA captured as screenshots
- **Agent-Executed QA**: ALWAYS (Playwright via Bash curl alternative for API, screenshots for UI)

### QA Policy
Every task MUST include agent-executed QA scenarios. Evidence saved to `.sisyphus/evidence/task-{N}-{slug}.png` or `.log`.

- **Frontend/UI**: Playwright — navigate, interact, assert DOM, screenshot
- **API/Backend**: Bash curl — send requests, assert status + fields
- **Fallback**: If Playwright not installed, use `npx playwright` or capture via `vite preview` + curl + screenshot tool; never require user manual click

---

## Execution Strategy

### Parallel Execution Waves

> Target: 5-8 tasks per wave. Shared tokens/setup first to unblock.

```
Wave 1 (Foundation — tokens + shell + contract, all parallel except 1→2→3 chain):
├── Task 1: Extract/share landing tokens + add chat theme extensions [quick]
├── Task 2: App routing + Chat shell chrome (masthead, rail, ledger bg) [visual-engineering]
├── Task 3: Validate Django chat API contract + document mock fallback [quick]
└── Task 4: Empty + skeleton + error state components [quick]

Wave 2 (Core chrome — messages + composer + citations, MAX PARALLEL):
├── Task 5: Message primitives (user/assistant/system, citation pills, stamp meta) [visual-engineering]
├── Task 6: Composer (ruled input, mono label, stamp submit, :active, keyboard) [visual-engineering]
├── Task 7: Citations dock / rail (slide-over desktop, bottom-sheet mobile, spring if needed) [visual-engineering]
├── Task 8: Conversation list / history rail (Box 00 manifest style, local state) [quick]

Wave 3 (Wiring — streaming + integration):
├── Task 9: Chat API adapter + SSE streaming harness [quick]
├── Task 10: Wire composer → stream → messages → citations (token-by-token, blur mask) [deep]
├── Task 11: Nav/Closing/AuthModal integration (Launch vs Ask, session bracketing) [quick]

Wave 4 (Polish — a11y + motion + responsive + perf):
├── Task 12: Emil motion pass (stagger 30-80ms, ease-out 150-250ms, reduced-motion) [visual-engineering]
├── Task 13: A11y + keyboard + focus trap + screen-reader audit [quick]
├── Task 14: Responsive + mobile sheet + touch states + adapt audit [quick]
├── Task 15: Perf + build verification (tinted shadows, animate transform/opacity only, no z-spam) [quick]

Wave FINAL (4 parallel reviews, then user okay):
├── Task F1: Plan compliance audit (oracle)
├── Task F2: Code quality + build + lint (unspecified-high)
├── Task F3: Real manual QA — every scenario (unspecified-high + playwright)
└── Task F4: Scope fidelity + visual parity vs landing (deep)
-> Present results -> Get explicit user okay

Critical Path: T1 → T2 → T5 → T10 → T12 → F1-F4
Parallel Speedup: ~62% vs sequential
Max Concurrent: 4 (Waves 1-2)
```

### Dependency Matrix

| Task | Blocked By | Blocks | Can Parallel |
|------|-----------|--------|--------------|
| T1 Tokens | — | T2,T5-T7,T12 | Wave 1 group |
| T2 Shell | T1 | T5-T8,T10 | Wave 1 |
| T3 Contract | T1 | T9,T10 | Wave 1 |
| T4 States | T1 | T10 | Wave 1 |
| T5 Messages | T2 | T10,T12 | Wave 2 |
| T6 Composer | T2 | T10 | Wave 2 |
| T7 Citations | T2 | T10 | Wave 2 |
| T8 History | T2 | T10 | Wave 2 |
| T9 API adapter | T3 | T10 | Wave 3 |
| T10 Wiring | T5-T9 | T12-T15 | Wave 3 |
| T11 Nav integration | T2,T10 | F3 | Wave 3 |
| T12 Motion | T10 | F3 | Wave 4 |
| T13 A11y | T10 | F3 | Wave 4 |
| T14 Responsive | T10 | F3 | Wave 4 |
| T15 Perf/build | T10 | F3 | Wave 4 |

### Agent Dispatch Summary

- **Wave 1**: 4 → T1 `quick`, T2 `visual-engineering`, T3 `quick`, T4 `quick`
- **Wave 2**: 4 → T5 `visual-engineering`, T6 `visual-engineering`, T7 `visual-engineering`, T8 `quick`
- **Wave 3**: 3 → T9 `quick`, T10 `deep`, T11 `quick`
- **Wave 4**: 4 → T12 `visual-engineering`, T13 `quick`, T14 `quick`, T15 `quick`
- **FINAL**: 4 → F1 `oracle`, F2 `unspecified-high`, F3 `unspecified-high`, F4 `deep`

---

## TODOs

- [ ] 1. Extract and share landing tokens for chat (theme continuity lock)

  **What to do**:
  - Read `src/index.css` fully (all :root vars, .eyebrow/.stamp/.rule-double/.ledger-lines/.grain) and `tailwind.config.js`.
  - Ensure `src/index.css` is the single source: export CSS vars (ink, paper, gold, etc.) and class names as comments in `src/chat/theme.ts` or `src/lib/tokens.ts` for JS reference (no duplication of values).
  - Add minimal chat-specific extensions ONLY: `--chat-surface` aliases to --paper/ink, `--chat-accent` = --gold, radius token `12px` (cards) + `999px` (stamps/pills) — lock ONE radius system per Impeccable shape lock.
  - Verify self-hosted fonts (`DM Serif Display`, `IBM Plex Sans`, `JetBrains Mono`) remain applied via index.css; do not re-declare or add new font deps.
  - Document tokens in a short comment block at top of `src/chat/theme.ts` so executor knows what to reuse.

  **Must NOT do**:
  - New color palette, new font, new gradient, pure #000, AI-purple, or any Taste-banned default
  - Duplicate landing tokens into JS constants that drift — reuse CSS vars
  - Add new dependency for theming

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Small, bounded token extraction + file creation, no complex logic
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - `impeccable`: domain overlaps but task is token hygiene, not component craft — defer to visual tasks

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 2,3,4)
  - **Blocks**: Tasks 2,5,6,7,8,12
  - **Blocked By**: None (can start immediately)

  **References**:
  - **Pattern**: `src/index.css:42-50` — :root tokens + body background — reuse exactly
  - **Pattern**: `src/index.css:87-138` — .eyebrow/.stamp/.rule-double/.ledger-lines — reuse class names in chat
  - **API/Type**: `tailwind.config.js` — content globs, no extension needed
  - **Test**: `src/components/Nav.tsx:31-40` — masthead reuse pattern (SVG triangle + wordmark)

  **Acceptance Criteria**:
  - [ ] File `src/chat/theme.ts` or `src/lib/tokens.ts` exists with comment listing landing tokens and two chat aliases
  - [ ] `src/index.css` unchanged or only appended variable aliases (no value drift)
  - [ ] `npm run build` still passes (token file is type-only)

  **QA Scenarios**:
  ```
  Scenario: Token reuse renders same gold
    Tool: Bash (curl) + visual spot
    Preconditions: `npm run build` fresh
    Steps:
      1. Run `grep -n "e8a23a" src/index.css` → expect ≥ 8 hits (gold used)
      2. Run `grep -n "e8a23a" src/chat/theme.ts` → expect 0 hard-coded repeats (only var refs or comment)
      3. Preview build, inspect chat header element computed color of `.stamp` → equals `rgb(232,162,58)`
    Expected Result: Chat uses same gold via CSS var, no hard-coded duplication
    Evidence: .sisyphus/evidence/task-1-token-reuse.log

  Scenario: Negative — new palette rejected
    Tool: Grep
    Steps:
      1. Grep `src/chat` for hex colors other than gold/ink/paper/line → expect none
    Expected Result: No rogue palette introduced
    Evidence: .sisyphus/evidence/task-1-no-new-palette.log
  ```

  **Commit**: NO (groups with Wave 1)
  - Files: `src/chat/theme.ts`

- [ ] 2. App routing + Chat shell chrome (operate frame, masthead, ledger, rail)

  **What to do**:
  - Add routing without new deps: hash-based (`#chat`) or minimal `react-router-dom` if already implied? Prefer hash to stay Ponytail-lazy — add `src/pages/Chat.tsx` or `src/chat/ChatShell.tsx` and mount in `App.tsx` conditional on `location.hash === '#chat'` OR add BrowserRouter with `src/chat/routes.tsx`.
  - Build shell: fixed masthead (reuse `Nav` SVG + wordmark, but Operate variant — no marketing links, only Operator pill + Launch App), left conversation history rail (desktop, collapsible), main chat column, right citations rail (desktop) / bottom sheet (mobile). Use `max-w-6xl mx-auto px-5` rhythm matching landing.
  - Surface: `bg-[#050505]` or `bg-[var(--ink)]`, ledger-lines subtle on empty state only (not full bleed per Theme Lock), grain overlay via `.grain` (z below content).
  - Height: `min-h-[100dvh]` with `h-[100dvh]` for shell (never `h-screen`), nav height ≤80px, single line on desktop.

  **Must NOT do**:
  - Marketing hero inside chat, centered hero, 3-equal-card grids, scroll cues, version labels, locale strips
  - `window.addEventListener('scroll',…)` — use CSS/IntersectionObserver
  - New icon lib — reuse `lucide-react` (already present) for minimal icons (send, panel, close)

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: Layout, rhythm, nav height discipline, operate frame craft
  - **Skills**: `impeccable`, `taste-skill`
    - `impeccable`: Operate mode layout + hierarchy + a11y
    - `taste-skill`: Dial setting (variance 8, motion 6, density 4) + anti-slop
  - **Skills Evaluated but Omitted**:
    - `emil-design-eng`: motion deferred to T12

  **Parallelization**:
  - **Can Run In Parallel**: YES (Wave 1, after T1 token alias)
  - **Parallel Group**: Wave 1
  - **Blocks**: Tasks 5,6,7,8,10,11
  - **Blocked By**: Task 1

  **References**:
  - **Pattern**: `src/App.tsx:12-30` — AuthProvider wrapper + section stack — add chat route alongside
  - **Pattern**: `src/components/Nav.tsx:24-55` — masthead structure to clone for chat (SVG triangle, wordmark)
  - **Pattern**: `src/index.css:193-201` — .grain — apply as shell pseudo
  - **External**: Tailwind grid `lg:grid-cols-12` pattern from `src/components/Pipeline.tsx:52` — adapt to 12-col chat layout

  **Acceptance Criteria**:
  - [ ] Route `#chat` (or `/chat`) renders ChatShell without breaking landing hash anchors (#shift etc.)
  - [ ] Shell header visually matches landing Nav (same SVG, same tracking, same gold) — side-by-side screenshot Δ < subtle
  - [ ] Responsive: desktop shows 2 rails, mobile shows single column + bottom sheet trigger, no horizontal overflow
  - [ ] `npm run build` passes

  **QA Scenarios**:
  ```
  Scenario: Chat shell visual parity
    Tool: Playwright (or preview + screenshot)
    Preconditions: `npm run build && npx vite preview --port 4173` running
    Steps:
      1. Open `/` → screenshot header (`task-2-landing-header.png`)
      2. Open `/#chat` (or `/chat`) → screenshot chat header (`task-2-chat-header.png`)
      3. Assert both headers: SVG fill #e8a23a, text "Zenith", mono sub "Form Z-1" or "Box 00" variant, height ≤80px
    Expected Result: Visual continuity confirmed
    Evidence: .sisyphus/evidence/task-2-header-parity.png

  Scenario: Mobile rail collapses gracefully
    Tool: Playwright emulate 390x844
    Steps:
      1. Resize to 390px → assert left history rail hidden, citations become bottom-sheet trigger visible
      2. Tap trigger → sheet opens, no body scroll leak
    Expected Result: No overflow, no 2-line nav on desktop, mobile usable
    Evidence: .sisyphus/evidence/task-2-mobile.png
  ```

  **Commit**: NO (groups with Wave 1)
  - Files: `src/chat/ChatShell.tsx`, `src/pages/Chat.tsx` or `src/App.tsx` edit

- [ ] 3. Validate Django chat API contract + document mock fallback

  **What to do**:
  - Read `src/lib/api.ts` fully; probe live backend if reachable: `GET /api/auth/me/`, `GET /api/auth/csrf/`, attempt `POST /api/chat/` or `/api/ask/` with dummy body, capture status + shape. Use `curl -i` with `credentials` cookie flow.
  - Document contract in `docs/api-contract.md` or `src/chat/api/README.md`: endpoint path, method, headers (X-CSRFToken), request shape (question, history, region?), response shape (SSE vs JSON, citation schema `{id, doc, page, url}`), auth requirement.
  - Produce typed mock fallback `src/chat/api/mock.ts` returning SSE-like async generator with fake citations (DGFT p.2, CBIC p.312) so UI can be built without backend. Adapter `src/chat/api/chat.ts` exports `askStream(question, opts)` that tries real fetch then falls back to mock when `!ok`.
  - Add one `demo()` self-check: parse a mock SSE chunk, assert citation extraction preserves page numbers.

  **Must NOT do**:
  - Hardcode backend URL — reuse `APP_URL` + relative `/api` proxy pattern
  - invent citation schema that diverges from landing's "[1] DGFT Notification 62 — p.2" format — keep identical pills
  - Add zod validation unless needed — keep minimal `if (!data) throw`

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Probe + doc + typed mock, no UI
  - **Skills**: []
    - Reason: Backend contract mapping, Ponytail-lazy fallback

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with T1,T2,T4)
  - **Blocks**: Tasks 9,10
  - **Blocked By**: Task 1 (for token reuse awareness)

  **References**:
  - **Pattern**: `src/lib/api.ts:38-77` — post/get + ensureCsrf + credentials:include — reuse for chat
  - **Pattern**: `src/components/BeforeAfter.tsx:235-243` — citation pills shape to preserve
  - **API**: `vite.config.ts:9-13` — proxy same-origin for cookies

  **Acceptance Criteria**:
  - [ ] Contract doc exists and lists real probing results (or "backend unreachable — mock fallback active")
  - [ ] `src/chat/api/chat.ts` exports `askStream` with real→mock fallback and types `Citation {id, doc, page}`
  - [ ] Demo self-check passes: `npx tsx src/chat/api/chat.ts` or `npm run build` not broken

  **QA Scenarios**:
  ```
  Scenario: Contract probing
    Tool: Bash curl
    Steps:
      1. `curl -i http://127.0.0.1:8000/api/auth/me/ -H "Cookie: ..."` (or via vite proxy `/api/auth/me/`) → assert status 200 or 401, JSON shape `{user}` 
      2. Trial `curl -X POST /api/chat -H "X-CSRFToken: $(getCookie)"` with `{"question":"HS code for wheat"}` → log shape to evidence
    Expected Result: Documented endpoint or confirmed fallback needed
    Evidence: .sisyphus/evidence/task-3-contract.log

  Scenario: Mock stream parses
    Tool: Bash (node)
    Steps:
      1. `node -e "import('./src/chat/api/chat.ts').then(m=>m.demo())"` or run `npx tsx`
      2. Assert output contains `DGFT Notification 62 — p.2`
    Expected Result: Mock cite format matches landing
    Evidence: .sisyphus/evidence/task-3-mock.log
  ```

  **Commit**: NO (groups with Wave 1)
  - Files: `docs/api-contract.md`, `src/chat/api/chat.ts`, `src/chat/api/mock.ts`

- [ ] 4. Empty + skeleton + error states (operate polish, no blank screens)

  **What to do**:
  - Build `src/chat/components/EmptyState.tsx`: Box 00 manifest style — ruled invoice, mono label "Box 00 · New clearance", prompt examples as dotted leaders (like Stats) plus one stamp CTA "Start clearance". Uses `.rule-double`, `.eyebrow`, `.stamp` — no illustration.
  - `src/chat/components/Skeleton.tsx`: skeleton matching final message layout (avatar pill, two-line text block, citation pill row) with `animate-pulse bg-white/[0.04]` — shape-identical to real message.
  - `src/chat/components/ErrorState.tsx`: inline error (not toast for persistent), mono "Field error" + retry stamp button with `scale(0.97)` active.
  - All three must respect Theme Lock (dark only) and one radius system.

  **Must NOT do**:
  - Generic "No messages yet" or "Jane Doe" slop
  - Spinning purple loader or neon glow
  - `border-t+b` on every skeleton row

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Small composed state components
  - **Skills**: `impeccable`
    - Reason: Empty/error pattern craft

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1
  - **Blocks**: Task 10 (wiring shows these states)
  - **Blocked By**: Task 1

  **References**:
  - **Pattern**: `src/components/Stats.tsx:28-51` — ruled manifest with dotted leaders — reuse for empty prompts
  - **Pattern**: `src/components/AuthModal.tsx:58` — field utility style for empty input affordance
  - **Pattern**: `src/components/Closing.tsx:13-14` — ledger-lines bg — optional subtle on empty only

  **Acceptance Criteria**:
  - [ ] Three components exist, each <80 lines, reuse landing classes
  - [ ] Empty shows 3 example prompts (HS code, duty rate, export procedure) with gold values

  **QA Scenarios**:
  ```
  Scenario: Empty state composition
    Tool: Playwright
    Steps:
      1. Open chat with empty history → screenshot
      2. Assert eyebrow "Box 00" visible, 3 prompts visible, stamp CTA visible, no plain placeholder text
    Expected Result: Empty reads as dossier, not blank
    Evidence: .sisyphus/evidence/task-4-empty.png

  Scenario: Skeleton matches message shape
    Tool: Playwright
    Steps:
      1. Trigger loading (throttle mock to 2s) → screenshot skeleton
      2. Assert skeleton rows = same height as real message rows after load
    Expected Result: No layout shift between skeleton and content (CLS <0.1)
    Evidence: .sisyphus/evidence/task-4-skeleton.png
  ```

  **Commit**: YES (Wave 1 closes here)
  - Message: `feat(chat): tokens + shell + contract + states`
  - Files: `src/chat/theme.ts`, `src/chat/ChatShell.tsx`, `src/App.tsx`, `docs/api-contract.md`, `src/chat/api/*`, `src/chat/components/EmptyState.tsx`, `src/chat/components/Skeleton.tsx`, `src/chat/components/ErrorState.tsx`
  - Pre-commit: `npm run build`

- [ ] 5. Message primitives (user / assistant / system, citation pills, stamp meta)

  **What to do**:
  - Create `src/chat/components/Message.tsx` with variants: `role=user` (right-aligned, paper-ish pill on ink), `role=assistant` (left, dossier card `border border-[#e8a23a]/25 bg-[#0d0b08]` mirroring `BeforeAfter AfterStage`), `role=system` (mono centered).
  - Assistant body: prose `text-sm leading-relaxed text-[#f5f1e8]/90`, citations inline `sup` gold `[1]` linking to dock, citation pills `font-mono-j text-[10px] border border-white/15 rounded-full px-3 py-1.5` exactly as BeforeAfter.
  - Meta row: mono "1 LLM call · 1.4s · grounded" + `Cleared · Zenith · 1.4s` stamp rotated -8deg scaled 0.95→1 (no scale(0)).
  - Animate enter: Emil `scale(0.95)+opacity 0 → scale(1)+opacity 1` 180ms ease-out, stagger 50ms between consecutive assistant messages. Use `useInView` or CSS `transition` (no rAF state loop).

  **Must NOT do**:
  - Bubbles with pure black or saturated accent beyond gold, gradient text on body, `transition: all`
  - Markdown-heavy generic prose without citation parity

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: Core operate readability + materiality (tinted shadows, not black)
  - **Skills**: `impeccable`, `taste-skill`
  - **Skills Evaluated but Omitted**:
    - `emil-design-eng`: enter motion lightweight, handled without spring import

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 6,7,8)
  - **Blocks**: Tasks 10,12
  - **Blocked By**: Task 2

  **References**:
  - **Pattern**: `src/components/BeforeAfter.tsx:206-261` — AfterStage card + citation pills + stamp — clone exactly
  - **Pattern**: `src/components/Reveal.tsx:4-23` — reveal wrapper for stagger
  - **API**: `src/chat/api/chat.ts:Citation` — pill data contract

  **Acceptance Criteria**:
  - [ ] Message renders citation pills identical to AfterStage (same border, padding, mono 10px)
  - [ ] Assistant card shadow is tinted `rgba(232,162,58,0.28)` not pure black
  - [ ] Enter animation is transform+opacity only, <200ms

  **QA Scenarios**:
  ```
  Scenario: Assistant message with citations
    Tool: Playwright
    Steps:
      1. Render assistant message with fixture: body + 3 citations
      2. Assert pills count 3, each contains "p." + page number, clicking pill scrolls to dock entry
      3. Assert stamp visible, rotated -8deg
    Expected Result: Dossier card reads premium, not generic chat bubble
    Evidence: .sisyphus/evidence/task-5-message.png

  Scenario: No purple bubble negative
    Tool: Grep
    Steps:
      1. Grep Message.tsx for `bg-purple|gradient|#000000|scale(0)` → expect 0 hits
    Expected Result: Anti-slop clean
    Evidence: .sisyphus/evidence/task-5-no-slop.log
  ```

  **Commit**: NO (groups with Wave 2)
  - Files: `src/chat/components/Message.tsx`

- [ ] 6. Composer (ruled input, mono label, stamp submit, keyboard discipline)

  **What to do**:
  - Create `src/chat/components/Composer.tsx`: container `rounded-2xl border border-white/10 bg-[#0a0906]` (Radius Lock 12px, not mixed), inner textarea `bg-transparent` with label ABOVE (mono "Box 00 · Question" `tracking-[0.25em] uppercase`, never placeholder-as-label), placeholder `Ask about HS codes…` in `white/25`.
  - Submit: `.stamp` gold button "File clearance →" with `hover:-rotate-1 hover:text-black hover:bg-[#e8a23a]`, `:active scale(0.97)`, disabled `opacity-50 pointer-events-none` while streaming.
  - Behavior: Enter sends, Shift+Enter newline; never animate keyboard-initiated sends (Emil §1). Focus visible gold outline, `max-h` with autosize.
  - Affix meta: "KB + Live Web" pill + "Session secured by Django · HttpOnly cookie" mono footer.

  **Must NOT do**:
  - Placeholder as label, CTA wrap at desktop, button without :active, Inter, duplicate CTA intent
  - Animating compositor width/height — only transform/opacity

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: Form pattern + tactile feedback + a11y
  - **Skills**: `impeccable`
  - **Skills Evaluated but Omitted**:
    - `taste-skill`: already applied at shell

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2
  - **Blocks**: Task 10
  - **Blocked By**: Task 2

  **References**:
  - **Pattern**: `src/components/AuthModal.tsx:108-121` — label above input + field class `w-full bg-[#0a0906] border rounded-md ... focus:border-[#e8a23a]`
  - **Pattern**: `src/components/Pipeline.tsx:108-113` — mono artifact row style for meta pill
  - **Pattern**: Emil Buttons must feel responsive `scale(0.97)` — add to stamp

  **Acceptance Criteria**:
  - [ ] Label above input, not placeholder; :active scale present; Enter/Shift+Enter correct
  - [ ] Composer max width `max-w-3xl` centered, never full bleed beyond `65ch` readable line length

  **QA Scenarios**:
  ```
  Scenario: Keyboard send discipline
    Tool: Playwright
    Steps:
      1. Focus composer, type "wheat quota" → press Enter → assert message appears, input clears
      2. Type "line1" → Shift+Enter → assert newline inserted, not sent; then Enter → sent
      3. Assert no animation on send (message appears via opacity+transform enter, but composer itself does not animate)
    Expected Result: Keyboard respect per Emil §1
    Evidence: .sisyphus/evidence/task-6-composer.png

  Scenario: Reduced-motion composer
    Tool: Playwright emulate prefers-reduced-motion
    Steps:
      1. Focus composer, tab to submit → focus ring gold, no scale animation beyond :active
    Expected Result: A11y intact
    Evidence: .sisyphus/evidence/task-6-a11y.log
  ```

  **Commit**: NO (groups with Wave 2)
  - Files: `src/chat/components/Composer.tsx`

- [ ] 7. Citations dock / rail (slide-over desktop, bottom-sheet mobile)

  **What to do**:
  - Create `src/chat/components/CitationsDock.tsx`: desktop = right rail `w-[360px] xl:w-[400px] border-l border-white/10 bg-[#0d0b08]` with header `eyebrow "Box 03 · Sources" + rule-double`, list of source rows (doc name, page, confidence) with dotted leader pattern from Stats; click citation scrolls to pill.
  - Mobile = bottom sheet with drag handle, `translateY` + `opacity` only, spring-bounce `0.2` if Motion added; otherwise CSS `transition: transform 200ms cubic-bezier(0.32,0.72,0,1)` (iOS drawer). Backdrop `bg-black/40 backdrop-blur-sm`, click to close, `Esc` to close.
  - Open state tied to `useState` + focus trap when open (first focusable = close button). Use `transform-origin` correctly (sheet from bottom, rail from right).

  **Must NOT do**:
  - Popover `transform-origin: center` — must be anchor-aware per Emil
  - `scale(0)` sheet enter, or `window.scroll` listener
  - Custom cursor or neon glow on rail

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: Operate rail — scanability, origin-aware motion
  - **Skills**: `impeccable`, `emil-design-eng`
    - `emil`: origin-aware popover, drawer curve, spring interruption handling

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2
  - **Blocks**: Task 10
  - **Blocked By**: Task 2

  **References**:
  - **Pattern**: `src/components/Stats.tsx:34-46` — dotted leader rows — reuse for source rows
  - **Pattern**: `src/index.css:140-154` — route-line / durable motion tokens — adapt drawer curve
  - **Pattern**: Emil drawer: `--ease-drawer: cubic-bezier(0.32,0.72,0,1)` and `@starting-style` for enter

  **Acceptance Criteria**:
  - [ ] Desktop rail persistent, mobile sheet bottom-anchored and dismissible via drag velocity >0.11 or Esc
  - [ ] Focus trap active when sheet open; body scroll locked only when sheet open (no leak after close)

  **QA Scenarios**:
  ```
  Scenario: Desktop rail + mobile sheet
    Tool: Playwright
    Steps:
      1. Desktop 1280px: open citations → rail slides from right, no scale(0), content behind not scrollable? (behind may scroll)
      2. Mobile 390px: trigger citations → sheet slides up from bottom, backdrop appears
      3. Press Esc → sheet closes, focus returns to trigger
    Expected Result: Origin-aware, interruptible, accessible
    Evidence: .sisyphus/evidence/task-7-dock.png
  ```

  **Commit**: NO (groups with Wave 2)
  - Files: `src/chat/components/CitationsDock.tsx`

- [ ] 8. Conversation list / history rail (Box 00 manifest, local state)

  **What to do**:
  - Create `src/chat/components/HistoryRail.tsx`: collapsible left rail (desktop `w-[280px]`), header `rule-double` with "Conversations · Form Z-1", list of past threads (mock local state `useState<{id,title,date}[]>` persisted to `localStorage` under `zenith:history`).
  - Row style: `py-3 border-b border-white/10` hover `bg-white/[0.02]`, title `text-sm text-white/80`, date `font-mono-j text-[10px] text-white/35`, active row shows gold left accent `border-l-2 border-[#e8a23a]`.
  - Empty: single dormant row "No clearances yet — start above". Actions: new chat (stamp), delete (hover reveal). No tabs, no second accent.

  **Must NOT do**:
  - Second accent color, version footer, city/weather strip, duplicate CTA
  - Heavy client DB — keep Ponytail localStorage only

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Simple list + localStorage, not main craft surface

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2
  - **Blocks**: Task 10
  - **Blocked By**: Task 2

  **References**:
  - **Pattern**: `src/components/Stats.tsx:34-51` — hover row + dotted leader — adapt to history row
  - **Pattern**: `src/auth/AuthContext.tsx:42-50` — cancelled flag pattern — adapt for localStorage hydration

  **Acceptance Criteria**:
  - [ ] History persists across reload via localStorage
  - [ ] Active conversation highlighted with gold accent, not background fill

  **QA Scenarios**:
  ```
  Scenario: History persistence
    Tool: Playwright + localStorage
    Steps:
      1. Create new chat "wheat quota" → refresh → assert row still present
      2. Delete row → assert removed from DOM and localStorage
    Expected Result: Local persistence works without backend
    Evidence: .sisyphus/evidence/task-8-history.png
  ```

  **Commit**: YES (Wave 2 closes)
  - Message: `feat(chat): message/composer/citations/history chrome`
  - Files: `src/chat/components/Message.tsx`, `src/chat/components/Composer.tsx`, `src/chat/components/CitationsDock.tsx`, `src/chat/components/HistoryRail.tsx`
  - Pre-commit: `npm run build`

- [ ] 9. Chat API adapter + SSE streaming harness (credentials + CSRF, one swap surface)

  **What to do**:
  - Create `src/chat/api/stream.ts` (or extend `chat.ts`): `async function* askStream(question: string, opts?: {history?: Message[]})` — calls `fetch('/api/chat/stream/' or '/api/ask/', {method:'POST', credentials:'include', headers:{'Content-Type':'application/json','X-CSRFToken': await ensureCsrf()}, body: JSON.stringify({question})})`.
  - Parse SSE: read `res.body.getReader()`, `TextDecoder`, split by `\n\n`, handle `data: {delta, citations, done, error}`. Fallback to mock generator if `!res.ok` or `!res.body`. Yield `{delta, citations?}` chunks.
  - Types: `export type Citation = {id:string, doc:string, page:string|number, url?:string, confidence?:number}` aligning with landing pills. Export `ApiError` handling (surface as inline ErrorState, not toast for persistent).
  - Add `demo()` / `if (import.meta.vitest)` self-check: feed synthetic SSE string, assert parser extracts 2 citations and concatenated text equals fixture.

  **Must NOT do**:
  - Add fetch lib (axios) — stdlib `fetch` only per Ponytail rung 3
  - Swallow errors with empty catch — surface via return `{ok:false, error}`
  - Hardcode endpoint without proxy awareness

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Straight fetch + SSE parse, no UI
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (Wave 3 start)
  - **Parallel Group**: Wave 3 (with Task 10,11 after)
  - **Blocks**: Task 10
  - **Blocked By**: Task 3

  **References**:
  - **Pattern**: `src/lib/api.ts:38-51` — ensureCsrf + post with X-CSRFToken — copy exactly
  - **Pattern**: `src/auth/AuthContext.tsx:60-68` — ok/data branching — reuse for stream
  - **External**: SSE spec `text/event-stream`, `data:` prefix, double newline framing

  **Acceptance Criteria**:
  - [ ] Parser handles real SSE and mock string, extracts deltas + citations, stops on `done:true`
  - [ ] Adapter correctly includes `credentials:include` and CSRF header
  - [ ] Build passes; adapter <120 lines

  **QA Scenarios**:
  ```
  Scenario: SSE parse with mock
    Tool: Bash (node)
    Steps:
      1. `node --loader tsx src/chat/api/stream.ts` runs demo → assert output text === "above 10,000 MT …" and citations len 2
    Expected Result: Parser faithful to contract
    Evidence: .sisyphus/evidence/task-9-sse.log

  Scenario: Fallback when backend down
    Tool: Bash curl
    Steps:
      1. Stop Django (or block 8000) → call askStream("test") → assert falls back to mock stream and still yields citations
    Expected Result: UI not bricked offline
    Evidence: .sisyphus/evidence/task-9-fallback.log
  ```

  **Commit**: NO (groups with Wave 3)
  - Files: `src/chat/api/stream.ts`, `src/chat/api/chat.ts`

- [ ] 10. Wire composer → stream → messages → citations (token-by-token, blur mask, one LLM call story)

  **What to do**:
  - Create `src/chat/hooks/useChat.ts`: state `messages: {id, role, content, citations}[]`, `streaming: boolean`, `streamBuffer: string`, `appendUser`, `startStream`, `cancelStream`. On `startStream`, push user message, create assistant placeholder, iterate `for await (const chunk of askStream(q))` appending `delta` to placeholder, collecting `citations` on final chunk, update dock.
  - Wire in `ChatShell`: `Composer onSubmit → useChat.startStream`, render `<Message>` list with last assistant streaming via blur mask (`filter: blur(2px)` during transition then `blur(0)` — keep <12px) if crossfade feels off per Emil. Show skeleton only before first delta, then stream.
  - Disable composer submit while `streaming`, show "Filing…" mono label (reuse AuthModal busy pattern). Esc cancels stream.
  - Persist conversation to `HistoryRail` localStorage on done.

  **Must NOT do**:
  - Animate width/height/padding during stream — only transform/opacity
  - `requestAnimationFrame` loop touching React state — stream drives state via async iter, not rAF
  - Store secrets — messages are plain text only

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Most complex orchestration, streaming + state + dock sync + cancel
  - **Skills**: `impeccable`
    - Reason: Operate wiring, loading vs streaming vs error branching

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 3 sequential after T5-T9
  - **Blocks**: Tasks 11,12,13,14,15
  - **Blocked By**: Tasks 5,6,7,8,9

  **References**:
  - **Pattern**: `src/auth/AuthContext.tsx:60-78` — signIn pattern (ok/data → setUser) — adapt to streaming incremental
  - **Pattern**: `src/components/AuthModal.tsx:44-56` — busy toggle + error map — reuse for composer busy
  - **Pattern**: `src/components/BeforeAfter.tsx:235-243` — final citation pill row construction — reuse

  **Acceptance Criteria**:
  - [ ] Sending message streams deltas token-by-token into assistant message (visible incremental rendering)
  - [ ] Citations appear as pills inline + in dock after stream done, clickable to dock entry
  - [ ] Streaming can be cancelled via Esc or new message, no orphan reader leak (abort controller)

  **QA Scenarios**:
  ```
  Scenario: Happy streaming
    Tool: Playwright
    Steps:
      1. Open chat empty → type "wheat quota" → hit Enter
      2. Assert user message appears immediately, assistant placeholder shows skeleton briefly then text appears incrementally (wait 1.4s)
      3. Assert final assistant text contains pinned number (e.g., "10,000 MT") and 2 citation pills + meta "1 LLM call · 1.4s"
      4. Click citation pill → dock highlights corresponding row
    Expected Result: Grounded, cited, verified — landings promise delivered
    Evidence: .sisyphus/evidence/task-10-stream.png

  Scenario: Error / abort
    Tool: Playwright
    Steps:
      1. Mock backend to return 500 → send → assert ErrorState inline with retry stamp, composer re-enabled
      2. Start stream then press Esc → assert stream stops, partial text preserved, composer enabled
    Expected Result: Graceful, no toast spam
    Evidence: .sisyphus/evidence/task-10-error.png
  ```

  **Commit**: NO (groups with Wave 3)
  - Files: `src/chat/hooks/useChat.ts`, `src/chat/ChatShell.tsx` edits

- [ ] 11. Nav/Closing/AuthModal integration (session continuity across marketing → chat)

  **What to do**:
  - Extend `Nav` and `Closing` CTAs: authenticated `Launch Zenith` now routes to internal `#chat` (or `/chat`) instead of external `APP_URL` when chat lives inside landing; keep external as fallback if `VITE_APP_URL` set and chat-in-landing disabled. Update `Hero` similarly.
  - Ensure `AuthModal` after `signIn/signUp` redirects or opens chat (if user arrived via chat gate). Handle `loading` state in shell: while `AuthContext.loading` true, show skeleton not gated content.
  - If unauthenticated user hits chat composer, gate with AuthModal `openAuth('signup')` then resume pending question after success (store pending in ref).

  **Must NOT do**:
  - Break existing hash anchors (#shift/#pipeline) — test that Nav links still smooth-scroll on landing
  - Duplicate auth logic — reuse `AuthContext` exclusively

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Small wiring edits, no new components

  **Parallelization**:
  - **Can Run In Parallel**: YES (after T10)
  - **Parallel Group**: Wave 3
  - **Blocks**: F3
  - **Blocked By**: Tasks 2,10

  **References**:
  - **Pattern**: `src/components/Nav.tsx:13-15` — useAuth branching
  - **Pattern**: `src/components/Hero.tsx:148-164` — conditional Launch vs Ask — update to internal route
  - **Pattern**: `src/components/Closing.tsx:35-51` — same conditional CTA pattern

  **Acceptance Criteria**:
  - [ ] Landing CTAs point to internal chat when built; external APP_URL only when env signals standalone
  - [ ] Unauthenticated composer submit opens AuthModal and resumes after sign-in

  **QA Scenarios**:
  ```
  Scenario: Auth gate resume
    Tool: Playwright
    Steps:
      1. Logout → open chat → type "HS code 8421" → Enter → assert AuthModal opens
      2. Sign up success → assert modal closes and message auto-sends (appears in list) without re-typing
    Expected Result: No lost question, session continuity
    Evidence: .sisyphus/evidence/task-11-auth-gate.png
  ```

  **Commit**: YES (Wave 3 closes)
  - Message: `feat(chat): streaming adapter + wiring + nav integration`
  - Files: `src/chat/hooks/useChat.ts`, `src/components/Nav.tsx`, `src/components/Hero.tsx`, `src/components/Closing.tsx`, `src/chat/ChatShell.tsx`
  - Pre-commit: `npm run build`

- [ ] 12. Emil motion pass (motivated, interrupted, reduced-motion-aware)

  **What to do**:
  - Audit every animation against Emil framework §1-4: keep only occasional (message enter, dock slide, citation stamp reveal). Remove any hover micro-animation on composer that fires tens/day at full intensity.
  - Implement with CSS `transition: transform 180ms cubic-bezier(0.23,1,0.32,1), opacity 180ms` and `filter` blur mask only during crossfade (<12px). Stagger assistant stream entry with 50ms steps, not 120ms+.
  - Use `useSpring(bounce 0.2)` only if spring interruption needed for sheet drag; otherwise CSS drawer curve. Add `@media (hover:hover) and (pointer:fine)` guard for hover scales.
  - Honor `prefers-reduced-motion: reduce` — message enters as `fade 0.2s ease` only, dock becomes instant, grain/route animations disabled already. Verify via `index.css:252-265` extended.

  **Must NOT do**:
  - `ease-in` on any UI, `scale(0)` entries, `transition: all`, animating keyboard sends
  - Duration >300ms on any operable element, or `requestAnimationFrame` state loops

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: Motion is taste — precise easing, spring, and restraint
  - **Skills**: `emil-design-eng`
    - Reason: Emil decision framework is the spec

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 4 (with T13,T14,T15)
  - **Blocks**: F3
  - **Blocked By**: Task 10

  **References**:
  - **Pattern**: `src/index.css:252-265` — reduced-motion kill switch — extend to chat
  - **Pattern**: Emil §3: `--ease-out: cubic-bezier(0.23,1,0.32,1)`, drawer `cubic-bezier(0.32,0.72,0,1)`
  - **Pattern**: `src/hooks/useInView.ts` — already uses IntersectionObserver correctly — reuse, do not add scroll listeners

  **Acceptance Criteria**:
  - [ ] All chat animations are transform/opacity only, <200ms, ease-out, reduced-motion fallback present
  - [ ] No `window.addEventListener('scroll'` or `requestAnimationFrame` state loop in `src/chat`

  **QA Scenarios**:
  ```
  Scenario: Motion restraint
    Tool: Grep + Playwright reduced-motion
    Steps:
      1. `grep -R "window.addEventListener('scroll'" src/chat` → 0 hits; grep "requestAnimationFrame" → 0 state hits (allow canvas guard but not chat)
      2. Enable prefers-reduced-motion → send message → assert messages appear with only fade, dock slides instantly
    Expected Result: Taste restraint enforced, a11y intact
    Evidence: .sisyphus/evidence/task-12-motion.png
  ```

  **Commit**: NO (groups with Wave 4)
  - Files: `src/chat/components/*`, `src/index.css` (if needed for reduced-motion)

- [ ] 13. A11y + keyboard + focus trap + screen-reader audit (impeccable harden)

  **What to do**:
  - Labels above every input (already), `aria-label` on icon-only buttons (close, history toggle), `role="dialog" aria-modal="true"` on sheet/dock when overlay, `role="log" aria-live="polite"` on message list for streaming (polite, not assertive).
  - Focus trap in sheet when open (first focusable = close, cycle includes composer when sheet open?). On close return focus to trigger. Tab order: composer → submit → history → citations.
  - Keyboard: `Esc` closes sheet/history/dock, `Enter` sends, `Shift+Enter` newline, `Ctrl/Cmd+K` focuses composer (native affordance). Minimum contrast: `text-white/65` on `#050505` → verify AAA, `focus-visible` gold outline already in index.css.
  - Screen-reader: announcements for "Answer streamed with 3 sources" on done, not per-token.

  **Must NOT do**:
  - Placeholder as label, toast for persistent error, decorative dots without semantic state
  - Remove focus styles — must keep gold outline

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Systematic a11y checklist, no new visuals
  - **Skills**: `impeccable`
    - Reason: Harden category

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 4
  - **Blocks**: F3
  - **Blocked By**: Task 10

  **References**:
  - **Pattern**: `src/components/AuthModal.tsx:62-67` — role dialog + Escape handler — reuse for sheet
  - **Pattern**: `src/index.css:66-70` — :focus-visible gold — verify applies to chat inputs/buttons
  - **External**: WAI-ARIA log pattern for streaming regions

  **Acceptance Criteria**:
  - [ ] axe-like manual audit: no missing labels, all icon buttons have aria-label, no focus loss on sheet open/close
  - [ ] Streaming announces completion once, not per-token

  **QA Scenarios**:
  ```
  Scenario: Focus trap
    Tool: Playwright keyboard
    Steps:
      1. Open citations sheet → Tab 3 times → assert focus stays inside sheet
      2. Press Esc → sheet closes → focus returns to citations trigger button
    Expected Result: No focus escape per Emil popover rule
    Evidence: .sisyphus/evidence/task-13-a11y.png
  ```

  **Commit**: NO (groups with Wave 4)
  - Files: `src/chat/components/*` (a11y attrs)

- [ ] 14. Responsive + mobile sheet + touch states + adapt audit

  **What to do**:
  - Breakpoints: `sm 640 md 768 lg 1024 xl 1280`. Collapse: left history rail hidden <1024 (hamburger `Menu` that actually works now, unlike dead Nav button), right citations rail becomes bottom sheet <1024. Composer stays fixed bottom on mobile with `safe-area-inset-bottom`.
  - Touch: `:active scale(0.97)` on all stamps, `hover` guarded by `@media (hover:hover) and (pointer:fine)` per Emil, tap targets ≥44px.
  - Grid: use CSS Grid `grid-cols-12` for shell, not flex math `w-[calc(...)]`. Letter-spacing restraint: no split-header pattern.
  - Test `min-h-[100dvh]` vs `h-screen` — fix any 100vh iOS bar jitter.

  **Must NOT do**:
  - Two-line nav at desktop, `h-screen` for shell, flex-math gutters
  - Over-wide reading lines >65ch — cap message prose to `max-w-[65ch]`

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Responsive grid + touch, systematic
  - **Skills**: `impeccable`
    - Reason: Adapt category

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 4
  - **Blocks**: F3
  - **Blocked By**: Task 10

  **References**:
  - **Pattern**: `src/components/Nav.tsx:95-97` — dead Menu now made functional for chat — reuse lucide Menu icon
  - **Pattern**: Taste §3.D — never `h-screen`, use `min-h-[100dvh]`
  - **Pattern**: `src/components/Regions.tsx:48-56` — responsive grid col-span handling

  **Acceptance Criteria**:
  - [ ] Mobile composer not obscured by sheet, safe-area respected, no horizontal scroll at 390px
  - [ ] Tap targets pass 44px, hover scales not firing on touch-only

  **QA Scenarios**:
  ```
  Scenario: Mobile full journey
    Tool: Playwright devices iPhone 14 + iPad
    Steps:
      1. iPhone 390px: open chat, trigger history drawer, send message, open citations sheet, close via drag velocity >0.11
      2. Assert composer visible throughout, no overlap, sheet damps at boundaries
    Expected Result: Operate on thumb, not just mouse
    Evidence: .sisyphus/evidence/task-14-mobile.png
  ```

  **Commit**: NO (groups with Wave 4)
  - Files: `src/chat/*` responsive edits

- [ ] 15. Perf + build verification (tinted shadows, animate only transform/opacity, no z-spam)

  **What to do**:
  - Remove any `z-[100]` spam (shell should use `z-10/20/30` layered correctly, grain already `z-90`). Tint shadows to `rgba(232,162,58,0.12)` or `rgba(5,5,5,0.6)`, never pure black drop.
  - Ensure no `padding/margin/height/width` animation — audit `transition` props explicitly (`transition: transform 180ms, opacity 180ms`).
  - Check bundle: `npm run build` + `npx vite build --debug` — chat code-split via `lazy(() => import('./chat/ChatShell'))` if shell >80kb, otherwise keep single chunk to stay Ponytail-lazy (measure before splitting).
  - Verify LCP <2.5s for chat route (no large higgs.ai images in chat — use tiny placeholders), INP <200ms (composer Enter→message <100ms before stream).

  **Must NOT do**:
  - CSS variables changed on parent driving recalc for children — update `transform` directly per Emil perf rule
  - New heavy dep for perf — use stdlib + CSS

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Build/perf audit, bounded

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 4
  - **Blocks**: F3
  - **Blocked By**: Task 10

  **References**:
  - **Pattern**: Emil Performance Rules — only transform/opacity, CSS variables inheritable caution, WAAPI for programmatic if needed
  - **Pattern**: `src/index.css:193-201` — grain already demonstrates correct fixed layer perf

  **Acceptance Criteria**:
  - [ ] `npm run build` passes, no z-spam above `z-50` except grain, no width/height transitions in `src/chat`
  - [ ] Composer keypress latency <150ms measured via Playwright trace

  **QA Scenarios**:
  ```
  Scenario: Perf audit
    Tool: Bash
    Steps:
      1. `grep -R "transition: all" src/chat` → 0 hits; `grep -R "z-\[.*\]" src/chat` → no z >50 except grain
      2. `npm run build` → assert dist size delta <50kb vs before (landing only)
    Expected Result: Premium feel without perf debt
    Evidence: .sisyphus/evidence/task-15-perf.log
  ```

  **Commit**: YES (Wave 4 closes)
  - Message: `feat(chat): a11y motion responsive perf polish`
  - Files: `src/chat/**/*`, `src/index.css`, `src/App.tsx`
  - Pre-commit: `npm run build && grep -R "console.log" src/chat` → 0

---

## Final Verification Wave (MANDATORY — after ALL implementation tasks)

> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results and get explicit "okay" before completing.

- [ ] F1. **Plan Compliance Audit** — `oracle`
  Read plan end-to-end. For each Must Have: verify file exists + visually matches landing (read src/index.css vars, compare header SVG, stamp class). For each Must NOT Have: grep for forbidden (`border-t.*border-b`, `scale(0)`, `window.addEventListener('scroll'`, `Inter`, `console.log`, pure `#000000`). Check evidence in `.sisyphus/evidence/`.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [ ] F2. **Code Quality Review** — `unspecified-high`
  Run `npx tsc --noEmit` + `npm run build`. Review changed files for `as any`/`@ts-ignore`, empty catch, unused imports, z-index spam. Check Ponytail: no new dep without need, shortest diff, no unrequested abstraction.
  Output: `Build [PASS/FAIL] | Lint [PASS/FAIL] | Files [N clean/N issues] | VERDICT`

- [ ] F3. **Real Manual QA** — `unspecified-high` (+ `playwright` if available)
  Start from clean state. Execute every QA scenario (happy + error) from T5-T15. Test cross-task: send message → stream → citations dock opens → mobile sheet. Test empty, invalid, rapid sends. Save to `.sisyphus/evidence/final-qa/`.
  Output: `Scenarios [N/N pass] | Integration [N/N] | Edge Cases [N tested] | VERDICT`

- [ ] F4. **Scope Fidelity + Visual Parity** — `deep`
  Diff `git diff` vs plan. Verify 1:1 — every TODO built, nothing beyond chat scope, no landing-only files touched except tokens/routing. Screenshot landing header vs chat header side-by-side, assert: same SVG, same gold, same paper, same mono tracking, same rule-double. Flag contamination.
  Output: `Tasks [N/N compliant] | Visual Parity [PASS/FAIL] | Contamination [CLEAN/N] | VERDICT`

---

## Commit Strategy

- **Wave 1**: `feat(chat): tokens + shell + contract + states` — src/index.css, src/chat/*
- **Wave 2**: `feat(chat): message/composer/citations/history chrome` — src/chat/components/*
- **Wave 3**: `feat(chat): streaming adapter + wiring` — src/chat/api/*, src/chat/hooks/*
- **Wave 4**: `feat(chat): a11y motion responsive perf polish` — src/chat/*, app routing
- **Final**: `chore: chat QA evidence + docs`

---

## Success Criteria

### Verification Commands
```bash
npm run build          # Expected: tsc passes, vite build emits dist/assets
grep -r "console.log" src/chat  # Expected: no output
grep -r "window.addEventListener('scroll'" src  # Expected: no output in chat
```

### Final Checklist
- [ ] Chat visually continuous with landing (same ink/paper/gold, same masthead stamp, same mono voice)
- [ ] Operate mode respected (one accent, one radius, no marketing clutter, scanable)
- [ ] Streaming + citations work (or documented mock with single swap)
- [ ] Empty/loading/error states are composed, not blank
- [ ] A11y: focus trap in citations dock, labels above inputs, :active states, reduced-motion honored
- [ ] Build passes, no forbidden patterns, evidence captured

