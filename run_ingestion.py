"""
run_ingestion.py — Full bootstrap of all document directories.
Usage: python run_ingestion.py
"""
import sys
import os
import time

from ingestion.document_loader import load_all_documents
from ingestion.chunker import chunk_documents
from ingestion.embedder import embed_chunks
from ingestion.vector_store import save_index

# All directories to scan for documents
SCAN_DIRS = [
    "local_storage",
    "data/raw_docs",
    "Project_Flowchart",
]


def run_ingestion(folder: str = None):
    print("=" * 60)
    print("  KPMG PMO Chatbot — Persistent Hybrid RAG Bootstrap")
    print("=" * 60)

    start = time.time()

    # ── Step 1: Load documents from ALL directories ──────
    all_documents = []
    folders = [folder] if folder else SCAN_DIRS

    for scan_dir in folders:
        if os.path.exists(scan_dir):
            print(f"\n[STEP 1] Loading documents from {scan_dir}...")
            docs = load_all_documents(folder_path=scan_dir)
            all_documents.extend(docs)
            print(f"         → {len(docs)} documents found in {scan_dir}")
        else:
            print(f"[STEP 1] Skipped (not found): {scan_dir}")

    if not all_documents:
        print(f"\n⚠️  No documents found in any directory.")
        return

    # ── Step 2: Chunk ───────────────────────────────
    print(f"\n[STEP 2] Chunking {len(all_documents)} documents (size=800, overlap=100)...")
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
    print(f"  📂 Directories:     {', '.join(folders)}")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    run_ingestion()
