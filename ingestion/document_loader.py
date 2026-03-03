"""
Step 1 — Load documents from /local_storage
Supports: PDF, Word (.docx), Excel (.xlsx), CSV, HTML, Markdown
Implement recursive scan of the directory.
"""
import os
import fitz           # PyMuPDF
import pandas as pd
from docx import Document


def load_all_documents(folder_path: str = "local_storage") -> list:
    """
    Reads all supported files from folder recursively.
    Returns list of dicts: {"text": str, "source": filename}
    """
    documents = []
    supported = (".pdf", ".docx", ".xlsx", ".csv", ".html", ".md")

    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
        print(f"[INFO] Created folder: {folder_path}")
        return documents

    # Recursive walk
    for root, _, files in os.walk(folder_path):
        for filename in files:
            if filename.lower().endswith(supported):
                filepath = os.path.join(root, filename)
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
                        continue

                    if text.strip():
                        # Use relative path as source identifier
                        rel_source = os.path.relpath(filepath, folder_path)
                        documents.append({"text": text, "source": rel_source})
                        print(f"[OK]  Loaded: {rel_source}  ({len(text)} chars)")
                except Exception as e:
                    print(f"[ERR] Failed: {filename} → {e}")

    return documents


def _load_pdf(filepath):
    doc = fitz.open(filepath)
    return "\n".join(page.get_text() for page in doc)


def _load_docx(filepath):
    doc = Document(filepath)
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def _load_excel(filepath):
    df = pd.read_excel(filepath)
    return df.to_string(index=False)


def _load_csv(filepath):
    df = pd.read_csv(filepath)
    return df.to_string(index=False)


def _load_html(filepath):
    import re
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        html = f.read()
    # Basic text extraction from HTML
    text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
    text = re.sub(r'<[^>]+>', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def _load_md(filepath):
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        return f.read()
