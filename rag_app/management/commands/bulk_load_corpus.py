"""
Fast bulk upload of export/corpus.json into the DEFAULT (Postgres) database.

Why this exists: `manage.py loaddata` saves objects one-by-one; each object
costs an UPDATE+INSERT roundtrip (~100 ms to Neon) → ~43 minutes for 12,898
objects. This loader issues batched multi-row INSERTs in a single transaction:
seconds instead of half an hour, with ids and timestamps preserved exactly
(bulk_create would clobber auto_now_add created_at).

Dependency order comes from the file itself (export_corpus writes Document →
Metadata → Page → SearchIndex (parents first) → FactIndex), and the whole
upload is one transaction: either everything lands or nothing does.

Verify afterwards with the printed ledger + `manage.py sync_vectors`.
"""
import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from rag_app.models import (
    Document,
    DocumentMetadata,
    DocumentPage,
    FactIndex,
    SearchIndex,
)

MODEL_MAP = {
    'rag_app.document': Document,
    'rag_app.documentmetadata': DocumentMetadata,
    'rag_app.documentpage': DocumentPage,
    'rag_app.searchindex': SearchIndex,
    'rag_app.factindex': FactIndex,
}
BATCH_ROWS = 500


class Command(BaseCommand):
    help = "Bulk-load export/corpus.json into the default DB (Postgres/Neon)."

    def add_arguments(self, parser):
        parser.add_argument('--file', default=str(Path(settings.BASE_DIR) / 'export' / 'corpus.json'))

    def handle(self, *args, **opts):
        if connection.vendor != 'postgresql':
            raise CommandError(
                "bulk_load_corpus targets Postgres — uncomment DJANGO_DB_ENGINE first.")
        src = Path(opts['file'])
        if not src.exists():
            raise CommandError(f"missing {src} — run export_corpus first (on SQLite).")

        objects = json.loads(src.read_text(encoding='utf-8'))
        self.stdout.write(f"parsed {len(objects)} objects from {src.name}")

        # group consecutive same-model runs, preserving file (dependency) order
        runs = []
        for obj in objects:
            model_key = obj['model']
            if model_key not in MODEL_MAP:
                raise CommandError(f"unknown model in export: {model_key}")
            if runs and runs[-1][0] == model_key:
                runs[-1][1].append(obj)
            else:
                runs.append((model_key, [obj]))

        loaded = {}
        with transaction.atomic():
            for model_key, objs in runs:
                model = MODEL_MAP[model_key]
                cols = [f.column for f in model._meta.concrete_fields]
                col_sql = ', '.join(f'"{c}"' for c in cols)
                table = model._meta.db_table
                n_rows = 0
                for i in range(0, len(objs), BATCH_ROWS):
                    batch = objs[i:i + BATCH_ROWS]
                    values_sql = []
                    params = []
                    for o in batch:
                        values_sql.append('(' + ', '.join(['%s'] * len(cols)) + ')')
                        row = [o['pk']]
                        for f in model._meta.concrete_fields[1:]:
                            row.append(o['fields'].get(f.name))
                        params.extend(row)
                    sql = f'INSERT INTO "{table}" ({col_sql}) VALUES ' + ', '.join(values_sql)
                    with connection.cursor() as cur:
                        cur.execute(sql, params)
                        n_rows += cur.rowcount
                loaded[model_key] = n_rows
                self.stdout.write(f"  {model_key:<32} inserted {n_rows:>6}")

        # post-verify against source counts
        self.stdout.write("\n-- verify --")
        expected = {}
        for obj in objects:
            expected[obj['model']] = expected.get(obj['model'], 0) + 1
        ok = True
        for key, want in expected.items():
            got = loaded.get(key, 0)
            passed = got == want
            ok = ok and passed
            self.stdout.write(f"  {'PASS' if passed else 'FAIL'}  {key}: {got} (expected {want})")

        with connection.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM rag_app_searchindex si "
                "LEFT JOIN rag_app_documentpage dp ON si.page_id = dp.id "
                "WHERE dp.id IS NULL")
            orphans = cur.fetchone()[0]
            cur.execute(
                "SELECT COUNT(*) FROM rag_app_searchindex WHERE embedding IS NOT NULL")
            json_rows = cur.fetchone()[0]
        for name, got, want in (("orphan search rows", orphans, 0),
                                ("legacy JSON rows (must be 0)", json_rows, 0)):
            passed = got == want
            ok = ok and passed
            self.stdout.write(f"  {'PASS' if passed else 'FAIL'}  {name}: {got}")

        if not ok:
            raise CommandError("bulk_load_corpus FAILED — transaction rolled back.")
        self.stdout.write(self.style.SUCCESS(
            "upload COMPLETE — next: python manage.py sync_vectors"))