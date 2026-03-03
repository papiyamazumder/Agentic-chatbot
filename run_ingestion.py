"""
run_ingestion.py — Full bootstrap of the /local_storage directory.
Usage: python run_ingestion.py
"""
import sys
import os
import time

from ingestion.document_loader import load_all_documents
from ingestion.chunker import chunk_documents
from ingestion.embedder import embed_chunks
from ingestion.vector_store import save_index


def run_ingestion(folder: str = "local_storage"):
    print("=" * 60)
    print("  KPMG PMO Chatbot — Persistent Hybrid RAG Bootstrap")
    print("=" * 60)

    start = time.time()
    
    # ── Step 1: Load documents ──────────────────────
    print(f"\n[STEP 1] Loading documents from {folder}...")
    all_documents = load_all_documents(folder_path=folder)

    if not all_documents:
        print(f"\n⚠️  No documents found in {folder}.")
        return

    # ── Step 2: Chunk ───────────────────────────────
    print(f"\n[STEP 2] Chunking {len(all_documents)} documents...")
    chunks = chunk_documents(all_documents)

    # ── Step 3: Embed ───────────────────────────────
    print(f"\n[STEP 3] Embedding {len(chunks)} chunks...")
    embeddings, chunks = embed_chunks(chunks)

    # ── Step 4: Save ────────────────────────────────
    print("\n[STEP 4] Building FAISS & BM25 indices...")
    save_index(embeddings, chunks)

    elapsed = time.time() - start
    print(f"\n{'=' * 60}")
    print(f"  ✅ Bootstrapping complete in {elapsed:.1f}s")
    print(f"  📄 Total Documents: {len(all_documents)}")
    print(f"  🧩 Total Chunks:    {len(chunks)}")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    run_ingestion()
