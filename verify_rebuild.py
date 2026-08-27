import os
os.environ['DJANGO_SETTINGS_MODULE'] = 'rag_project.settings'
import django
django.setup()

from rag_app.models import Document, DocumentPage, SearchIndex

print("REBUILT FILES:")
for kw in ['Notification 62', 'Public Notice 49', 'Appendix 4R', 'DGFT HBP 2023']:
    docs = Document.objects.filter(title__icontains=kw)
    for d in docs:
        chunks = SearchIndex.objects.filter(page__document=d).count()
        print(f"  {d.title[:55]:55s} | {d.pages.count():3d} pg | {chunks:4d} chunks")

print(f"\nTotal KB: {Document.objects.count()} docs, {SearchIndex.objects.count()} chunks")

# Check keyword-boosted chunks exist
boosted = SearchIndex.objects.filter(section_title__icontains='KEYWORD BOOST')
print(f"\nKeyword-boosted chunks: {boosted.count()}")
for b in boosted[:10]:
    print(f"  BOOSTED: {b.section_title[:80]}")

# Check 10,000 MT content
mt_chunks = SearchIndex.objects.filter(content__icontains='10,000 MT')
print(f"\nChunks containing '10,000 MT': {mt_chunks.count()}")
for c in mt_chunks[:5]:
    preview = c.content[:150].replace('\n', ' ')
    print(f"  PAGE {c.page.page_number} | {c.page.document.title[:40]} | {preview}")
