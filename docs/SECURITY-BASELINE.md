# Security Baseline — pre-hardening snapshot (Phase 0)

Date: 2026-09-02 · Repo state: `593e4f2` · Tag: `pre-security-hardening`

## Rollback assets
- Git tag `pre-security-hardening` (code)
- `C:\Zenith1\backups\2026-09-02-pre-security\` — `db.sqlite3` (447.8 MB) + `faiss_index.index` (59.4 MB)

## Environment variables present in `.env` (names only)
`NVIDIA_LLM_API_KEY`, `NVIDIA_OCR_API_KEY`, `NVIDIA_API_URL`, `SECRET_KEY`,
`DEBUG`, `JINA_API_KEY`, `TAVILY_API_KEY`, `FIRECRAWL_API_KEY`,
`NVIDIA_EMBEDDING_API_KEY`, `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`,
`NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`, `CLERK_SECRET_KEY` (Clerk keys unused — candidates for removal)

## Confirmed pre-fix state
- `SECRET_KEY` env var IS set locally (27-char custom value, NOT the public fallback) — but the insecure fallback remains in `settings.py` and would activate if the var were missing in prod
- `DEBUG=True` in `.env`; `settings.py` hardcodes `DEBUG=True` regardless
- `ALLOWED_HOSTS=[]` · no rate limiting · no HTTPS/HSTS cookie flags
- Authed POST endpoints are `@csrf_exempt` · `/clear/` is login-gated but not staff-gated
- Public (no auth): `/documents/`, `/document/<id>/pages/`, `/page/<id>/`, `/stats/`, `/suggestions/`
- Missing from `requirements.txt`: faiss-cpu, llama-index-*, httpx, tenacity, gunicorn, whitenoise, psycopg

## Acceptance harness
`scripts/acceptance_test.py [BASE_URL]` — 14 checks (auth gates, registration
validation, login/logout cycle, chat render). Baseline run: **14/14 PASS**
against `http://127.0.0.1:8000`. Every later phase must keep this green.
