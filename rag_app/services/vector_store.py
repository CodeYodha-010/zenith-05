"""
Postgres/pgvector backend for Source-3 semantic search.

Parity contract with the local FAISS path (retrieval_service.py Source 3):
  * vectors are L2-normalized float32, dim 2048 (nemotron-3-embed-1b)
  * FAISS IndexFlatIP on normalized vectors == pgvector cosine distance:
        score = 1 - (a <=> b)
  * row identity: chunk ids ordered by id — the same order used to build
    the FAISS index, so both backends return identical rankings.

At ~7,184 rows no ANN index is created on purpose: vector-HNSW columns are
capped at 2,000 dims (< 2048) and an exact scan of 7k rows is already
sub-millisecond, preserving exact FAISS parity.
"""
import json
import queue
import threading
from typing import List, Tuple

import numpy as np
from django.db import connection, transaction


def _literal(vec) -> str:
    """Full-precision text literal (used for one-off query vectors)."""
    arr = np.asarray(vec, dtype=np.float32).reshape(-1)
    return json.dumps([float(x) for x in arr.tolist()])


def _short_literal(vec) -> str:
    """Compact pgvector text literal for bulk uploads.

    %.9g keeps 9 significant digits — enough to round-trip float32 exactly —
    while cutting each vector from ~47 KB (full-precision repr) to ~27 KB.
    """
    arr = np.asarray(vec, dtype=np.float32).reshape(-1)
    return '[' + ','.join('%.9g' % float(x) for x in arr) + ']'


def _require_postgres():
    if connection.vendor != 'postgresql':
        raise RuntimeError(
            "vector_store requires Postgres — set DJANGO_DB_ENGINE (direct endpoint) first.")


def vector_search(query_emb, k: int = 50) -> List[Tuple[int, float]]:
    """Top-k (chunk_id, score) ordered by score desc; score mirrors FAISS IP."""
    _require_postgres()
    sql = """
        SELECT id, 1 - (embedding_v <=> %s::vector) AS score
        FROM rag_app_searchindex
        WHERE source_type = 'chunk' AND embedding_v IS NOT NULL
        ORDER BY embedding_v <=> %s::vector
        LIMIT %s
    """
    lit = _literal(query_emb)
    with connection.cursor() as cur:
        cur.execute(sql, [lit, lit, k])
        return [(int(r[0]), float(r[1])) for r in cur.fetchall()]


def bulk_upsert(pairs, batch: int = 200, workers: int = 6) -> int:
    """Parallel batched UPDATE of embedding_v for (chunk_id, vector) pairs.

    Design notes (why this shape):
      * Each batch commits independently — progress is observable while it
        runs (`embedding_v IS NOT NULL`), an interrupted run resumes safely,
        and no multi-minute open transaction is held against Neon.
      * 6 parallel connections hide the ~100 ms RTT and multiply usable
        upload bandwidth: a single connection pushed the vectors at only
        ~230 KB/s of text (~18 minutes for one serialized pass).
      * Multi-row UPDATE ... FROM (VALUES ...) = one roundtrip per batch.
        (A naive executemany is one roundtrip per row: ~12 minutes alone.)

    NEVER writes the legacy `embedding` JSON column (331 MB of redundant data).
    """
    _require_postgres()
    items = list(pairs)
    chunks = [items[i:i + batch] for i in range(0, len(items), batch)]
    q = queue.Queue()
    for ch in chunks:
        q.put(ch)
    state = {'rows': 0}
    lock = threading.Lock()
    errors: list = []

    def worker():
        try:
            while True:
                try:
                    ch = q.get_nowait()
                except queue.Empty:
                    return
                rows = [(int(cid), _short_literal(vec)) for cid, vec in ch]
                params = [v for pair in rows for v in pair]
                placeholders = ', '.join(['(%s::int, %s::vector)'] * len(rows))
                with transaction.atomic():
                    with connection.cursor() as cur:
                        cur.execute(
                            "UPDATE rag_app_searchindex AS t "
                            "SET embedding_v = v.vec "
                            "FROM (VALUES " + placeholders + ") AS v(id, vec) "
                            "WHERE t.id = v.id",
                            params)
                with lock:
                    state['rows'] += len(rows)
        except Exception as exc:  # noqa: BLE001 — surfaced to the main thread
            errors.append(exc)
        finally:
            try:
                connection.close()
            except Exception:  # noqa: BLE001 — thread teardown, best effort
                pass

    n_threads = min(workers, max(len(chunks), 1))
    threads = [threading.Thread(target=worker, daemon=True)
               for _ in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    if errors:
        raise errors[0]
    return state['rows']


def assert_column() -> None:
    _require_postgres()
    with connection.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = 'rag_app_searchindex' AND column_name = 'embedding_v'")
        if cur.fetchone() is None:
            raise RuntimeError("embedding_v column missing — run `python manage.py migrate`.")


def count_vectors() -> int:
    _require_postgres()
    with connection.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM rag_app_searchindex WHERE embedding_v IS NOT NULL")
        return int(cur.fetchone()[0])