# Zenith Export AI

A retrieval-augmented generation (RAG) assistant for **international trade compliance**, built for Indian exporters working across the **India, EU, and US** customs regimes. Ask questions like *"What is the minimum export quantity for wheat under DGFT rules?"* and get cited, grounded answers from a 40+ document corpus, with live web search as a fallback.

## How it works

```
Question
  → POST /ask/ or /ask/stream/ (SSE)
    → QueryAgentService
         ├─ KB retrieval (parallel, 4 sources fused)
         │    DocumentMetadata · FactIndex · FAISS chunks · BM25 summaries
         ├─ Web search (Tavily, verify-pass with domain allowlist)
         └→ 1 LLM synthesis call (OpenRouter) → cited answer
```

- **Hybrid retrieval** — dense (NVIDIA embeddings + FAISS) and sparse (BM25) fused with RRF, keyword boosting for trade-critical terms
- **Structured facts** — a `FactIndex` model stores extracted facts (type / subject / value / confidence) for hard numeric questions
- **Citations first** — every number in an answer must cite a document page or live source; the system prompt enforces anti-hallucination rules for HS-code and duty queries
- **Session auth** — register/login via JSON API (`/api/auth/*`), product endpoints return 401 anonymously, CSRF-protected POSTs, rate-limited auth endpoints

## Repository layout

```
rag_project/           Django project (settings, ASGI/Wsgi, URLs)
rag_app/               The application
  views.py             HTTP layer (ask, stream, search, upload, stats)
  api_auth.py          JSON auth endpoints + login/staff gates + throttling
  retrieval_service.py 4-source retrieval and RRF fusion
  services/            LLM, embeddings, FAISS, cache, web search, OCR
  templates/           Chat UI (Form Z-1 theme: warm ink + gold)
  static/rag_app/      CSS/JS for the chat UI
scripts/               acceptance_test.py — the 25-check security harness
docs/                  SECURITY-BASELINE.md · DEPLOYMENT.md
Knowlegebase/          Source PDFs (gitignored; rebuild via build_knowledge_base)
```

## Quick start

```bash
cp .env.example .env          # then fill in real values (SECRET_KEY is required)
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver    # http://localhost:8000
```

The React landing page lives on the `landing` branch of this repository (`npm run dev` on Vite, proxies `/api` to Django; see its own README there).

## Security posture

Hardened in phases, each verified by the acceptance harness (`python scripts/acceptance_test.py`): fail-fast secret management, env-driven DEBUG, CSRF on all authenticated POSTs, staff-gated knowledge-base reset, login/register throttling, upload magic-byte and page-count validation, gated document reads, Argon2 hashing, HSTS/secure cookies behind a proxy flag. See `docs/DEPLOYMENT.md` for the phase-by-phase record and the production runbook.

## Notes

- Answers are guidance for research, **not legal advice** — always confirm against the official gazette notifications.
- Rebuilding the knowledge base: `python manage.py build_knowledge_base` (requires the NVIDIA API keys and the source PDFs).
