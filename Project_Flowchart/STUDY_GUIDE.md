# KPMG PMO Chatbot — Study Guide (Interview + AI Concepts)

> Combined reference: 54 AI concepts, interview Q&A, agent details, and technical patterns.

---

## 🎯 Elevator Pitch

"I built a **multi-agent RAG chatbot** for KPMG PMO with **4 specialized agents** (retrieval, API, helpdesk, workflow), a **3-tier hybrid router** (keyword → embedding → LLM), **hybrid search** (FAISS + BM25 + RRF + Cross-Encoder reranking), **RBAC** with 3 roles, and **workflow automation** (onboarding/offboarding/tagging with manager approval notifications). Stack: Python, FastAPI, LangGraph, Groq LLaMA 3.1, FAISS, BM25, HuggingFace, Streamlit, Docker, Azure."

---

## 🤖 4 Agents — Quick Reference

| Agent | Triggers | Data Source | LLM Temp | Output |
|-------|----------|-------------|----------|--------|
| 🔍 Retrieval | "SOP", "document", "policy" | FAISS + BM25 + uploaded files | 0.2 | Grounded answer + sources |
| 📊 API | "KPI", "budget", "sprint" | Excel trackers, SQL, Jira | 0 + 0.3 | Formatted metrics |
| 🎫 Helpdesk | "ticket", "broken", "laptop" | ServiceNow | 0 | Ticket ID + status |
| ⚙️ Workflow | "email", "approve", "onboard" | Outlook, Teams, SharePoint | 0 | Confirmation message |

### Workflow Agent — 8 Sub-Actions

| Action | Connector | API | Access |
|--------|-----------|-----|--------|
| 📧 send_email | outlook | MS Graph | All roles |
| ✅ approve | teams | Webhook | Manager+ |
| 📋 raid_log | sharepoint | Graph Lists | Manager+ |
| 📊 system_logs | azure_insights | KQL REST | Manager+ |
| 🤖 copilot | copilot_studio | HTTP POST | Manager+ |
| 👤 onboard | outlook | MS Graph | PMO Admin only |
| 📤 offboard | outlook | MS Graph | PMO Admin only |
| 🏷️ tag_resource | outlook | MS Graph | PMO Admin only |

---

## 🔀 3-Tier Hybrid Router

| Tier | Method | Speed | Cost | Accuracy |
|------|--------|-------|------|----------|
| 1 | Keyword scan (priority: helpdesk > workflow > api > retrieval) | <1ms | Free | High for obvious queries |
| 2 | all-MiniLM-L6-v2 cosine similarity (threshold 0.45) | ~5ms | Free | Handles paraphrasing |
| 3 | Groq LLM classification | ~300ms | Free tier | Handles anything |

---

## � Hybrid RAG Search Pipeline

```
Query → [Path A: FAISS cosine (top 20)] + [Path B: BM25 keyword (top 20)]
          ↓                                    ↓
     Reciprocal Rank Fusion (k=60) → top 10 candidates
          ↓
     Cross-Encoder Reranking (ms-marco-MiniLM-L-6-v2) → top 5 results
          ↓
     Groq LLaMA 3.1 generates grounded answer from context
```

---

## �🔐 RBAC — 3 Roles

| Role | Level | Agents | Vault Docs | Pages |
|------|-------|--------|-----------|-------|
| PMO Admin | 3 | All 4 | All 6 | All 7 pages |
| Manager | 2 | All 4 | 4/6 (Build Guide + Deployment unlocked) | All 7 pages |
| Resource | 1 | Retrieval + Helpdesk | 4/6 (AI Concepts, Architecture, Features, Tech Stack) | All 7 pages |

---

## 🧠 AI Concepts Table (54 Total)

### Foundation Concepts

| # | Concept | Definition | Project Usage |
|---|---------|-----------|--------------|
| 1 | LLM | Neural network trained on billions of tokens for text generation | Groq LLaMA 3.1 in all agents |
| 2 | Transformer | Architecture using self-attention for parallel text processing | LLaMA = decoder-only, MiniLM = encoder-only |
| 3 | Attention | Mechanism to focus on relevant input parts during generation | Inside both LLaMA and MiniLM |
| 4 | Inference | Running trained model for predictions (not training) | Every Groq API call |
| 5 | Token | Smallest unit of text for LLM processing (~4 chars = 1 token) | LLaMA 3.1 = 128K token context |

### Embeddings & Vector Search

