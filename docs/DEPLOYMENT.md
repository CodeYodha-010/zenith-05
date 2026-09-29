# Deployment Runbook — Phase 0 procedures

## Acceptance harness

The harness is the pass/fail gate for every hardening phase. It must exit 0
before any phase is committed.

```bash
# against a running dev server
python scripts/acceptance_test.py http://127.0.0.1:8000

# against a staged deployment
python scripts/acceptance_test.py https://your-domain
```

Exit code 0 = all checks green. Exit 1 = regression; fix before proceeding.

## Backup procedure (run before any destructive phase)

```bash
# from the repo root (adjust the date folder)
New-Item -ItemType Directory -Force C:\Zenith1\backups\<date> | Out-Null
Copy-Item db.sqlite3 C:\Zenith1\backups\<date>\
Copy-Item faiss_index.index C:\Zenith1\backups\<date>\
```

## Rollback procedure

Code rollback (restores all tracked files):

```bash
git checkout pre-security-hardening   # tag created at 593e4f2
```

Data rollback (restores accounts + KB index):

```powershell
Copy-Item C:\Zenith1\backups\<date>\db.sqlite3 .
Copy-Item C:\Zenith1\backups\<date>\faiss_index.index .
```

Then restart the dev server and re-run the acceptance harness.

## Phase status

| Phase | Focus | Status |
|---|---|---|
| 0 | Backups, tag, acceptance harness | ✅ done |
| 1 | Critical fixes (SECRET_KEY, DEBUG, CSRF, /clear) | ✅ done |
| 2 | High-severity hardening (rate limits, uploads, deps) | ✅ done |
| 3 | Medium hardening (cookies, logging, injection) | done |
| 4 | Production packaging (gunicorn, Postgres, same-origin) | done |
| 5 | Server & TLS | pending |
| 6 | Go-live verification | pending |

## Environment variables (added in Phase 2)

| Var | Default | Purpose |
|---|---|---|
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1,testserver` | Comma-separated hosts; never use `*` |
| `DJANGO_BEHIND_PROXY` | `False` | Set `True` only when always behind a trusted reverse proxy (enables `SECURE_PROXY_SSL_HEADER`) |

## Rate limits (Phase 2, fixed-window, default LocMem cache)

| Endpoint | Limit | Keyed by |
|---|---|---|
| `POST /api/auth/register/` | 10/hour | IP |
| `POST /api/auth/login/` | 10/min | IP |
| `POST /ask/stream/` | 20/min | user |
| `POST /enhanced-search/stream/` | 20/min | user |

Note: the login burst test in the harness consumes the IP's login allowance;
wait ~60s between harness runs.

## Known issues

- ~~OpenRouter free-tier model (`openai/gpt-oss-20b:free`) intermittently
  returns "model unavailable for free"~~ **Resolved:** `OPENROUTER_MODEL`
  now defaults to `openrouter/free` (OpenRouter's free-model router), which
  picks a live free model per request instead of pinning a slug that can be
  retired without notice.

## Phase 4 - production packaging runbook

1. Build the landing page: cd zenith-landing && npm run build:prod
2. Set in .env: DEBUG=False, DJANGO_LANDING_DIST=<path>/dist, LANDING_URL=/landing/, DJANGO_ALLOWED_HOSTS=<domain>, DJANGO_BEHIND_PROXY=True, DJANGO_COOKIE_SECURE=True
3. Optional Postgres: set DJANGO_DB_* then manage.py migrate
4. Collect static: python manage.py collectstatic --noinput
5. Serve: gunicorn rag_project.asgi:application -k uvicorn.workers.UvicornWorker --workers 2 --bind 127.0.0.1:8000 (see deploy/zenith.service for the systemd unit)
6. Reverse proxy (Caddy): domain -> 127.0.0.1:8000, automatic TLS
7. Verify: python scripts/acceptance_test.py https://<domain>

## Free-tier production deploy — Render (API) + Netlify (landing)

Recommended stack when Docker Spaces / VPS are unavailable. Everything below
has a working free tier.

    browser ───> https://<site>.netlify.app          (React landing, dist/)
                    │
                    └─ /api/* proxy (configured in netlify.toml)
                            └──> https://<service>.onrender.com   (Django)

The browser only ever talks to the Netlify origin, so **no CORS setup is
needed**; the only cross-origin value Django must trust is the Netlify
origin itself (for CSRF), via `DJANGO_CSRF_TRUSTED_ORIGINS`.

### Step 1 — Backend on Render first (the landing page needs its URL)

New Web Service → connect `CodeYodha-010/zenith-05`:

| Setting | Value |
|---|---|
| Name | `zenith-backend` (gives you `zenith-backend.onrender.com`) |
| Branch | `main` |
| Root directory | *(empty — the backend is the repo root)* |
| Runtime | Python 3 |
| Build command | `pip install -r requirements.txt` |
| Start command | `gunicorn rag_project.asgi:application -k uvicorn.workers.UvicornWorker --workers 2 --bind 0.0.0.0:$PORT` |

Environment variables (Dashboard → Environment):

| Var | Value |
|---|---|
| `SECRET_KEY` | `python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"` |
| `DEBUG` | `False` |
| `DJANGO_ALLOWED_HOSTS` | `zenith-backend.onrender.com` |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | `https://<your-site>.netlify.app` |
| `DJANGO_BEHIND_PROXY` | `True` (Render terminates TLS; enables secure cookies + HSTS) |
| `LANDING_URL` | `https://<your-site>.netlify.app` (anonymous-visitor redirect) |
| `AUTH_MODE` | `supabase` |
| `SUPABASE_URL` / `SUPABASE_ANON_KEY` | from Supabase project settings |
| `OPENROUTER_API_KEY` | OpenRouter key (`OPENROUTER_MODEL` already defaults to `openrouter/free`) |
| `NVIDIA_EMBEDDING_API_KEY` | required — retrieval embeds queries with NVIDIA |
| `TAVILY_API_KEY` | optional — live web-search fallback |

