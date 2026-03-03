"""
Step 4 — Hybrid Vector Store (FAISS + BM25 + RRF + Cross-Encoder)
Path A: BM25 for keyword/ID matching.
Path B: FAISS (Cosine Similarity) for semantic matching.
Fusion: Reciprocal Rank Fusion (RRF).
Reranker: Cross-Encoder for top-level refinement.
"""
import os
import pickle
import numpy as np
import faiss
from rank_bm25 import BM25Okapi
from sentence_transformers import CrossEncoder

FAISS_INDEX_PATH = "data/vector_store/index.faiss"
METADATA_PATH    = "data/vector_store/metadata.pkl"
BM25_INDEX_PATH  = "data/vector_store/bm25.pkl"
DIMENSION        = 384   # all-MiniLM-L6-v2 dimension

_reranker = None

def get_reranker():
    global _reranker
    if _reranker is None:
        print("[INFO] Loading Cross-Encoder: ms-marco-MiniLM-L-6-v2 ...")
        _reranker = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
    return _reranker


def _tokenize(text: str) -> list:
    """Tokenizer for BM25."""
    import re
    return re.findall(r'\b\w{2,}\b', text.lower())


def save_index(embeddings: np.ndarray, chunks: list):
    """Build and save FAISS and BM25 indices."""
    os.makedirs("data/vector_store", exist_ok=True)

    # 1. FAISS - Cosine Similarity (IndexFlatIP with normalized vectors)
    faiss.normalize_L2(embeddings)
    index = faiss.IndexFlatIP(DIMENSION)
    index.add(embeddings)
    faiss.write_index(index, FAISS_INDEX_PATH)

    # 2. BM25
    tokenized_corpus = [_tokenize(c["text"]) for c in chunks]
    bm25 = BM25Okapi(tokenized_corpus)
    with open(BM25_INDEX_PATH, "wb") as f:
        pickle.dump(bm25, f)

    # 3. Metadata
    with open(METADATA_PATH, "wb") as f:
        pickle.dump(chunks, f)

    print(f"[OK]  FAISS index saved: {index.ntotal} vectors")
    print(f"[OK]  BM25 index saved.")


def load_indices():
    """Load all indices and metadata."""
    if not os.path.exists(FAISS_INDEX_PATH):
        raise FileNotFoundError("Indices not found. Run ingestion first.")
    
    index = faiss.read_index(FAISS_INDEX_PATH)
    with open(METADATA_PATH, "rb") as f:
        chunks = pickle.load(f)
    with open(BM25_INDEX_PATH, "rb") as f:
        bm25 = pickle.load(f)
        
    return index, chunks, bm25


def update_index(new_embeddings: np.ndarray, new_chunks: list):
    """Incremental update of indices."""
    try:
        index, chunks, bm25 = load_indices()
    except FileNotFoundError:
        save_index(new_embeddings, new_chunks)
        return

    # Update FAISS
    faiss.normalize_L2(new_embeddings)
    index.add(new_embeddings)
    faiss.write_index(index, FAISS_INDEX_PATH)

    # Update metadata
    chunks.extend(new_chunks)
    with open(METADATA_PATH, "wb") as f:
        pickle.dump(chunks, f)

    # Update BM25 (re-build is necessary for rank_bm25)
    tokenized_corpus = [_tokenize(c["text"]) for c in chunks]
    bm25 = BM25Okapi(tokenized_corpus)
    with open(BM25_INDEX_PATH, "wb") as f:
        pickle.dump(bm25, f)

    print(f"[OK]  Index updated: {index.ntotal} total vectors.")


def reciprocal_rank_fusion(results_semantic, results_keyword, k=60):
    """Fuse results using RRF."""
    fused_scores = {}
    
    # Path B: Semantic
    for rank, idx in enumerate(results_semantic):
        fused_scores[idx] = fused_scores.get(idx, 0) + 1 / (k + rank + 1)
        
    # Path A: Keyword
    for rank, idx in enumerate(results_keyword):
        fused_scores[idx] = fused_scores.get(idx, 0) + 1 / (k + rank + 1)
        
    # Sort by score descending
    fused_indices = sorted(fused_scores.keys(), key=lambda x: fused_scores[x], reverse=True)
    return fused_indices


def hybrid_search(query: str, query_vector: np.ndarray, top_k: int = 5) -> list:
    """Hybrid Search with RRF and Cross-Encoder Reranking."""
    try:
        index, chunks, bm25 = load_indices()
    except FileNotFoundError:
        return []

    # 1. Semantic Search (top 20)
    faiss.normalize_L2(query_vector)
    distances, semantic_indices = index.search(query_vector, min(20, index.ntotal))
    semantic_ids = semantic_indices[0].tolist()

    # 2. Keyword Search (top 20)
    tokenized_query = _tokenize(query)
    keyword_scores = bm25.get_scores(tokenized_query)
    keyword_ids = np.argsort(keyword_scores)[::-1][:20].tolist()

    # 3. RRF Fusion
    fused_ids = reciprocal_rank_fusion(semantic_ids, keyword_ids)
    
    # 4. Filter top 10 for reranking
    candidate_ids = fused_ids[:10]
    candidates = [chunks[i] for i in candidate_ids]

    # 5. Cross-Encoder Reranking
    reranker = get_reranker()
    pairs = [[query, c["text"]] for c in candidates]
    scores = reranker.predict(pairs)
    
    # Sort candidates by reranker score
    for i, score in enumerate(scores):
        candidates[i]["rerank_score"] = float(score)
        # Map rerank_score to a distance-like 'score' for retrieval_agent compatibility
        # Higher rerank_score = more relevant → lower distance score
        candidates[i]["score"] = max(0.0, 1.0 - float(score) / 10.0)
    
    final_results = sorted(candidates, key=lambda x: x["rerank_score"], reverse=True)
    
    return final_results[:top_k]


def index_exists() -> bool:
    return os.path.exists(FAISS_INDEX_PATH) and os.path.exists(METADATA_PATH)
