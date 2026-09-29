# Zenith Landing Page (`frontend/`)

Public marketing + sign-up page for **Zenith Export AI** — React 18, Vite 5,
TypeScript, Tailwind CSS, Supabase Auth. This is the half of the repository
that Netlify deploys; the Django backend lives at the repository root.

## Quick start

```bash
cd frontend
npm ci          # exact versions from package-lock.json
npm run dev     # http://localhost:5173
```

The Vite dev server proxies `/api` to Django on `http://127.0.0.1:8000`
(see `vite.config.ts`), so start the backend first:

```bash
# from the repository root
python manage.py runserver    # http://localhost:8000
```

## Scripts

| Command | What it does |
|---|---|
| `npm run dev` | Dev server with HMR + `/api` proxy |
| `npm run build` | Typecheck + production build → `dist/` |
| `npm run build:prod` | Same, but with `--base=./` (relative asset paths; **used by Netlify**) |
| `npm run preview` | Serve the built `dist/` locally |

## Environment variables

All are `VITE_*` (baked in at build time — **never put secrets here**, the
bundle is public):

| Variable | Purpose |
|---|---|
| `VITE_APP_URL` | Django base URL. Feeds `CHAT_URL`, the "Launch console" link. Empty = `http://localhost:8000` fallback |
| `VITE_SUPABASE_URL` | Supabase project URL (Auth) |
| `VITE_SUPABASE_PUBLISHABLE_KEY` | Supabase anon/publishable key |

`.env.production` in this folder carries **empty placeholders only**; set the
real values as build environment variables in the Netlify UI so they never
touch git.

## How it talks to the backend

The API client (`src/lib/api.ts`) always calls **relative** `/api/...` paths:

- **Dev** — Vite proxies `/api` → `127.0.0.1:8000`
- **Production** — Netlify proxies `/api/*` → the Render service URL
  (redirect configured in the repository-root `netlify.toml`)

Because the browser only ever talks to one origin, cookies and CSRF work
without any CORS configuration.

## Production deploy

Netlify reads `netlify.toml` at the **repository root** (base `frontend`,
build `npm run build:prod`, publish `dist`). Full runbook, including the
`/api` proxy URL you must fill in before the first deploy: `docs/DEPLOYMENT.md`.

## Layout

```
src/
  App.tsx               Page composition
  components/           Nav, Hero, Pipeline, Regions, Stats, Closing, ...
  auth/AuthContext.tsx  Supabase session state
  auth/AuthModal.tsx    Sign-in / sign-up modal
  lib/api.ts            Fetch wrapper (+ CSRF/bearer headers)
  lib/supabase.ts       Supabase client (skipped when env vars absent)
  hooks/useInView.ts    Scroll reveal helper
public/                 Favicon, self-hosted fonts
```
