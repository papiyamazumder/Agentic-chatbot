"""
Watchdog Service — monitors /local_storage for new/modified files.
Triggers incremental ingestion.
"""
import time
import os
import threading
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from ingestion.document_loader import _load_pdf, _load_docx, _load_excel, _load_csv, _load_html, _load_md
from ingestion.chunker import chunk_documents
from ingestion.embedder import embed_chunks
from ingestion.vector_store import update_index

WATCH_DIR = "local_storage"
SUPPORTED = (".pdf", ".docx", ".xlsx", ".csv", ".html", ".md")


class IngestionHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if not event.is_directory and event.src_path.lower().endswith(SUPPORTED):
            self._process_file(event.src_path)

    def on_created(self, event):
        if not event.is_directory and event.src_path.lower().endswith(SUPPORTED):
            self._process_file(event.src_path)

    def _process_file(self, filepath):
        # Wait a bit for file to be fully written
        time.sleep(1)
        filename = os.path.basename(filepath)
        print(f"[WATCHDOG] Change detected: {filename}. Processing...")
        
        ext = filename.lower().split(".")[-1]
        try:
            if ext == "pdf":
                text = _load_pdf(filepath)
            elif ext == "docx":
                text = _load_docx(filepath)
            elif ext in ("xlsx", "xls"):
                text = _load_excel(filepath)
            elif ext == "csv":
                text = _load_csv(filepath)
            elif ext == "html":
                text = _load_html(filepath)
            elif ext == "md":
                text = _load_md(filepath)
            else:
                return

            if text.strip():
                rel_source = os.path.relpath(filepath, WATCH_DIR)
                doc = [{"text": text, "source": rel_source}]
                chunks = chunk_documents(doc)
                embeddings, chunks = embed_chunks(chunks)
                update_index(embeddings, chunks)
                print(f"[WATCHDOG] Incrementally added: {filename}")
        except Exception as e:
            print(f"[WATCHDOG] ERROR processing {filename}: {e}")


def start_watchdog():
    if not os.path.exists(WATCH_DIR):
        os.makedirs(WATCH_DIR)
        
    event_handler = IngestionHandler()
    observer = Observer()
    observer.schedule(event_handler, WATCH_DIR, recursive=True)
    observer.start()
    print(f"[WATCHDOG] Monitoring {WATCH_DIR} for changes...")
    
    # Run in background
    # Note: Keep the thread alive if this is the main entry point, 
    # but for FastAPI it should be started in a separate thread.
    return observer
