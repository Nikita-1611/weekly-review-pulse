from sentence_transformers import SentenceTransformer
from typing import List
import numpy as np

MODEL_NAME = "BAAI/bge-small-en-v1.5"

class ReviewEmbedder:
    def __init__(self):
        # Using the local BAAI/bge-small-en-v1.5 model as defined in architecture
        self.model = SentenceTransformer(MODEL_NAME)
        
    def embed_reviews(self, texts: List[str]) -> np.ndarray:
        """
        Converts a list of review texts into high-dimensional vectors.
        """
        if not texts:
            return np.array([])
            
        # Encode the text using the BGE model
        embeddings = self.model.encode(texts, show_progress_bar=False, normalize_embeddings=True)
        return embeddings

def embed_reviews(texts: List[str]) -> np.ndarray:
    """Wrapper function for easy access."""
    embedder = ReviewEmbedder()
    return embedder.embed_reviews(texts)
