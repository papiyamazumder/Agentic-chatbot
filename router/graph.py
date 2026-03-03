"""
LangGraph Router — the brain of the multi-agent system
Builds a StateGraph with 4 agent nodes + hybrid 3-tier routing

Routing Strategy (in order):
  Tier 1: Keyword matching   — fast, free, deterministic (handles ~70% of queries)
  Tier 2: Embedding similarity — semantic cosine sim with all-MiniLM-L6-v2 anchors
  Tier 3: Groq LLM classifier — definitive fallback for truly ambiguous queries

Flow:
  User query
    → Tier 1 keyword hit?     → route immediately
    → else Tier 2 embed sim > 0.45? → route
    → else Tier 3 Groq LLM   → route
    → dispatched to:
        ├── retrieval_agent  (doc questions, SOPs, reports)
        ├── api_agent        (KPI data, metrics, dashboards)
        ├── helpdesk_agent   (IT tickets — create, check, escalate)
        └── workflow_agent   (email, approval, RAID log, system logs)
"""
import os
import numpy as np
from typing import TypedDict, Literal
from dotenv import load_dotenv

from langgraph.graph import StateGraph, END

from agents.retrieval_agent  import run_retrieval_agent
from agents.api_agent        import run_api_agent
from agents.helpdesk_agent   import run_helpdesk_agent
from agents.workflow_agent   import run_workflow_agent

load_dotenv()

AgentType = Literal["retrieval", "api", "helpdesk", "workflow"]


# ── Shared state schema for the graph ────────────────
class ChatState(TypedDict):
    query:        str
    session_id:   str
    agent_used:   str
    answer:       str
    sources:      list
    chat_history: list


# ════════════════════════════════════════════════════
# TIER 1 — Keyword Matching (fast, free, deterministic)
# ════════════════════════════════════════════════════

HELPDESK_KEYWORDS = [
    "ticket", "raise", "incident", "helpdesk", "support",
    "it issue", "it problem", "broken", "not working",
    "access denied", "locked out", "reset password",
    "hardware", "laptop", "monitor", "printer",
    "check status", "ticket status", "inc",
    "vpn", "network", "software install", "permission",
    "unable to", "can't access", "cannot access", "error message",
]

WORKFLOW_KEYWORDS = [
    "email", "notify", "send", "alert",
    "approval", "approve", "sign off", "sign-off",
    "raid", "risk register", "risk log", "action item",
    "log entry", "decision log",
    "system log", "error log", "app insights",
    "escalate", "notify team",
    "onboard", "onboarding", "new joiner", "new hire", "new resource",
    "offboard", "offboarding", "release resource", "exit", "last working day",
    "tag resource", "tagging", "re-tag", "reallocate", "reassign", "move resource",
    "employee id", "emp id", "check in", "check-in", "check out", "check-out",
    "spr-", "spr ", "assign", "transfer", "deployment",
]

API_KEYWORDS = [
    "kpi", "metric", "dashboard", "performance", "score",
    "utilisation", "utilization", "velocity", "burn rate",
    "budget", "milestone", "completion", "rate", "percentage",
    "how many", "current status", "number",
    "sprint", "jira", "project data"
]

RETRIEVAL_KEYWORDS = [
    "document", "sop", "report", "pdf", "what does", "what is",
    "explain", "summarise", "summarize", "find", "search",
    "show me", "tell me about", "according to", "based on",
    "meeting", "notes", "policy", "procedure", "guideline",
    "ai", "ml", "rag", "architecture", "build guide", "scratch",
    "libraries", "huggingface", "model", "roadmap", "overview",
    "process", "workflow documentation", "handbook", "standard",
    "how to", "steps to", "describe",
]


def _keyword_route(query: str) -> AgentType | None:
    """
    Tier 1: Fast keyword matching.
    Priority: helpdesk > workflow > api > retrieval
    """
    q = query.lower()
    if any(kw in q for kw in HELPDESK_KEYWORDS):
        return "helpdesk"
    if any(kw in q for kw in WORKFLOW_KEYWORDS):
        return "workflow"
    if any(kw in q for kw in API_KEYWORDS):
        return "api"
    if any(kw in q for kw in RETRIEVAL_KEYWORDS):
        return "retrieval"
    return None


