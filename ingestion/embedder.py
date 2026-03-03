"""
Step 3 — Generate embeddings using HuggingFace sentence-transformers
Model: all-MiniLM-L6-v2 (free, runs locally, no API key needed)
Produces 384-dimensional vectors
"""
import numpy as np
from sentence_transformers import SentenceTransformer

# Load once at module level — cached after first load
_model = None


def get_model():
    global _model
    if _model is None:
        print("[INFO] Loading HuggingFace embedding model: all-MiniLM-L6-v2 ...")
        _model = SentenceTransformer("all-MiniLM-L6-v2")
        print("[OK]  Embedding model loaded.")
    return _model


def embed_chunks(chunks: list) -> tuple:
    """
    Input:  list of chunk dicts with "text" key
    Output: (numpy array of embeddings, list of chunk dicts)
    """
    model = get_model()
    texts = [c["text"] for c in chunks]

    print(f"[INFO] Embedding {len(texts)} chunks ...")
    embeddings = model.encode(texts, batch_size=32, show_progress_bar=True)
    embeddings = np.array(embeddings).astype("float32")

    print(f"[OK]  Embeddings shape: {embeddings.shape}")
    return embeddings, chunks


def embed_query(query: str) -> np.ndarray:
    """
    Embed a single user query at search time.
    Returns float32 numpy array of shape (1, 384)
    """
    model = get_model()
    vec = model.encode([query])
    return np.array(vec).astype("float32")
