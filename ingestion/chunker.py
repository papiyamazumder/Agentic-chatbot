"""
Step 2 — Chunk documents into smaller pieces
Uses LangChain's RecursiveCharacterTextSplitter for semantic chunking.
Target chunk size: 1000, overlap: 100.
"""
from langchain_text_splitters import RecursiveCharacterTextSplitter


def chunk_documents(documents: list, chunk_size: int = 1000, overlap: int = 100) -> list:
    """
    Input:  list of {"text": str, "source": str}
    Output: list of {"chunk_id": int, "text": str, "source": str, "chunk_pos": str}
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        length_function=len,
        is_separator_regex=False,
    )

    chunks = []
    chunk_id = 0

    for doc in documents:
        text = doc["text"]
        source = doc["source"]
        
        doc_chunks = splitter.split_text(text)
        total_chunks = len(doc_chunks)

        for i, chunk_text in enumerate(doc_chunks, 1):
            if chunk_text.strip():
                chunks.append({
                    "chunk_id": chunk_id,
                    "text": chunk_text.strip(),
                    "source": source,
                    "chunk_pos": f"Section {i} of {total_chunks}"
                })
                chunk_id += 1

    print(f"[INFO] Created {len(chunks)} chunks from {len(documents)} documents")
    return chunks
