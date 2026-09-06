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

- OpenRouter free-tier model (`openai/gpt-oss-20b:free`) intermittently
  returns "model unavailable for free" — answers fail at the LLM step.
  Unrelated to security work; resolve by pinning a different
  `OPENROUTER_MODEL` in `.env` or topping up the OpenRouter account.

## Phase 4 - production packaging runbook

1. Build the landing page: cd zenith-landing && npm run build:prod
2. Set in .env: DEBUG=False, DJANGO_LANDING_DIST=<path>/dist, LANDING_URL=/landing/, DJANGO_ALLOWED_HOSTS=<domain>, DJANGO_BEHIND_PROXY=True, DJANGO_COOKIE_SECURE=True
3. Optional Postgres: set DJANGO_DB_* then manage.py migrate
4. Collect static: python manage.py collectstatic --noinput
5. Serve: gunicorn rag_project.asgi:application -k uvicorn.workers.UvicornWorker --workers 2 --bind 127.0.0.1:8000 (see deploy/zenith.service for the systemd unit)
6. Reverse proxy (Caddy): domain -> 127.0.0.1:8000, automatic TLS
7. Verify: python scripts/acceptance_test.py https://<domain>