# ════════════════════════════════════════════════════
# TIER 2 — Embedding Cosine Similarity (semantic)
# ════════════════════════════════════════════════════

AGENT_DESCRIPTIONS = {
    "retrieval": [
        "What does the SOP say about risk management?",
        "Summarize the Q3 delivery report",
        "Find the policy on data handling",
        "Explain the onboarding procedure from the handbook",
        "What were the key points in the last meeting notes?",
        "Tell me about the project guidelines document",
    ],
    "api": [
        "What is the current sprint velocity?",
        "Show me the KPI dashboard metrics",
        "What is the budget burn rate this quarter?",
        "How many open risk items are there?",
        "What is our resource utilisation score?",
        "Give me the milestone completion percentage",
        "What is the delivery risk score for Project Alpha?",
        "Show me the Jira sprint data",
    ],
    "helpdesk": [
        "Create a helpdesk ticket for the login issue",
        "My VPN is not connecting, please help",
        "Check the status of ticket INC0010001",
        "Show me all open IT support tickets",
        "Escalate the database incident to priority 1",
        "My laptop screen is flickering, raise a ticket",
        "I can't access the shared drive, need IT support",
    ],
    "workflow": [
        "Send an email to the team about the deployment delay",
        "I need to raise an approval for the budget change",
        "Log this as a RAID risk item",
        "Notify stakeholders about the milestone delay",
        "Check the system error logs from this morning",
        "Post a notification to the Teams channel",
        "Add a decision entry to the RAID log",
    ],
}

_anchor_embeddings: dict | None = None


def _build_anchor_embeddings() -> dict:
    """Embed all anchor sentences for each agent. Called once and cached."""
    from ingestion.embedder import get_model
    model = get_model()
    anchors = {}
    for agent, sentences in AGENT_DESCRIPTIONS.items():
        vecs = model.encode(sentences)
        anchors[agent] = np.array(vecs).astype("float32")
    return anchors


def _get_anchor_embeddings() -> dict:
    global _anchor_embeddings
    if _anchor_embeddings is None:
        _anchor_embeddings = _build_anchor_embeddings()
    return _anchor_embeddings


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def _semantic_route_embedding(query: str, threshold: float = 0.45) -> AgentType | None:
    """Tier 2: Embed query + cosine sim vs agent anchors."""
    from ingestion.embedder import get_model
    model = get_model()
    query_vec = model.encode([query])[0]
    anchors   = _get_anchor_embeddings()

    best_agent = None
    best_score = -1.0
    for agent, anchor_matrix in anchors.items():
        sims  = [_cosine_similarity(query_vec, anchor) for anchor in anchor_matrix]
        score = max(sims)
        if score > best_score:
            best_score = score
            best_agent = agent

    if best_score >= threshold:
        print(f"[Router] Tier 2 (embedding) → {best_agent}  (score={best_score:.3f})")
        return best_agent
    print(f"[Router] Tier 2 embedding score too low ({best_score:.3f}) → escalating to Tier 3")
    return None


# ════════════════════════════════════════════════════
# TIER 3 — Groq LLM Classifier (definitive fallback)
# ════════════════════════════════════════════════════

def _llm_route_fallback(query: str) -> AgentType:
    """Tier 3: Ask Groq to classify the intent."""
    from groq import Groq
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    model  = os.getenv("GROQ_MODEL") or "llama-3.1-8b-instant"

    prompt = f"""You are a query router for a KPMG enterprise chatbot.
Classify the user query into EXACTLY ONE of these four agents:

- retrieval  → questions about documents, SOPs, reports, policies, meeting notes
- api        → requests for KPI metrics, dashboards, performance scores, project data
- helpdesk   → IT support: reporting problems, ticket creation, checking ticket status
- workflow   → email notifications, approval requests, RAID log updates, system log queries

User query: "{query}"

Reply with ONLY one word: retrieval, api, helpdesk, or workflow."""

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=10,
    )
    decision = response.choices[0].message.content.strip().lower()

    if decision not in ("retrieval", "api", "helpdesk", "workflow"):
        decision = "retrieval"

    print(f"[Router] Tier 3 (LLM)      → {decision}")
    return decision  # type: ignore[return-value]