| # | Concept | Definition | Project Usage |
|---|---------|-----------|--------------|
| 6 | Embedding | Text → fixed-size numerical vector capturing semantic meaning | all-MiniLM-L6-v2 → 384-dim vectors |
| 7 | Sentence Transformer | Transformer fine-tuned for sentence-level embeddings | HuggingFace sentence-transformers |
| 8 | Vector Database | DB optimized for similarity search on vectors | FAISS IndexFlatIP (cosine similarity) |
| 9 | Cosine Similarity | Angle between vectors (1.0 = identical meaning) | Router Tier 2 + FAISS search |
| 10 | BM25 | Best Matching 25 — probabilistic keyword ranking algorithm | BM25Okapi for keyword-based retrieval path |
| 11 | Nearest Neighbor | Finding K closest vectors to query | FAISS top_k=20 → fused to top 5 |
| 12 | Dimensionality | Number of values per vector (384 for MiniLM) | DIMENSION=384 constant |

### RAG (Retrieval-Augmented Generation)

| # | Concept | Definition | Project Usage |
|---|---------|-----------|--------------|
| 13 | RAG | Retrieve docs → inject as context → LLM generates grounded answer | Core pattern in Retrieval Agent |
| 14 | Chunking | Split docs into smaller pieces (800 chars, 100 overlap) | ingestion/chunker.py |
| 15 | Context Window | Max text LLM processes at once (128K for LLaMA) | ~5 chunks per query after reranking |
| 16 | Grounded Generation | LLM answers ONLY from provided context | System prompt enforcement |
| 17 | Hybrid Search | Combining semantic + keyword search for better recall | FAISS + BM25 + RRF fusion |
| 18 | Document Ingestion | Parse → Chunk → Embed → Store in FAISS + BM25 | ingestion/ pipeline |
| 19 | Reciprocal Rank Fusion | Merging ranked results from multiple sources by reciprocal rank | RRF with k=60 in vector_store.py |
| 20 | Cross-Encoder Reranking | Re-scoring candidate pairs with a cross-encoder model | ms-marco-MiniLM-L-6-v2 reranker |

### Agent Architecture

| # | Concept | Definition | Project Usage |
|---|---------|-----------|--------------|
| 21 | Multi-Agent System | Multiple specialized agents, each expert in one domain | 4 agents |
| 22 | Agent Orchestration | Coordinating which agent handles which request | LangGraph StateGraph |
| 23 | State Machine | Typed state dict flowing through nodes/edges | ChatState TypedDict |
| 24 | Conditional Routing | Different paths based on classification result | route_query() → 4 branches |
| 25 | Tool Use | Agent calling external APIs/functions | Connectors are agent tools |

### LLM Techniques

| # | Concept | Definition | Project Usage |
|---|---------|-----------|--------------|
| 26 | Prompt Engineering | Crafting instructions for LLM behavior | System prompts per agent |
| 27 | System Prompt | Instructions that set LLM behavior/persona | "Answer ONLY from context" |
| 28 | Temperature | Controls randomness (0=deterministic, 1=creative) | 0, 0.2, 0.3 per task |
| 29 | Few-Shot Learning | Examples in prompt to guide LLM output | JSON extraction examples |
| 30 | Zero-Shot Classification | LLM classifies without examples | Router Tier 3 |
| 31 | JSON Mode | Forcing LLM to output valid JSON | Helpdesk/Workflow extraction |
| 32 | Chain-of-Thought | Step-by-step reasoning in prompts | Complex metric explanations |

### NLP & Text Processing

| # | Concept | Definition | Project Usage |
|---|---------|-----------|--------------|
| 33 | Text-to-SQL | LLM generates SQL from natural language | API Agent queries |
| 34 | Named Entity Recognition | Extracting names/dates/IDs from text | Ticket fields extraction |
| 35 | Intent Classification | Determining user's goal from query | Router + agent action parsing |
| 36 | Keyword Extraction | Identifying important terms in text | Router Tier 1 |

### APIs, Frameworks & Infrastructure

