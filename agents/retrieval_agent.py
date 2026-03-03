"""
Retrieval Agent — Production-Grade RAG Pipeline
Pipeline: Search → Rank → Filter → Consolidate → Cite → (General Knowledge Fallback)

Features:
  - Searches ALL indexed sources (PDF, Excel, CSV, Word, HTML, MD) simultaneously
  - Hybrid ranking (semantic L2 + keyword boost)
  - Score-based filtering to discard noise
  - Multi-source consolidation with deduplication
  - Source file citations in every answer
  - Last-5-message context memory for follow-up questions
  - General knowledge fallback via LLM pretrained data
  - Concise bullet-point answers with actionable items
"""
import os
import logging
from dotenv import load_dotenv
from utils.llm_client import get_llm_client, get_model_name
from ingestion.embedder import embed_query
from ingestion.vector_store import hybrid_search, index_exists

load_dotenv()
logger = logging.getLogger(__name__)

# Score threshold — chunks above this L2 distance are considered low-relevance
RELEVANCE_THRESHOLD = 1.8


# ── LLM Client (Centralized) ──────────────────────────
def get_retrieval_client():
    return get_llm_client()


def _build_history_messages(chat_history: list) -> list:
    """Convert last 5 messages into LLM message format for context memory."""
    if not chat_history:
        return []
    # Take up to 10 messages (5 user/assistant pairs)
    recent = chat_history[-10:]
    messages = []
    for msg in recent:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role in ("user", "assistant") and content:
            # Truncate long messages to avoid context overflow
            messages.append({"role": role, "content": content[:500]})
    return messages


def _run_general_knowledge(query: str, chat_history: list) -> dict:
    """Fallback: Use LLM's pretrained knowledge for general queries."""
    client = get_retrieval_client()
    model = get_model_name()

    system_prompt = """You are a knowledgeable AI assistant for KPMG.
The user's question was NOT found in the enterprise knowledge base.
Use your general knowledge to answer helpfully.

Rules:
1. Answer in brief bullet points — be concise and actionable.
2. Clearly state that this answer is from GENERAL KNOWLEDGE, not from enterprise documents.
3. If the question is about a specific vocabulary, concept, or general topic, explain it clearly.
4. Keep answers professional and relevant to a PMO/enterprise context when applicable.
5. Start your response with: 🌐 **General Knowledge** (not from indexed documents)"""

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(_build_history_messages(chat_history))
    messages.append({"role": "user", "content": query})

    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.4,
            max_tokens=1000,
        )
        answer = response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"[General Knowledge] LLM call failed: {e}")
        answer = f"⚠️ I couldn't find this in the knowledge base, and the general knowledge query also failed: {str(e)}"

    return {
        "answer": answer,
        "sources": ["General Knowledge (LLM pretrained data)"],
        "agent": "retrieval"
    }


