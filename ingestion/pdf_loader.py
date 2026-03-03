"""
Step 1 — Load documents from /data/raw_docs
Supports: PDF, Word (.docx), Excel (.xlsx), CSV
"""
import os
import fitz           # PyMuPDF
import pandas as pd
from docx import Document


def load_all_documents(folder_path: str = "data/raw_docs") -> list:
    """
    Reads all supported files from folder.
    Returns list of dicts: {"text": str, "source": filename}
    """
    documents = []
    supported = (".pdf", ".docx", ".xlsx", ".csv", ".html", ".md")

    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
        print(f"[INFO] Created folder: {folder_path}")
        return documents

    files = [f for f in os.listdir(folder_path) if f.lower().endswith(supported)]
    print(f"[INFO] Found {len(files)} files in {folder_path}")

    for filename in files:
        filepath = os.path.join(folder_path, filename)
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
                documents.append({"text": text, "source": filename})
                print(f"[OK]  Loaded: {filename}  ({len(text)} chars)")
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