# ════════════════════════════════════════════════════
# MASTER ROUTE FUNCTION — 3-tier hybrid
# ════════════════════════════════════════════════════

def route_query(state: ChatState) -> AgentType:
    """3-tier hybrid router: keyword → embedding → LLM"""
    query = state["query"]

    result = _keyword_route(query)
    if result:
        print(f"[Router] Tier 1 (keyword)  → {result}")
        return result

    result = _semantic_route_embedding(query)
    if result:
        return result

    return _llm_route_fallback(query)


# ── Agent node wrappers ──────────────────────────────
def retrieval_node(state: ChatState) -> ChatState:
    result = run_retrieval_agent(state["query"], session_id=state.get("session_id"), chat_history=state.get("chat_history", []))
    return {**state, "answer": result["answer"], "sources": result["sources"], "agent_used": "Retrieval Agent"}

def api_node(state: ChatState) -> ChatState:
    result = run_api_agent(state["query"], chat_history=state.get("chat_history", []))
    return {**state, "answer": result["answer"], "sources": result["sources"], "agent_used": "API Agent"}

def helpdesk_node(state: ChatState) -> ChatState:
    result = run_helpdesk_agent(state["query"], chat_history=state.get("chat_history", []))
    return {**state, "answer": result["answer"], "sources": result["sources"], "agent_used": "Helpdesk Agent"}

def workflow_node(state: ChatState) -> ChatState:
    result = run_workflow_agent(state["query"], chat_history=state.get("chat_history", []))
    return {**state, "answer": result["answer"], "sources": result["sources"], "agent_used": "Workflow Agent"}


# ── Build LangGraph StateGraph ───────────────────────
def build_graph():
    graph = StateGraph(ChatState)

    graph.add_node("retrieval", retrieval_node)
    graph.add_node("api",       api_node)
    graph.add_node("helpdesk",  helpdesk_node)
    graph.add_node("workflow",  workflow_node)

    graph.set_conditional_entry_point(
        route_query,
        {
            "retrieval": "retrieval",
            "api":       "api",
            "helpdesk":  "helpdesk",
            "workflow":  "workflow",
        }
    )

    graph.add_edge("retrieval", END)
    graph.add_edge("api",       END)
    graph.add_edge("helpdesk",  END)
    graph.add_edge("workflow",  END)

    return graph.compile()


# ── Singleton compiled graph ─────────────────────────
_compiled_graph = None

def get_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph()
    return _compiled_graph


# ── Main entry point used by FastAPI ─────────────────
def run_chat(query: str, session_id: str = None, upload_only: bool = False, agent_override: str = None, chat_history: list = None) -> dict:
    if chat_history is None:
        chat_history = []

    if upload_only:
        from agents.retrieval_agent import run_retrieval_agent
        result = run_retrieval_agent(query, session_id=session_id, upload_only=True, chat_history=chat_history)
        return {
            "answer":     result["answer"],
            "agent_used": "Retrieval Agent",
            "sources":    result["sources"]
        }

    # If explicit override, bypass routing logic
    if agent_override and agent_override.lower() != "auto":
        node_map = {
            "docs":      retrieval_node,
            "kpis":      api_node,
            "helpdesk":   helpdesk_node,
            "automation": workflow_node
        }
        handler = node_map.get(agent_override.lower())
        if handler:
            initial_state: ChatState = {
                "query": query, "session_id": session_id or "",
                "agent_used": "", "answer": "", "sources": [],
                "chat_history": chat_history
            }
            final_state = handler(initial_state)
            return {
                "answer":     final_state["answer"],
                "agent_used": final_state["agent_used"],
                "sources":    final_state["sources"]
            }

    graph = get_graph()
    initial_state: ChatState = {
        "query": query, "session_id": session_id or "",
        "agent_used": "", "answer": "", "sources": [],
        "chat_history": chat_history
    }
    final_state = graph.invoke(initial_state)
    return {
        "answer":     final_state["answer"],
        "agent_used": final_state["agent_used"],
        "sources":    final_state["sources"]
    }
