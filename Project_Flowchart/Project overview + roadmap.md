# KPMG PMO AI Chatbot — Project Overview

**Multi-agent RAG chatbot** for KPMG's PMO team with 4 specialized AI agents, hybrid search (FAISS + BM25 + RRF + Cross-Encoder), RBAC, and workflow automation.

**Stack:** Python · FastAPI · LangGraph · Groq (LLaMA 3.1) · FAISS · BM25 · HuggingFace · Streamlit · Docker · Azure

---

## Quick Start

```bash
git clone <repo-url> && cd kpmg-chatbot
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # Add GROQ_API_KEY
python run_ingestion.py
uvicorn backend.main:app --reload --port 8000  # Terminal 1
streamlit run frontend/app.py                   # Terminal 2
```

---

## Architecture

```
User → Streamlit (Login + 3 Roles) → FastAPI /chat → LangGraph 3-Tier Hybrid Router
                                                           ↓
       ┌──────────────┬───────────────┬───────────────┬────────────────┐
  🔍 Retrieval    📊 API         🎫 Helpdesk     ⚙️ Workflow
  FAISS+BM25+RRF  Excel+SQL+Jira ServiceNow     Email/Approve/RAID
  +Cross-Encoder                                  + Onboard/Offboard/Tag
```

## 4 Agents

| Agent | Purpose | Data Sources |
|-------|---------|-------------|
| 🔍 Retrieval | Document Q&A via hybrid RAG | local_storage/ docs, uploaded files |
| 📊 API | KPI metrics & sprint data | Excel trackers, SQL Server, Jira REST |
| 🎫 Helpdesk | IT ticket automation | ServiceNow Table API |
| ⚙️ Workflow | Emails, approvals, RAID, onboarding | Outlook, Teams, SharePoint |

## Roles (RBAC)

| Role | Level | Agents | Vault Docs |
|------|-------|--------|-----------|
| PMO Admin | 3 | All 4 | All 6 |
| Manager | 2 | All 4 | 4/6 (+ Build Guide, Deployment) |
| Resource | 1 | Retrieval + Helpdesk | 4/6 |

All 7 navigation pages are open to every role.

---

## File Structure

```
kpmg-chatbot/
├── backend/main.py            → FastAPI (20+ endpoints, doc conversion)
├── router/graph.py            → LangGraph 3-tier routing (keyword → embedding → LLM)
├── agents/                    → 4 specialized agents
│   ├── retrieval_agent.py     → Hybrid RAG (FAISS + BM25 + RRF + Cross-Encoder)
│   ├── api_agent.py           → KPI data retrieval + formatting
│   ├── helpdesk_agent.py      → ServiceNow ticket automation
│   └── workflow_agent.py      → 8 sub-actions (email, approve, RAID, onboard...)
├── connectors/                → 8 data source adapters (mock fallback pattern)
│   ├── servicenow_connector   → IT tickets
│   ├── outlook_connector      → Email (MS Graph)
│   ├── teams_connector        → Approval webhooks
│   ├── sharepoint_connector   → RAID logs, docs
│   ├── jira_connector         → Sprint data
│   ├── sql_connector          → SQL Server KPIs
│   ├── azure_insights_connector → System logs (KQL)
│   └── kpi_file_connector     → Excel KPI data reader
├── ingestion/                 → Document processing pipeline
│   ├── document_loader.py     → Multi-format parser (PDF, DOCX, XLSX, CSV, PPTX, TXT, MD)
│   ├── chunker.py             → 800-char chunks, 100-char overlap
│   ├── embedder.py            → all-MiniLM-L6-v2 (384-dim)
│   ├── vector_store.py        → FAISS IndexFlatIP + BM25Okapi + RRF + Cross-Encoder
│   ├── upload_handler.py      → Session-scoped doc uploads
│   └── pdf_loader.py          → PyMuPDF-based PDF extraction
├── utils/                     → Shared utilities
│   ├── llm_client.py          → Groq LLaMA 3.1 client (singleton)
│   ├── watchdog_service.py    → Real-time file monitor for local_storage/
│   └── file_generator.py      → Report/file generation helpers
├── frontend/app.py            → Streamlit multi-page UI (1400+ lines)
├── local_storage/             → 9 enterprise documents (ingested on startup)
├── data/                      → Runtime data
│   ├── vector_store/          → FAISS + BM25 + metadata indices
│   ├── KPI Data/              → 12 Excel KPI trackers
│   └── raw_docs/              → Uploaded documents
├── Project_Flowchart/         → 8 HTML docs + 2 MD guides (Encrypted Data Vault)
├── tests/                     → pytest test suite
├── Dockerfile + start.sh      → Single-container deployment
├── requirements.txt           → 15 Python packages
└── run_ingestion.py           → Bootstrap ingestion script
```

---

## Deployment

**Phase 1 (Local):** `uvicorn` + `streamlit run` on localhost
**Phase 2 (Azure):** Docker → ACR → Azure App Service (same code, swap connection strings)

```bash
docker build -t kpmg-chatbot .
docker run -p 8000:8000 -p 8501:8501 -e GROQ_API_KEY=gsk_... kpmg-chatbot
```

---

## Production Roadmap

| Phase | Components | Status |
|-------|-----------|--------|
| P1 — Local | FAISS+BM25, Groq, mock connectors, Streamlit | ✅ Done |
| P2 — Azure | Azure AI Search, OpenAI, Logic Apps, Key Vault | 🔜 Ready |

## Environment Variables

| Category | Keys |
|----------|------|
| LLM | `GROQ_API_KEY`, `GROQ_MODEL` |
| Embedding | `EMBEDDING_MODEL` |
| Azure AD | `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET` |
| SQL | `SQL_SERVER`, `SQL_DATABASE`, `SQL_USER`, `SQL_PASSWORD` |
| Jira | `JIRA_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN` |
| ServiceNow | `SNOW_INSTANCE`, `SNOW_USER`, `SNOW_PASSWORD` |
| Outlook | `OUTLOOK_CLIENT_ID`, `OUTLOOK_CLIENT_SECRET` |

---

**Built by Papiya Mazumder · Capgemini · KPMG PMO AI Project**

