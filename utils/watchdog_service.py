"""
Watchdog Service — monitors document directories for new/modified files.
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

WATCH_DIRS = ["local_storage", "data/raw_docs", "Project_Flowchart"]
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
                # Determine which watch dir this file belongs to
                for watch_dir in WATCH_DIRS:
                    abs_watch = os.path.abspath(watch_dir)
                    abs_file = os.path.abspath(filepath)
                    if abs_file.startswith(abs_watch):
                        rel_source = os.path.relpath(filepath, watch_dir)
                        break
                else:
                    rel_source = filename

                doc = [{"text": text, "source": rel_source}]
                chunks = chunk_documents(doc)
                embeddings, chunks = embed_chunks(chunks)
                update_index(embeddings, chunks)
                print(f"[WATCHDOG] Incrementally added: {filename}")
        except Exception as e:
            print(f"[WATCHDOG] ERROR processing {filename}: {e}")


def start_watchdog():
    event_handler = IngestionHandler()
    observer = Observer()
    
    for watch_dir in WATCH_DIRS:
        if not os.path.exists(watch_dir):
            os.makedirs(watch_dir)
        observer.schedule(event_handler, watch_dir, recursive=True)
        print(f"[WATCHDOG] Monitoring {watch_dir} for changes...")
    
    observer.start()
    return observer
