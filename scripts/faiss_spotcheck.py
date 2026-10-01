"""
Post-change retrieval spot check: runs real queries through the exact
production mapping (FAISS row i -> i-th chunk id ordered by id) and prints
the top hits so semantic sanity can be eyeballed after corpus surgery.

Run from the repo root:  python scripts/faiss_spotcheck.py
Exit 0 = alignment + API + content sane; 1 = regression.
"""
import os
import sys

import django
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'rag_project.settings')
django.setup()

from rag_app.models import SearchIndex, Document  # noqa: E402
from rag_app.services.service_registry import get_embedding_model, get_faiss_service  # noqa: E402

QUERIES = [
    "minimum export quantity for wheat from India",
    "RCMC certificate validity for exporters",
    "customs duty drawback procedure for re-export",
]

failures = []
emb = get_embedding_model()
svc = get_faiss_service()
if emb is None or svc is None:
    print("FAIL  embedding model or FAISS index unavailable")
    sys.exit(1)

all_chunk_ids = list(
    SearchIndex.objects.filter(source_type='chunk')
    .order_by('id').values_list('id', flat=True)
)
live_doc_ids = set(Document.objects.values_list('id', flat=True))
print(f"index ntotal={svc.index.ntotal}  chunk rows={len(all_chunk_ids)}  docs={len(live_doc_ids)}")
if svc.index.ntotal != len(all_chunk_ids):
    print("FAIL  index/DB id-map misaligned")
    sys.exit(1)

for q in QUERIES:
    print(f"\nQ: {q}")
    try:
        vec = emb.embed_query(q)
    except Exception as e:
        print(f"FAIL  embedding API error: {e}")
        sys.exit(1)
    v = np.array(vec, dtype=np.float32)
    v = v / np.linalg.norm(v)
    D, I = svc.search(v.reshape(1, -1), k=5)
    for rank, (score, row) in enumerate(zip(D[0], I[0]), start=1):
        cid = all_chunk_ids[row]
        chunk = SearchIndex.objects.select_related('page__document').get(id=cid)
        ok = chunk.source_type == 'chunk' and chunk.page.document_id in live_doc_ids
        if not ok:
            failures.append(f"row {row} -> dead/incorrect doc")
        snippet = ' '.join(chunk.content.split())[:90]
        print(f"  {rank}. {float(score):+.4f}  doc={chunk.page.document_id} "
              f"p{chunk.page.page_number}  {chunk.page.document.title[:42]}  | {snippet}")

print()
if failures:
    for f in failures:
        print(f"FAIL  {f}")
    sys.exit(1)
print("PASS  alignment + live embeddings + content sanity")
