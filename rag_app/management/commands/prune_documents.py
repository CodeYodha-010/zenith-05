"""
Safe knowledge-base pruning.

Removes broken/duplicate documents AND rebuilds the FAISS index in the
same operation, preserving the row-order invariant:

    retrieval_service.py:200  all_chunk_ids = ...order_by('id').values_list('id', flat=True)
    retrieval_service.py:218  chunk_ids = [all_chunk_ids[i] for i in I ...]

i.e. FAISS row i corresponds to the i-th chunk id ordered by id.
Deleting rows WITHOUT rebuilding the index would silently score wrong content.

Default mode is DRY-RUN. Nothing is written without --execute.

Safety gates:
  1. Duplicate check: docs 400 (keep) vs 411 (delete) must have identical
     normalized source text, otherwise the run aborts.
  2. Pre-delete invariants: FAISS ntotal == current chunk row count.
  3. Survivor count must match the expected targets (43 docs / 7,184 chunks).
  4. New index is built and verified in a temp file BEFORE any DB write.
  5. DB delete runs inside a transaction; the index file is swapped atomically
     (os.replace) only after the transaction commits.
  6. Post-verify: reloaded index ntotal/dim + sampled vector equality.
"""

import hashlib
import os
from pathlib import Path

import numpy as np
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from rag_app.models import Document, DocumentPage, SearchIndex, DocumentMetadata, FactIndex
from rag_app.services.faiss_service import FAISSService


DELETE_DOC_IDS = [399, 402, 403, 411, 412, 428]
DUP_KEEP_DOC_ID = 400       # DGFT handbook — kept
DUP_DELETE_DOC_ID = 411     # duplicate handbook — deleted

EXPECTED_DOCS = 43
EXPECTED_CHUNKS = 7184
EXPECTED_DIM = 2048


def _norm_text(text: str) -> str:
    return " ".join((text or "").split())


def _source_fingerprint(doc_id: int):
    """Normalized whole-source-text SHA-256 (LLM summaries excluded on purpose:
    they are non-deterministic across runs, source text is not)."""
    pages = DocumentPage.objects.filter(document_id=doc_id).order_by("page_number")
    joined = "\n".join(_norm_text(p.original_text) for p in pages)
    total_chars = sum(len(p.original_text or "") for p in pages)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest(), total_chars, pages.count()


