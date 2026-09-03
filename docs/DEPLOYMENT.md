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
| 2 | High-severity hardening (rate limits, uploads, deps) | pending |
| 3 | Medium hardening (cookies, logging, injection) | pending |
| 4 | Production packaging (gunicorn, Postgres, same-origin) | pending |
| 5 | Server & TLS | pending |
| 6 | Go-live verification | pending |

## Known issues

- OpenRouter free-tier model (`openai/gpt-oss-20b:free`) intermittently
  returns "model unavailable for free" — answers fail at the LLM step.
  Unrelated to security work; resolve by pinning a different
  `OPENROUTER_MODEL` in `.env` or topping up the OpenRouter account.

