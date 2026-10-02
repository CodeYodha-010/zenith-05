"""
Export the rag_app corpus (documents, metadata, pages, search entries, facts)
to a loaddata-compatible JSON file for uploading to Neon.

Deliberately excludes SearchIndex.embedding — the legacy JSON vector column
(331 MB of redundant data at 49 docs; still ~legacy-sized after the prune).
Vectors travel separately via sync_vectors, straight from faiss_index.index
into Postgres column embedding_v, which keeps this export small and makes
"never copy the JSON column" structurally impossible to violate.
"""
import json
from pathlib import Path

from django.conf import settings
from django.core import serializers
from django.core.management.base import BaseCommand
from django.db.models import Case, IntegerField, Value, When

from rag_app.models import (
    Document,
    DocumentMetadata,
    DocumentPage,
    FactIndex,
    SearchIndex,
)


class Command(BaseCommand):
    help = "Export rag_app data to export/corpus.json (excludes the legacy embedding JSON)."

    def handle(self, *args, **opts):
        plans = [
            (Document, Document.objects.all().order_by('id'), ()),
            (DocumentMetadata, DocumentMetadata.objects.all().order_by('id'), ()),
            (DocumentPage, DocumentPage.objects.all().order_by('id'), ()),
            (SearchIndex, self._searchindex_queryset(), ('embedding',)),
            (FactIndex, FactIndex.objects.all().order_by('id'), ()),
        ]

        out_dir = Path(settings.BASE_DIR) / 'export'
        out_dir.mkdir(exist_ok=True)
        path = out_dir / 'corpus.json'

        parts = []
        total = 0
        for model, qs, exclude in plans:
            fields = [f.name for f in model._meta.concrete_fields if f.name not in exclude]
            blob = serializers.serialize('json', qs, fields=fields).strip()
            count = qs.count()
            total += count
            self.stdout.write(
                f"  {model._meta.label:<35} {count:>6} rows"
                + (f"  (excluded: {', '.join(exclude)})" if exclude else ""))
            if blob != '[]':
                parts.append(blob[1:-1].strip())

        path.write_text('[' + ',\n'.join(parts) + ']', encoding='utf-8')

        # Round-trip sanity: the file must parse and carry the expected objects.
        data = json.loads(path.read_text(encoding='utf-8'))
        size_mb = path.stat().st_size / 1e6
        self.stdout.write(f"\n  wrote {path}  ({size_mb:.1f} MB, {len(data)} objects, "
                          f"source rows {total})")
        if len(data) != total:
            raise SystemExit("ABORT: serialized object count != source row count")
        if any('embedding' in obj.get('fields', {}) for obj in data
               if obj.get('model') == 'rag_app.searchindex'):
            raise SystemExit("ABORT: export contains the embedding JSON column")
        self.stdout.write(self.style.SUCCESS(
            "export OK — load with:  python manage.py loaddata export/corpus.json"))

    @staticmethod
    def _searchindex_queryset():
        # loaddata inserts in file order under immediate FK constraints, so all
        # parent chunks (parent_chunk IS NULL) must precede their children.
        return SearchIndex.objects.annotate(
            _depth=Case(
                When(parent_chunk__isnull=True, then=Value(0)),
                default=Value(1),
                output_field=IntegerField(),
            )
        ).order_by('_depth', 'id')