**Knowledge-base data:** `db.sqlite3` and `Knowlegebase/` are gitignored, so
a fresh instance starts with an empty database. Either run
`python manage.py build_knowledge_base` once against the source PDFs (needs
the NVIDIA keys), or restore a seed backup and run
`python manage.py migrate` + `python manage.py collectstatic --noinput`.
For a managed Postgres (e.g. Neon), add `psycopg[binary]` to
`requirements.txt` and point `DJANGO_DB_*` at it.

### Step 2 — Landing page on Netlify

1. **Edit `netlify.toml`** (repository root): replace `YOUR-SERVICE` in the
   `[[redirects]]` block with your Render name, then commit — this is the
   `/api` proxy target.
2. **app.netlify.com → Add new site → Import from Git** →
   `CodeYodha-010/zenith-05` → branch `main`. Build settings are taken from
   `netlify.toml` automatically (base `frontend`, `npm run build:prod`,
   publish `dist`) — don't override them in the UI.
3. **Site configuration → Environment variables** (build-time, public):
   | Var | Value |
   |---|---|
   | `VITE_APP_URL` | `https://zenith-backend.onrender.com` (the "Launch console" link) |
   | `VITE_SUPABASE_URL` | Supabase project URL |
   | `VITE_SUPABASE_PUBLISHABLE_KEY` | Supabase publishable/anon key |
4. **Deploy.** First build ≈ 2 minutes.

### Step 3 — Supabase URL allowlist

Supabase dashboard → Authentication → URL Configuration → Site URL and
Redirect URLs → add `https://<your-site>.netlify.app`.

### Step 4 — Verify

```bash
python scripts/acceptance_test.py https://zenith-backend.onrender.com
```

Then manually: landing loads over HTTPS → register/login → ask a question →
citations render → `/api/auth/me/` returns the user.

### Rollback

Render → Deploys → previous deploy; Netlify → Deploys → previous deploy.
`AUTH_MODE=django` remains the auth rollback path.
