# KPMG PMO AI Chatbot — Project Overview

**Multi-agent RAG chatbot** for KPMG's PMO team with 4 specialized AI agents, RBAC, and workflow automation.

**Stack:** Python · FastAPI · LangGraph · Groq (LLaMA 3.1) · FAISS · HuggingFace · Streamlit · Docker · Azure

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
User → Streamlit (Login + RBAC) → FastAPI /chat → LangGraph 3-Tier Router
                                                        ↓
       ┌──────────────┬───────────────┬───────────────┬────────────────┐
  🔍 Retrieval    📊 API         🎫 Helpdesk     ⚙️ Workflow
  FAISS + RAG    SQL + Jira     ServiceNow     Email/Approve/RAID
                                                + Onboard/Offboard/Tag
```

## 4 Agents

| Agent | Purpose | Data Sources |
|-------|---------|-------------|
| 🔍 Retrieval | Document Q&A via RAG | SharePoint, uploaded files |
| 📊 API | KPI metrics & sprint data | SQL Server, Jira REST |
| 🎫 Helpdesk | IT ticket automation | ServiceNow Table API |
| ⚙️ Workflow | Emails, approvals, RAID, onboarding | Outlook, Teams, SharePoint |

## Roles (RBAC)

| Role | Level | Agents | Extra |
|------|-------|--------|-------|
| PMO Admin | 3 | All 4 | User Management + Onboarding/Offboarding/Tagging |
| Manager | 2 | All 4 | Receives approval notifications |
| Resource | 1 | Retrieval + Helpdesk | Basic access |

---

## File Structure

```
kpmg-chatbot/
├── backend/main.py           → FastAPI endpoints
├── router/graph.py            → LangGraph 3-tier routing
├── agents/                    → 4 specialized agents
├── connectors/                → 7 data source adapters
├── ingestion/                 → Document processing pipeline
├── frontend/app.py            → Streamlit multi-page UI
├── Project_Flowchart/         → 8 HTML docs + 2 MD guides
├── Dockerfile + start.sh      → Containerization
└── .github/workflows/         → CI/CD to Azure
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
| P1 — Local | FAISS, Groq, mock connectors, Streamlit | ✅ Done |
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

