import pytest
import os
import shutil
from ingestion.document_loader import load_all_documents

@pytest.fixture
def temp_docs_dir(tmp_path):
    """Create a temporary directory with various document types."""
    d = tmp_path / "test_local_storage"
    d.mkdir()
    (d / "test.txt").write_text("Hello World", encoding="utf-8")
    (d / "test.md").write_text("# Markdown", encoding="utf-8")
    # Subdirectory
    sub = d / "subdir"
    sub.mkdir()
    (sub / "inner.txt").write_text("Inner text", encoding="utf-8")
    return str(d)

def test_load_all_documents_traversal(temp_docs_dir):
    """Verify recursive document loading."""
    docs = load_all_documents(temp_docs_dir)
    # Filtered by supported extensions: .pdf, .docx, .xlsx, .csv, .html, .md
    # test.txt and inner.txt should be IGNORED. Only test.md should be loaded.
    assert len(docs) == 1
    assert docs[0]["source"] == "test.md"

def test_load_all_documents_empty_dir(tmp_path):
    """Test loading from an empty directory."""
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    docs = load_all_documents(str(empty_dir))
    assert len(docs) == 0

def test_load_all_documents_non_existent():
    """Test loading from a non-existent directory (should create it)."""
    path = "non_existent_test_dir_123"
    if os.path.exists(path):
        os.rmdir(path)
    
    docs = load_all_documents(path)
    assert len(docs) == 0
    assert os.path.exists(path)
    os.rmdir(path)
