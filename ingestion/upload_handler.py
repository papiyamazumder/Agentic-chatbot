"""
Upload Handler — session-scoped temporary document ingestion
Handles: upload file → parse → chunk → embed → store in temp FAISS index per session

Each session gets its own FAISS index stored in /tmp/kpmg_uploads/{session_id}/
Auto-cleanup: temp files deleted when session cleared or on expiry

Supports: PDF, Word (.docx), Excel (.xlsx/.xls), CSV, text files, images (OCR placeholder)
"""
import os
import shutil
import pickle
import logging
import tempfile
import numpy as np
import faiss
from datetime import datetime

from ingestion.pdf_loader import _load_pdf, _load_docx, _load_excel, _load_csv
from ingestion.chunker import chunk_documents
from ingestion.embedder import get_model

logger = logging.getLogger(__name__)

UPLOAD_BASE_DIR = os.path.join(tempfile.gettempdir(), "kpmg_uploads")
DIMENSION = 384  # all-MiniLM-L6-v2


# ── Session-scoped temp store ────────────────────────
# In-memory registry: session_id → { "index": faiss.Index, "chunks": list, "files": list }
_session_stores: dict = {}


def _session_dir(session_id: str) -> str:
    """Get or create temp directory for a session."""
    path = os.path.join(UPLOAD_BASE_DIR, session_id)
    os.makedirs(path, exist_ok=True)
    return path


def _parse_file(filepath: str, filename: str) -> str:
    """Parse a file into raw text based on extension."""
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""

    try:
        if ext == "pdf":
            return _load_pdf(filepath)
        elif ext == "docx":
            return _load_docx(filepath)
        elif ext in ("xlsx", "xls"):
            return _load_excel(filepath)
        elif ext == "csv":
            return _load_csv(filepath)
        elif ext in ("txt", "md", "log"):
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        elif ext in ("png", "jpg", "jpeg", "gif", "bmp"):
            # Image OCR placeholder — returns a note for now
            # To enable: pip install pytesseract, and use pytesseract.image_to_string()
            return f"[Image file: {filename} — OCR not enabled. Install pytesseract for image text extraction.]"
        else:
            # Try reading as text
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
    except Exception as e:
        logger.error(f"Failed to parse {filename}: {e}")
        return ""


def ingest_uploaded_file(session_id: str, filename: str, file_bytes: bytes) -> dict:
    """
    Ingest an uploaded file into the session's temp FAISS index.

    Steps:
      1. Save file to temp directory
      2. Parse into text
      3. Chunk
      4. Embed with HuggingFace
      5. Add to session's FAISS index (create or append)

    Returns: { "status": str, "filename": str, "chunks": int, "total_files": int }
    """
    session_dir = _session_dir(session_id)

    # Step 1 — Save file to temp
    filepath = os.path.join(session_dir, filename)
    with open(filepath, "wb") as f:
        f.write(file_bytes)
    logger.info(f"[Upload] Saved: {filename} → {filepath}")

    # Step 2 — Parse
    text = _parse_file(filepath, filename)
    if not text.strip():
        return {
            "status": "error",
            "message": f"Could not extract text from {filename}",
            "filename": filename,
            "chunks": 0,
            "total_files": len(_get_session_files(session_id))
        }

    # Step 3 — Chunk
    doc = {"text": text, "source": f"📎 {filename} (uploaded)"}
    chunks = chunk_documents([doc])
    logger.info(f"[Upload] {filename} → {len(chunks)} chunks")

    # Step 4 — Embed
    model = get_model()
    texts = [c["text"] for c in chunks]
    embeddings = model.encode(texts, batch_size=32)
    embeddings = np.array(embeddings).astype("float32")

    # Step 5 — Add to session FAISS index
    if session_id not in _session_stores:
        _session_stores[session_id] = {
            "index": faiss.IndexFlatL2(DIMENSION),
            "chunks": [],
            "files": [],
            "keyword_index": {}, # token -> list of chunk indices
        }

    store = _session_stores[session_id]
    start_idx = len(store["chunks"])
    store["index"].add(embeddings)
    store["chunks"].extend(chunks)

    # Update keyword index
    from ingestion.vector_store import _tokenize
    for i, chunk in enumerate(chunks):
        global_idx = start_idx + i
        tokens = _tokenize(chunk["text"])
        for token in tokens:
            if token not in store["keyword_index"]:
                store["keyword_index"][token] = []
            store["keyword_index"][token].append(global_idx)
    if filename not in store["files"]:
        store["files"].append(filename)

    logger.info(f"[Upload] Session {session_id[:8]}...: {store['index'].ntotal} vectors, {len(store['files'])} files")

    return {
        "status": "success",
        "filename": filename,
        "chunks": len(chunks),
        "total_files": len(store["files"]),
        "total_vectors": store["index"].ntotal,
    }


def search_uploaded_docs(session_id: str, query: str, query_vector: np.ndarray, top_k: int = 3) -> list:
    """
    Search the session's temp FAISS index using hybrid approach.
    """
    if session_id not in _session_stores:
        return []

    store = _session_stores[session_id]
    if store["index"].ntotal == 0:
        return []

    # 1. Semantic Search
    distances, indices = store["index"].search(query_vector, min(top_k * 2, store["index"].ntotal))

    semantic_results = {}
    for dist, idx in zip(distances[0], indices[0]):
        if 0 <= idx < len(store["chunks"]):
            semantic_results[idx] = float(dist)

    # 2. Keyword Search
    from ingestion.vector_store import _tokenize
    query_tokens = _tokenize(query)
    keyword_hits = {}
    kw_index = store.get("keyword_index", {})
    for token in query_tokens:
        if token in kw_index:
            for idx in kw_index[token]:
                keyword_hits[idx] = keyword_hits.get(idx, 0) + 1

    # 3. Fusion & Ranking
    final_results = []
    all_indices = set(list(semantic_results.keys()) + list(keyword_hits.keys()))

    for idx in all_indices:
        chunk = dict(store["chunks"][idx])
        base_score = semantic_results.get(idx, 2.0)
        kw_count = keyword_hits.get(idx, 0)
        kw_boost = min(kw_count * 0.1, 0.5)
        
        chunk["score"] = base_score - kw_boost
        chunk["kw_matches"] = kw_count
        final_results.append(chunk)

    final_results = sorted(final_results, key=lambda x: x["score"])
    return final_results[:top_k]


def get_session_files(session_id: str) -> list[str]:
    """Get list of uploaded filenames for a session."""
    if session_id not in _session_stores:
        return []
    return _session_stores[session_id]["files"]


def _get_session_files(session_id: str) -> list[str]:
    return get_session_files(session_id)


def clear_session(session_id: str):
    """Delete all temp files and FAISS index for a session."""
    # Remove in-memory store
    if session_id in _session_stores:
        del _session_stores[session_id]
        logger.info(f"[Upload] Session {session_id[:8]}... cleared from memory")

    # Remove temp directory
    session_dir = os.path.join(UPLOAD_BASE_DIR, session_id)
    if os.path.exists(session_dir):
        shutil.rmtree(session_dir)
        logger.info(f"[Upload] Temp files deleted: {session_dir}")


def get_session_stats(session_id: str) -> dict:
    """Get stats for a session's uploaded documents."""
    if session_id not in _session_stores:
        return {"files": 0, "vectors": 0, "chunks": 0}

    store = _session_stores[session_id]
    return {
        "files": len(store["files"]),
        "vectors": store["index"].ntotal,
        "chunks": len(store["chunks"]),
        "filenames": store["files"],
    }
