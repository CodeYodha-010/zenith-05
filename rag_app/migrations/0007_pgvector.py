from django.db import migrations

VECTOR_DIM = 2048  # nemotron-3-embed-1b


def add_pgvector_columns(apps, schema_editor):
    """Postgres only: pgvector extension + normalized vector column.

    The legacy `embedding` JSONField column still exists (created by 0006) but
    is intentionally left empty on Postgres — it held 331 MB of redundant data
    locally and must never be uploaded (see sync_vectors).
    """
    if schema_editor.connection.vendor != 'postgresql':
        return
    schema_editor.execute('CREATE EXTENSION IF NOT EXISTS vector')
    schema_editor.execute(
        f'ALTER TABLE rag_app_searchindex ADD COLUMN embedding_v vector({VECTOR_DIM})')


def remove_pgvector_columns(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    schema_editor.execute('ALTER TABLE rag_app_searchindex DROP COLUMN IF EXISTS embedding_v')


class Migration(migrations.Migration):

    dependencies = [
        ('rag_app', '0006_searchindex_embedding_searchindex_embedding_model'),
    ]

    operations = [
        migrations.RunPython(add_pgvector_columns, remove_pgvector_columns),
    ]