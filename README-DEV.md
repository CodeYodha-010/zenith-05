# Zenith Export AI — Dev Guide

Developer & contributor guide for the trade-compliance RAG assistant.

## Quick start (Windows + Python 3.12+)

```bash
git clone https://github.com/CodeYodhax-010/zenith-05.git
cd zenith-05/rag_project

# Virtual env (recommended)
python -m venv .venv
.venv\Scripts\activate      # Linux: source .venv/bin/activate

pip install -r requirements.txt

# Secrets — copy the template and fill with your keys
cp .env.example .env
# Edit .env:
#   DJANGO_SECRET_KEY, OPENROUTER_API_KEY, NVIDIA_API_KEY, TAVILY_API_KEY, ...

python manage.py migrate
python manage.py runserver
```

App starts at `http://127.0.0.1:8000/`.

## Scripts

| Command | What it does |
|---|---|
| `python manage.py lint` | Syntax-check Python sources (`py_compile`) |
| `python manage.py migrate` | Apply Django migrations |
| `python manage.py runserver` | Start dev server (auto-reloads) |

## Architecture (quick)

- **Backend**: Django 5.1 + htmx + server-sent events (SSE) streaming
- **Retrieval**: FAISS dense vectors + BM25 sparse, fused via **Reciprocal Rank Fusion (RRF)**
- **Embeddings**: NVIDIA `nemotron-3-embed-1b-embed-context-512`
- **LLM routing**: OpenRouter (model pinned to a free tier)
- **Web search**: Tavily (advanced depth) + Jina rerank
- **KB**: PDF/DOCX/MD ingested and chunked; SQLite metadata store

## Env vars (`.env`)

| Var | Purpose |
|---|---|
| `DJANGO_SECRET_KEY` | Django sessions/CSRF |
| `OPENROUTER_API_KEY` / `OPENROUTER_MODEL` | LLM (text generation) |
| `NVIDIA_API_KEY` / `NVIDIA_OCR_API_KEY` | Embeddings + OCR fallback |
| `TAVILY_API_KEY` | Web search |
| `JINA_API_KEY` | Reranking |

## Tests

Run the golden-query regression in `scratch/`:
```bash
python manage.py lint && echo 'lint OK'
```

## Notes for contributors

- Templates use self-hosted fonts + compiled Tailwind (no CDN). After adding
  **new** Tailwind utilities, regenerate `static/rag_app/css/tailwind.css`:
  ```
  npx tailwindcss -i rag_app/static/rag_app/css/tailwind.in.css -o rag_app/static/rag_app/css/tailwind.css --minify
  ```
- Frontend layering: `fonts.css` → `tokens.css` → `glass.css` → `chat.css` →
  `animations.css` → `components.css` (order is intentional).
- See the inline spec comments in `static/rag_app/css/tokens.css` for the
  full design-token reference.

## License
MIT (add LICENSE file if you publish it).