class Command(BaseCommand):
    help = "Prune broken/duplicate documents and rebuild the FAISS index (dry-run by default)."

    def add_arguments(self, parser):
        parser.add_argument("--execute", action="store_true",
                            help="Actually delete (default: dry-run)")
        parser.add_argument("--expect-docs", type=int, default=EXPECTED_DOCS)
        parser.add_argument("--expect-chunks", type=int, default=EXPECTED_CHUNKS)

    # ───────────────────────── helpers ─────────────────────────
    def _doc_stats(self, doc_id: int):
        doc = Document.objects.filter(id=doc_id).first()
        if doc is None:
            return None
        pages = DocumentPage.objects.filter(document_id=doc_id).count()
        chunks = SearchIndex.objects.filter(
            source_type="chunk", page__document_id=doc_id).count()
        summaries = SearchIndex.objects.filter(
            source_type="summary", page__document_id=doc_id).count()
        facts = FactIndex.objects.filter(page__document_id=doc_id).count()
        meta = DocumentMetadata.objects.filter(document_id=doc_id).exists()
        return {
            "id": doc_id, "title": doc.title, "region": doc.region,
            "pages": pages, "chunks": chunks, "summaries": summaries,
            "facts": facts, "metadata": meta,
        }

    def _check_duplicates(self, dry_run: bool):
        keep = _source_fingerprint(DUP_KEEP_DOC_ID)
        delete = _source_fingerprint(DUP_DELETE_DOC_ID)
        same_text = keep[0] == delete[0]
        self.stdout.write(
            f"  doc {DUP_KEEP_DOC_ID}: pages={keep[2]} chars={keep[1]} sha={keep[0][:16]}…")
        self.stdout.write(
            f"  doc {DUP_DELETE_DOC_ID}: pages={delete[2]} chars={delete[1]} sha={delete[0][:16]}…")
        if not same_text:
            raise CommandError(
                "ABORT: duplicate gate failed — source text of docs "
                f"{DUP_KEEP_DOC_ID} and {DUP_DELETE_DOC_ID} differ. "
                f"Do not delete doc {DUP_DELETE_DOC_ID} without manual review.")
        self.stdout.write(self.style.SUCCESS("  duplicate gate PASSED (identical source text)"))

    def _load_index(self, path: Path):
        if not path.exists():
            raise CommandError(f"FAISS index not found: {path}")
        svc = FAISSService()
        svc.load(str(path))
        return svc

    def _verify_counts(self, expect_docs: int, expect_chunks: int):
        """Count/alignment verification (safe to run any time)."""
        faiss_path = Path(settings.BASE_DIR) / "faiss_index.index"
        docs = Document.objects.count()
        chunks = SearchIndex.objects.filter(source_type="chunk").count()
        summaries = SearchIndex.objects.filter(source_type="summary").count()
        pages = DocumentPage.objects.count()
        json_rows = SearchIndex.objects.filter(embedding__isnull=False).count()
        svc = self._load_index(faiss_path)

        ok = True
        for name, got, want in (
            ("documents", docs, expect_docs),
            ("chunk rows", chunks, expect_chunks),
            ("FAISS ntotal", svc.index.ntotal, expect_chunks),
            ("FAISS dim", svc.index.d, EXPECTED_DIM),
        ):
            passed = got == want
            ok = ok and passed
            self.stdout.write(
                f"  {'PASS' if passed else 'FAIL'}  {name}: {got}"
                + ("" if passed else f" (expected {want})"))
        self.stdout.write(
            f"  info  local JSON embedding col populated rows: {json_rows} "
            "(legacy local data — sync_vectors NEVER copies this column)")
        self.stdout.write(
            f"\n  state: {docs} docs / {pages} pages / {chunks} chunks / "
            f"{summaries} summaries / FAISS {svc.index.ntotal} x {svc.index.d}")
        if not ok:
            raise CommandError("STATE VERIFICATION FAILED — see FAIL lines above.")

    # ───────────────────────── main ─────────────────────────
    def handle(self, *args, **opts):
        execute = opts["execute"]
        expect_docs = opts["expect_docs"]
        expect_chunks = opts["expect_chunks"]

        mode = "EXECUTE" if execute else "DRY-RUN (no writes)"
        self.stdout.write(self.style.WARNING(f"=== prune_documents [{mode}] ==="))

        faiss_path = Path(settings.BASE_DIR) / "faiss_index.index"

        # 1 ── stats table for the delete set
        self.stdout.write("\n-- documents selected for deletion --")
        stats = []
        missing = []
        total_chunks = 0
        for doc_id in DELETE_DOC_IDS:
            s = self._doc_stats(doc_id)
            if s is None:
                missing.append(doc_id)
                continue
            stats.append(s)
            total_chunks += s["chunks"]
            self.stdout.write(
                f"  {s['id']:>4}  [{s['region']:<5}] pages={s['pages']:<5} chunks={s['chunks']:<5} "
                f"summaries={s['summaries']:<5} facts={s['facts']:<4} "
                f"meta={'Y' if s['metadata'] else 'N'}  {s['title'][:70]}")
        if missing:
            self.stdout.write(self.style.WARNING(f"  (not present, already pruned?): {missing}"))
        if not stats:
            self.stdout.write(self.style.SUCCESS(
                "Nothing to delete — targets already pruned. Verifying current state."))
            self._verify_counts(expect_docs, expect_chunks)
            return

        current_docs = Document.objects.count()
        current_chunks = SearchIndex.objects.filter(source_type="chunk").count()
        projected_docs = current_docs - len(stats)
        projected_chunks = current_chunks - total_chunks
        self.stdout.write(f"\n  current:   {current_docs} docs / {current_chunks} chunks")
        self.stdout.write(f"  projected: {projected_docs} docs / {projected_chunks} chunks "
                          f"(targets: {expect_docs} / {expect_chunks})")

        if projected_docs != expect_docs or projected_chunks != expect_chunks:
            raise CommandError(
                "ABORT: projection mismatch — expected "
                f"{expect_docs} docs / {expect_chunks} chunks after deletion, "
                f"got {projected_docs} / {projected_chunks}.")

        # 2 ── duplicate gate (400 keep vs 411 delete)
        if DUP_DELETE_DOC_ID in [s["id"] for s in stats]:
            self.stdout.write("\n-- duplicate gate (400 vs 411) --")
            self._check_duplicates(True)

        # 3 ── index/DB alignment gate + rebuild preparation
        self.stdout.write("\n-- FAISS alignment --")
        old_service = self._load_index(faiss_path)
        old_index = old_service.index
        old_ids = list(SearchIndex.objects.filter(source_type="chunk")
                       .order_by("id").values_list("id", flat=True))
        if old_index.ntotal != len(old_ids):
            raise CommandError(
                f"ABORT: index/DB mismatch — FAISS ntotal={old_index.ntotal} "
                f"vs chunk rows={len(old_ids)}. Restore from backup first.")
        self.stdout.write(f"  old index: ntotal={old_index.ntotal} d={old_index.d} matches chunk rows")

        delete_chunk_ids = set(
            SearchIndex.objects.filter(
                source_type="chunk", page__document_id__in=DELETE_DOC_IDS
            ).values_list("id", flat=True))
        old_pos = {cid: i for i, cid in enumerate(old_ids)}
        survivor_ids = [cid for cid in old_ids if cid not in delete_chunk_ids]
        if len(survivor_ids) != expect_chunks:
            raise CommandError(f"ABORT: survivor count {len(survivor_ids)} != {expect_chunks}")

        # Reconstruct ALL old vectors once (≈62 MB float32), then subset.
        try:
            all_vecs = old_index.reconstruct_n(0, old_index.ntotal)
        except Exception:
            all_vecs = np.vstack([old_index.reconstruct(i) for i in range(old_index.ntotal)])
        all_vecs = np.asarray(all_vecs, dtype=np.float32)
        positions = np.array([old_pos[cid] for cid in survivor_ids], dtype=np.int64)
        survivor_vecs = all_vecs[positions]
        self.stdout.write(f"  survivors: {len(survivor_ids)} rows staged "
                          f"(reconstructed from old rows at id-sorted positions)")

        # Build + verify the NEW index in a temp file BEFORE touching the DB.
        tmp_path = Path(str(faiss_path) + ".prune.tmp")
        new_service = FAISSService(dimension=EXPECTED_DIM)
        new_service.add_vectors(survivor_vecs)
        if new_service.index.ntotal != expect_chunks or new_service.index.d != EXPECTED_DIM:
            raise CommandError("ABORT: staged index failed size check")
        new_service.save(str(tmp_path))

        # Verify staged file: reload and compare sampled rows.
        verify_service = self._load_index(tmp_path)
        if verify_service.index.ntotal != expect_chunks:
            raise CommandError("ABORT: staged index failed reload check")
        for row in (0, expect_chunks // 2, expect_chunks - 1):
            got = np.asarray(verify_service.index.reconstruct(row), dtype=np.float32)
            want = survivor_vecs[row]
            drift = float(np.max(np.abs(got - want)))
            if drift > 1e-5:
                tmp_path.unlink(missing_ok=True)
                raise CommandError(f"ABORT: staged vector drift {drift} at row {row}")
        self.stdout.write(self.style.SUCCESS(
            f"  staged index OK: {tmp_path.name} ({expect_chunks} x {EXPECTED_DIM}), "
            "3 sampled rows within 1e-5"))

        if not execute:
            self.stdout.write(self.style.WARNING(
                "\nDRY-RUN complete. DB untouched, live index untouched, staged file left at "
                f"{tmp_path.name}. Re-run with --execute to apply."))
            return

        # 4 ── execute: move old index aside, DB transaction, atomic swap.
        bak_path = Path(str(faiss_path) + ".bak")
        try:
            os.replace(faiss_path, bak_path)          # keep pre-delete index as .bak
        except OSError as e:
            tmp_path.unlink(missing_ok=True)
            raise CommandError(f"ABORT: could not move old index aside: {e}")

        try:
            with transaction.atomic():
                deleted, _details = Document.objects.filter(
                    id__in=[s["id"] for s in stats]).delete()
                # Collector cascades: DocumentPage, SearchIndex, DocumentMetadata, FactIndex
        except Exception as e:
            # DB failed → put the old index back, drop staged file.
            os.replace(bak_path, faiss_path)
            tmp_path.unlink(missing_ok=True)
            raise CommandError(f"ABORT: DB delete failed ({e}); old index restored.")

        try:
            os.replace(tmp_path, faiss_path)           # atomic swap (same volume)
        except OSError as e:
            raise CommandError(
                f"CRITICAL: DB pruned but index swap failed ({e}). "
                f"Restore manually: copy {bak_path} -> {faiss_path}")

        # 5 ── post-verify
        self.stdout.write("\n-- post-verify --")
        final_docs = Document.objects.count()
        final_pages = DocumentPage.objects.count()
        final_chunks = SearchIndex.objects.filter(source_type="chunk").count()
        final_summaries = SearchIndex.objects.filter(source_type="summary").count()
        json_rows = SearchIndex.objects.filter(embedding__isnull=False).count()
        final_service = self._load_index(faiss_path)

        checks = [
            ("documents", final_docs, expect_docs),
            ("chunk rows", final_chunks, expect_chunks),
            ("FAISS ntotal", final_service.index.ntotal, expect_chunks),
            ("FAISS dim", final_service.index.d, EXPECTED_DIM),
        ]
        ok = True
        for name, got, want in checks:
            passed = got == want
            ok = ok and passed
            self.stdout.write(
                f"  {'PASS' if passed else 'FAIL'}  {name}: {got}"
                + ("" if passed else f" (expected {want})"))
        self.stdout.write(
            f"  info  local JSON embedding col populated rows: {json_rows} "
            "(legacy local data — sync_vectors NEVER copies this column)")

        # sampled vector equality against the pre-delete vectors
        new_id_order = list(SearchIndex.objects.filter(source_type="chunk")
                            .order_by("id").values_list("id", flat=True))
        for row in (0, len(new_id_order) // 2, len(new_id_order) - 1):
            got = np.asarray(final_service.index.reconstruct(row), dtype=np.float32)
            want = all_vecs[old_pos[new_id_order[row]]]
            drift = float(np.max(np.abs(got - want)))
            if drift > 1e-5:
                ok = False
                self.stdout.write(f"  FAIL  vector drift {drift} at row {row}")

        self.stdout.write(
            f"\n  final: {final_docs} docs / {final_pages} pages / {final_chunks} chunks / "
            f"{final_summaries} summaries / FAISS {final_service.index.ntotal} x "
            f"{final_service.index.d}")
        self.stdout.write(f"  pre-delete index kept at: {bak_path}")
        self.stdout.write(f"  DB objects deleted (incl. cascades): {deleted}")
        if not ok:
            raise CommandError(
                "POST-VERIFY FAILED — see FAIL lines above. "
                f"Rollback: copy {bak_path} -> {faiss_path} and restore db.sqlite3 "
                "from C:\\Zenith1\\backups\\2026-10-01-pre-neon")
        self.stdout.write(self.style.SUCCESS("prune_documents COMPLETE — all checks PASS"))