# ── Main agent function ──────────────────────────────
def run_retrieval_agent(query: str, session_id: str = None, upload_only: bool = False, chat_history: list = None) -> dict:
    """
    Production-grade RAG pipeline:
    1. SEARCH  — Embed query, search across ALL indexed sources simultaneously
    2. RANK    — Score every chunk by hybrid (semantic L2 + keyword boost)
    3. FILTER  — Discard chunks with score above RELEVANCE_THRESHOLD
    4. CONSOLIDATE — Group top-scoring chunks (even from different files)
    5. CITE    — Attach file name to each chunk in the LLM prompt
    6. GENERATE — LLM produces grounded answer with source citations
    7. FALLBACK — If no relevant docs found, use LLM general knowledge
    """
    if chat_history is None:
        chat_history = []

    has_main_index = index_exists() and not upload_only
    has_uploads = False

    # Check if session has uploaded docs
    if session_id:
        from ingestion.upload_handler import get_session_stats
        stats = get_session_stats(session_id)
        has_uploads = stats["files"] > 0

    if not has_main_index and not has_uploads:
        if upload_only:
            return {
                "answer": "No uploaded documents found for your session. Please upload a document first.",
                "sources": [],
                "agent": "retrieval"
            }
        # No index at all — try general knowledge
        return _run_general_knowledge(query, chat_history)

    # ── STEP 1: SEARCH — Embed & search across ALL sources ──
    query_vector = embed_query(query)  # shape (1, 384)

    main_results = []
    if has_main_index:
        main_results = hybrid_search(query, query_vector, top_k=10)

    upload_results = []
    if has_uploads and session_id:
        from ingestion.upload_handler import search_uploaded_docs
        upload_results = search_uploaded_docs(
            session_id, query, query_vector,
            top_k=3 if not upload_only else 7
        )

    # ── STEP 2: RANK — Merge and sort by hybrid score (lower = better) ──
    all_results = upload_results + main_results
    all_results = sorted(all_results, key=lambda x: x.get("score", 999.0))

    if not all_results:
        # No results at all — fallback to general knowledge
        return _run_general_knowledge(query, chat_history)

    # ── STEP 3: FILTER — Discard low-relevance chunks ──
    filtered = [r for r in all_results if r.get("score", 999.0) < RELEVANCE_THRESHOLD]

    # If filtering removed everything, try general knowledge instead
    if not filtered:
        logger.info("[Retrieval] All chunks below threshold — falling back to general knowledge")
        return _run_general_knowledge(query, chat_history)

    # ── STEP 4: CONSOLIDATE — Group top chunks across files ──
    seen_texts = set()
    consolidated = []
    sources_used = []

    for r in filtered[:8]:
        text_key = r["text"][:100]  # Dedup by first 100 chars
        if text_key not in seen_texts:
            seen_texts.add(text_key)
            consolidated.append(r)
            if r["source"] not in sources_used:
                sources_used.append(r["source"])
        if len(consolidated) >= 6:
            break

    # ── STEP 5: CITE — Build context with file-name citations ──
    context_parts = []
    for i, r in enumerate(consolidated, 1):
        is_upload = "📎 " if r.get("is_upload") else ""
        pos = r.get("chunk_pos", "")
        pos_str = f" ({pos})" if pos else ""
        context_parts.append(
            f"[Source {i} — {is_upload}{r['source']}{pos_str}]\n{r['text']}"
        )

    context = "\n\n".join(context_parts)
    source_list_str = ", ".join(f"📄 {s}" for s in sources_used)

    # ── STEP 6: GENERATE — LLM produces grounded, concise answer ──
    system_prompt = """You are an expert enterprise AI Assistant for KPMG.
Answer the user's question using ONLY the document context below.

OUTPUT FORMAT:
1. Start with a 1-line summary answer.
2. Then provide BRIEF BULLET POINTS with key details/actions.
3. If data is tabular (from Excel/CSV), show a clean markdown table.
4. End with: 📄 Sources: [list file names used]

CRITICAL RULES:
- If the answer is NOT in the context, say: "I couldn't find this in the knowledge base" and suggest using General Knowledge mode.
- NEVER invent data, names, dates, or numbers.
- Be CONCISE — bullet points, not paragraphs.
- ALWAYS cite source file names."""

    # Build message list with conversation history for follow-up context
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(_build_history_messages(chat_history))

    user_prompt = f"""Documents found across the knowledge base:
{context}

---
Available sources: {source_list_str}

Question: {query}

Answer concisely with bullet points. Cite sources."""

    messages.append({"role": "user", "content": user_prompt})

    client = get_retrieval_client()
    model = get_model_name()

    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.15,
            max_tokens=1500,
        )
        answer = response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"[Retrieval] LLM call failed: {e}")
        answer = (
            f"⚠️ LLM processing failed ({str(e)}), but here are the most relevant snippets:\n\n"
            + "\n\n---\n\n".join(f"**{r['source']}:**\n{r['text']}" for r in consolidated[:3])
        )

    return {
        "answer":  answer,
        "sources": sources_used,
        "agent":   "retrieval"
    }
