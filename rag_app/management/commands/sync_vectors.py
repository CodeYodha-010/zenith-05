"""
Upload vectors into Postgres: faiss_index.index -> embedding_v (vector(2048)).

Contract:
  * Source of truth for vectors is the FAISS file (byte-identical copies of
    what local retrieval ranks with) — never re-embed, never read the JSON.
  * The legacy `embedding` JSON column on Neon must stay NULL (0 bytes of the
    331 MB it held locally); this command asserts that before and after.
  * Local SQLite chunk ids must equal Neon chunk ids (same order) — guaranteed
    by loaddata restoring primary keys, and verified here.
  * Upload is resume-safe: only rows whose embedding_v IS NULL are sent, each
    batch commits on its own, so an interrupted run just continues next time.
  * embedding_v is a DB-only column (migration 0007, not a model field) —
    pending ids are fetched with raw SQL.

Requires DJANGO_DB_ENGINE pointing at the Neon DIRECT endpoint.
"""
import sqlite3
from pathlib import Path

import faiss
import numpy as np
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from rag_app.models import SearchIndex
from rag_app.services.vector_store import assert_column, bulk_upsert, count_vectors


class Command(BaseCommand):
    help = "Copy FAISS vectors into Postgres embedding_v (never the legacy JSON column)."

    def add_arguments(self, parser):
        parser.add_argument("--expect-chunks", type=int, default=7184)

    def handle(self, *args, **opts):
        expect = opts["expect_chunks"]
        if connection.vendor != 'postgresql':
            raise CommandError(
                "sync_vectors targets Postgres. Uncomment DJANGO_DB_ENGINE in .env "
                "(DIRECT endpoint, sslmode=require), run migrate + loaddata first.")

        assert_column()

        # 1 — Neon chunk ids (id-sorted = FAISS row order)
        remote_ids = list(
            SearchIndex.objects.filter(source_type='chunk')
            .order_by('id').values_list('id', flat=True))

        # 2 — Local SQLite chunk ids (read-only, independent of Django)
        db_path = Path(settings.BASE_DIR) / 'db.sqlite3'
        if not db_path.exists():
            raise CommandError(f"local SQLite source missing: {db_path}")
        con = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
        try:
            local_ids = [r[0] for r in con.execute(
                "SELECT id FROM rag_app_searchindex WHERE source_type='chunk' ORDER BY id")]
        finally:
            con.close()

        if local_ids != remote_ids:
            raise CommandError(
                f"id mismatch: local={len(local_ids)} remote={len(remote_ids)} "
                "or different id sets — loaddata fidelity broken, aborting.")
        if len(remote_ids) != expect:
            raise CommandError(f"chunk rows {len(remote_ids)} != expected {expect}")

        # 3 — Vectors straight from the FAISS file (row i == remote_ids[i])
        idx_path = Path(settings.BASE_DIR) / 'faiss_index.index'
        index = faiss.read_index(str(idx_path))
        if index.ntotal != len(remote_ids):
            raise CommandError(
                f"FAISS ntotal={index.ntotal} != Neon chunks={len(remote_ids)}")
        try:
            vecs = index.reconstruct_n(0, index.ntotal)
        except Exception:
            vecs = np.vstack([index.reconstruct(i) for i in range(index.ntotal)])
        vecs = np.asarray(vecs, dtype=np.float32)

        # 4 — JSON column guard: must be NULL now and after
        json_before = SearchIndex.objects.filter(embedding__isnull=False).count()

        # 5 — Resume-safe upload: only rows still missing embedding_v
        with connection.cursor() as cur:
            cur.execute(
                "SELECT id FROM rag_app_searchindex "
                "WHERE source_type = 'chunk' AND embedding_v IS NULL")
            pending = {r[0] for r in cur.fetchall()}
        pairs = [(cid, vecs[i]) for i, cid in enumerate(remote_ids) if cid in pending]
        self.stdout.write(f"  pending vectors:   {len(pairs)} (of {expect})")
        written = bulk_upsert(pairs)

        json_after = SearchIndex.objects.filter(embedding__isnull=False).count()
        verified = count_vectors()

        self.stdout.write("\n-- sync ledger --")
        self.stdout.write(f"  vectors written:   {written}")
        self.stdout.write(f"  embedding_v set:   {verified} (of {expect} expected)")
        self.stdout.write(f"  legacy JSON rows:  {json_before} -> {json_after} "
                          "(must both be 0 on Neon)")
        self.stdout.write(f"  index:             {idx_path} ({index.ntotal} x {index.d})")

        ok = True
        if verified != expect:
            ok = False
            self.stdout.write(f"  FAIL embedding_v count {verified} != {expect}")
        if json_before != 0 or json_after != 0:
            ok = False
            self.stdout.write("  FAIL legacy JSON column is not empty on Neon")
        if not ok:
            raise CommandError("sync_vectors FAILED — see FAIL lines.")
        self.stdout.write(self.style.SUCCESS(
            "sync_vectors COMPLETE — next: python scripts/parity_check.py"))