| # | Concept | Definition | Project Usage |
|---|---------|-----------|--------------|
| 37 | REST API | HTTP endpoints for data exchange | FastAPI + all connectors |
| 38 | API Gateway | Central entry point for API requests | FastAPI /chat endpoint |
| 39 | Webhook | HTTP callback triggered by events | Teams approval cards |
| 40 | Middleware | Code between request and handler | CORS, auth validation |
| 41 | Containerization | Packaging app with dependencies | Docker + Dockerfile |
| 42 | CI/CD | Automated build + deploy pipeline | GitHub Actions → Azure |
| 43 | Microservices | App split into independent services | Frontend + Backend containers |
| 44 | Watchdog | File system monitoring for real-time changes | utils/watchdog_service.py monitors local_storage/ |

### HuggingFace & Model Details

| # | Concept | Definition | Project Usage |
|---|---------|-----------|--------------|
| 45 | HuggingFace Hub | Repository of pre-trained ML models | all-MiniLM-L6-v2 + ms-marco reranker |
| 46 | Model Card | Documentation for ML model capabilities | MiniLM: 22M params, 384 dims |
| 47 | Fine-Tuning | Training pre-trained model on specific data | MiniLM fine-tuned on 1B+ sentence pairs |
| 48 | Transfer Learning | Using knowledge from one task for another | MiniLM trained on NLI → used for search |
| 49 | Contrastive Learning | Training by comparing similar/dissimilar pairs | How MiniLM learned embeddings |

### Design Patterns

| # | Concept | Definition | Project Usage |
|---|---------|-----------|--------------|
| 50 | Singleton Pattern | One instance shared globally | LLM client, embedding model, FAISS index |
| 51 | Mock Fallback | Try real → catch error → return mock | Every connector |
| 52 | Session Scoping | Data isolated per user session | upload_handler per session_id |
| 53 | Graceful Degradation | System works with reduced features when APIs fail | Mock data always available |

### Security & Workflow Automation

| # | Concept | Definition | Project Usage |
|---|---------|-----------|--------------|
| 54 | RBAC | Access control based on assigned roles | 3 roles: PMO Admin/Manager/Resource |
| 55 | Approval Workflow | Multi-step process requiring authorization | Onboarding/offboarding need manager approval |
| 56 | Onboarding/Offboarding | Automated employee lifecycle workflows | PMO Admin triggers via chatbot |
| 57 | Resource Tagging | Reassigning resources between projects | PMO Admin moves people between projects |

---

## 🔌 8 Connectors — Mock Fallback Pattern

```python
# Every connector follows this pattern:
def get_data(key):
    real = fetch_from_real_api(key)  # Try real API
    if real: return real
    return MOCK_DATA.get(key, {})    # Fallback to mock
```

| Connector | Real API | Mock Data |
|-----------|----------|-----------|
| sql_connector | pyodbc → SQL Server | MOCK_KPI_DATA dict |
| jira_connector | Jira REST v3 | MOCK_SPRINTS list |
| servicenow_connector | Table API | MOCK_TICKETS dict |
| outlook_connector | MS Graph sendMail | Console log |
| teams_connector | Webhook POST | Console log |
| sharepoint_connector | MS Graph Drive+Lists | MOCK_DOCS list |
| azure_insights | KQL REST API | MOCK_LOGS list |
| kpi_file_connector | pandas read_excel | Formatted KPI data from Excel |

---

## 📦 Python Libraries

| Library | Use | Category |
|---------|-----|----------|
| groq | LLM API client | AI |
| sentence-transformers | Embedding model + Cross-Encoder reranker | AI |
| faiss-cpu | Vector similarity search | AI |
| rank-bm25 | BM25 keyword search | AI |
| langchain / langgraph | Agent orchestration | AI |
| fastapi + uvicorn | REST API server | Web |
| streamlit | Frontend UI | Web |
| pydantic | Data validation | Web |
| pymupdf (fitz) | PDF parsing | Docs |
| python-docx | Word parsing | Docs |
| pandas + openpyxl | Excel/CSV processing | Docs |
| python-pptx | PowerPoint parsing | Docs |
| watchdog | File system monitoring | Utils |
| python-multipart | File upload handling | Utils |

## 🤖 HuggingFace Models

| Model | Type | Dims | Params | Use |
|-------|------|------|--------|-----|
| all-MiniLM-L6-v2 | Sentence Transformer | 384 | 22M | Document + query embeddings + Router Tier 2 |
| cross-encoder/ms-marco-MiniLM-L-6-v2 | Cross-Encoder | — | 22M | Reranking search results |
| LLaMA 3.1 8B Instant | Decoder LLM (via Groq) | — | 8B | All generation + classification |

---

**Built by Papiya Mazumder · Capgemini · KPMG PMO AI Project**
