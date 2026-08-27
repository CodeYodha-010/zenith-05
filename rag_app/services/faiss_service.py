import numpy as np
import faiss
import logging

logger = logging.getLogger('rag_pipeline')

class FAISSService:
    """
    Manages vector indices and similarity search using Facebook AI Similarity Search (FAISS).
    Does not require any API keys.
    """
    def __init__(self, dimension: int = 2048):  # Adjust dimension based on the actual embedding model
        self.dimension = dimension
        # L2-distance based index wrapped for inner product (cosine similarity if normalized)
        # We will use IndexFlatL2 for simplicity or IndexFlatIP if we normalize vectors.
        # Nomic/Llama embeddings are usually better suited for inner product if normalized
        self.index = faiss.IndexFlatIP(self.dimension)
        logger.info(f"Initialized FAISS index with dimension {self.dimension}")

    def add_vectors(self, vectors):
        """
        Add a list or numpy array of vectors to the index. Vectors should be normalized for Cosine Sim.
        """
        if len(vectors) == 0:
            return
            
        # Convert to numpy array if it is a list
        if not isinstance(vectors, np.ndarray):
            vectors = np.array(vectors, dtype=np.float32)
            
        # Ensure vectors are float32
        if vectors.dtype != np.float32:
            vectors = vectors.astype(np.float32)
            
        # Normalize vectors for cosine similarity
        faiss.normalize_L2(vectors)
        self.index.add(vectors)
        logger.info(f"Added {len(vectors)} vectors to FAISS index. Total: {self.index.ntotal}")

    def search(self, query_vector, k: int = 5) -> tuple:
        """
        Search for top-k most similar vectors.
        Returns distances and indices of top matches.
        """
        if self.index.ntotal == 0:
            return np.array([]), np.array([])
            
        if not isinstance(query_vector, np.ndarray):
            query_vector = np.array(query_vector, dtype=np.float32)
            
        if query_vector.dtype != np.float32:
            query_vector = query_vector.astype(np.float32)
            
        faiss.normalize_L2(query_vector)
        distances, indices = self.index.search(query_vector, k)
        return distances, indices

    def reset_index(self):
        """Clears the FAISS index."""
        self.index.reset()
        logger.info("FAISS index has been reset.")

    def save(self, file_path: str):
        """Saves the FAISS index to disk."""
        faiss.write_index(self.index, file_path)
        logger.info(f"Saved FAISS index to {file_path}")

    def load(self, file_path: str):
        """Loads a FAISS index from disk."""
        self.index = faiss.read_index(file_path)
        self.dimension = self.index.d
        logger.info(f"Loaded FAISS index from {file_path} with dimension {self.dimension}")
