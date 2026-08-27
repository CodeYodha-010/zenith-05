"""
Quick verification script for the OpenDataLoader + NVIDIA embeddings pipeline.
Run after setting real API keys in .env
"""
import os
import sys
import time

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'rag_project.settings')

import django
django.setup()

from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / '.env')


def test_opendataloader():
    """Test OpenDataLoader parsing (no API key needed)."""
    print("=" * 60)
    print("1. Testing OpenDataLoader PDF parsing...")
    print("=" * 60)
    
    from rag_app.services.opendataloader_service import OpenDataLoaderService
    
    service = OpenDataLoaderService()
    
    # Test with a small PDF
    kb_path = Path(__file__).parent / "Knowlegebase" / "rag_documents" / "rag_documents"
    test_files = list(kb_path.glob("*.pdf"))[:2]  # Test first 2 PDFs
    
    for pdf_file in test_files:
        print(f"\n  Testing: {pdf_file.name}")
        start = time.time()
        result = service.parse_pdf(str(pdf_file))
        elapsed = time.time() - start
        
        print(f"    Pages: {result['metadata']['page_count']}")
        print(f"    Chunks: {result['metadata']['chunk_count']}")
        print(f"    Time: {elapsed:.1f}s")
        
        if result['chunks']:
            sample = result['chunks'][0]
            print(f"    Sample chunk (page {sample['page_number']}): {sample['content'][:100]}...")
    
    print("\n  [OK] OpenDataLoader working\n")
    return True


def test_nvidia_embeddings():
    """Test NVIDIA embeddings (needs API key)."""
    print("=" * 60)
    print("2. Testing NVIDIA embeddings...")
    print("=" * 60)
    
    api_key = os.getenv("NVIDIA_EMBEDDING_API_KEY", "")
    if not api_key or "your-nvidia" in api_key:
        print("  [SKIP] NVIDIA_EMBEDDING_API_KEY not set in .env")
        print("  Get key from: https://build.nvidia.com")
        return False
    
    from rag_app.services.nvidia_embedding_service import NvidiaEmbeddingService
    
    service = NvidiaEmbeddingService()
    
    # Test single embedding
    start = time.time()
    embedding = service.get_embedding("Test document for trade compliance")
    elapsed = time.time() - start
    
    print(f"  Embedding dimension: {len(embedding)}")
    print(f"  Time: {elapsed:.1f}s")
    print(f"  Sample values: {embedding[:3]}...")
    
    print("\n  [OK] NVIDIA embeddings working\n")
    return True


def test_faiss_index():
    """Test FAISS index building."""
    print("=" * 60)
    print("3. Testing FAISS index building...")
    print("=" * 60)
    
    api_key = os.getenv("NVIDIA_EMBEDDING_API_KEY", "")
    if not api_key or "your-nvidia" in api_key:
        print("  [SKIP] Requires NVIDIA_EMBEDDING_API_KEY")
        return False
    
    from rag_app.services.faiss_service import FAISSService
    from rag_app.services.nvidia_embedding_service import NvidiaEmbeddingService
    
    embedding_service = NvidiaEmbeddingService()
    faiss_service = FAISSService(embedding_service=embedding_service)
    
    # Create small test chunks
    test_chunks = [
        {"content": "RoDTEP rates for textile exports", "page_number": 1, "source_file": "test.pdf"},
        {"content": "Customs duty on imported electronics", "page_number": 2, "source_file": "test.pdf"},
        {"content": "DGFT guidelines for export licenses", "page_number": 3, "source_file": "test.pdf"},
    ]
    
    start = time.time()
    faiss_service.add_documents(test_chunks)
    elapsed = time.time() - start
    
    print(f"  Added {len(test_chunks)} documents")
    print(f"  Index size: {faiss_service.index.ntotal}")
    print(f"  Time: {elapsed:.1f}s")
    
    # Test search
    results = faiss_service.search("textile export rates", top_k=2)
    print(f"  Search results: {len(results)}")
    for r in results:
        print(f"    - {r['content'][:50]}... (score: {r.get('score', 'N/A')})")
    
    print("\n  [OK] FAISS index working\n")
    return True


def test_full_pipeline():
    """Test full pipeline: parse -> embed -> index -> search."""
    print("=" * 60)
    print("4. Testing full pipeline (small PDF)...")
    print("=" * 60)
    
    api_key = os.getenv("NVIDIA_EMBEDDING_API_KEY", "")
    if not api_key or "your-nvidia" in api_key:
        print("  [SKIP] Requires NVIDIA_EMBEDDING_API_KEY")
        return False
    
    from rag_app.services.opendataloader_service import OpenDataLoaderService
    from rag_app.services.faiss_service import FAISSService
    from rag_app.services.nvidia_embedding_service import NvidiaEmbeddingService
    
    kb_path = Path(__file__).parent / "Knowlegebase" / "rag_documents" / "rag_documents"
    test_pdf = list(kb_path.glob("*.pdf"))[0]  # Use first PDF
    
    print(f"  Using: {test_pdf.name}")
    
    # Step 1: Parse
    loader = OpenDataLoaderService()
    result = loader.parse_pdf(str(test_pdf))
    chunks = result['chunks'][:10]  # Limit to 10 chunks for speed
    
    print(f"  Parsed: {len(chunks)} chunks (limited)")
    
    # Step 2: Embed + Index
    embedding_service = NvidiaEmbeddingService()
    faiss_service = FAISSService(embedding_service=embedding_service)
    
    start = time.time()
    faiss_service.add_documents(chunks)
    elapsed = time.time() - start
    
    print(f"  Indexed: {faiss_service.index.ntotal} documents in {elapsed:.1f}s")
    
    # Step 3: Search
    results = faiss_service.search("RoDTEP rates", top_k=3)
    print(f"\n  Search results for 'RoDTEP rates':")
    for i, r in enumerate(results):
        print(f"    {i+1}. {r['content'][:80]}...")
    
    print("\n  [OK] Full pipeline working\n")
    return True


if __name__ == "__main__":
    print("\nZenith Export AI - Pipeline Verification\n")
    
    results = {}
    results['opendataloader'] = test_opendataloader()
    results['embeddings'] = test_nvidia_embeddings()
    results['faiss'] = test_faiss_index()
    results['full_pipeline'] = test_full_pipeline()
    
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for name, passed in results.items():
        status = "[OK]" if passed else "[SKIP]"
        print(f"  {status} {name}")
    
    if not results['embeddings']:
        print("\nACTION REQUIRED:")
        print("  1. Get NVIDIA API key from https://build.nvidia.com")
        print("  2. Update .env: NVIDIA_EMBEDDING_API_KEY=nvapi-xxxxx")
        print("  3. Run this script again: python test_pipeline.py")
