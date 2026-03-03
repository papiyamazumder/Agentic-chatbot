# KPMG PMO AI Chatbot

**Multi-agent RAG chatbot** built for the KPMG PMO team.  
Enables project managers to query documents, retrieve KPIs, and trigger workflow actions — all via natural language.

**Stack:** Python · FastAPI · LangGraph · Groq (llama3) · HuggingFace Embeddings · FAISS · Streamlit · Docker · Azure App Service

---

## Architecture

```
User Query (Streamlit UI)
        ↓
FastAPI /chat endpoint  (backend/main.py)
        ↓
LangGraph Router  (router/graph.py)
  ├── 🔍 Retrieval Agent  → FAISS search → Groq LLM → Document answer
  ├── 📊 API Agent        → REST API / mock KPI → Groq formatting
  └── ⚙️ Workflow Agent   → Ticket / Email / Approval / RAID log
```

---

## Project Structure

```
kpmg-chatbot/
├── .env                    ← API keys (copy from .env.example)
├── requirements.txt
├── README.md
├── Dockerfile
├── start.sh
├── run_ingestion.py        ← Run ONCE to index documents
│
├── ingestion/
│   ├── pdf_loader.py       ← Load PDF, Word, Excel, CSV
│   ├── chunker.py          ← Split into 500-char chunks
│   ├── embedder.py         ← HuggingFace all-MiniLM-L6-v2
│   └── vector_store.py     ← FAISS save/load/search
│
├── agents/
│   ├── retrieval_agent.py  ← RAG: FAISS + Groq answer
│   ├── api_agent.py        ← KPI: REST API + Groq format
│   └── workflow_agent.py   ← Actions: tickets/email/logs
│
├── router/
│   └── graph.py            ← LangGraph StateGraph routing
│
├── backend/
│   └── main.py             ← FastAPI: /chat /health /tickets
│
├── frontend/
│   └── app.py              ← Streamlit chat UI
│
└── data/
    ├── raw_docs/           ← Drop PDFs, SOPs, reports here
    └── vector_store/       ← FAISS index auto-saved here
```

---

## Quick Start — Local

### 1. Clone and setup

```bash
git clone https://github.com/yourusername/kpmg-chatbot.git
cd kpmg-chatbot
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and add your GROQ_API_KEY
# Get free key at: https://console.groq.com
```

### 3. Add documents

```bash
# Drop any PDFs, Word files, Excel sheets into:
data/raw_docs/
# Example: SOPs, meeting notes, project reports
```

### 4. Run ingestion (index your documents)

```bash
python run_ingestion.py
# Downloads HuggingFace model on first run (~90MB, cached after)
# Creates FAISS index in data/vector_store/
```

### 5. Start backend

```bash
# Terminal 1
uvicorn backend.main:app --reload --port 8000
# Swagger UI: http://localhost:8000/docs
```

### 6. Start frontend

```bash
# Terminal 2
streamlit run frontend/app.py
# Opens: http://localhost:8501
```

---

## Example Queries

| Query | Agent Handled By |
|---|---|
| "What are the risks in the Q3 delivery report?" | 🔍 Retrieval Agent |
| "What is the current delivery risk score for Project Alpha?" | 📊 API Agent |
| "Raise a P1 ticket — reporting dashboard is down" | ⚙️ Workflow Agent |
| "Notify the delivery team about the 3pm meeting" | ⚙️ Workflow Agent |
| "What does the SOP say about vendor onboarding?" | 🔍 Retrieval Agent |
| "Show me this month's resource utilisation rate" | 📊 API Agent |

---

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/chat` | POST | Main chat — routes to LangGraph |
| `/health` | GET | Backend health + index status |
| `/tickets` | GET | All IT tickets (admin) |
| `/logs` | GET | All RAID log entries (admin) |
| `/approvals` | GET | All approval requests (admin) |
| `/docs` | GET | Swagger UI |

---

## Docker (local)

```bash
# Build
docker build -t kpmg-chatbot .

# Run
docker run -p 8000:8000 -p 8501:8501 --env-file .env kpmg-chatbot

# Frontend: http://localhost:8501
# Backend:  http://localhost:8000/docs
```

---

## Deploy to Azure App Service

### Option A — Azure CLI (fastest)

```bash
# Login
az login

# Create resource group
az group create --name kpmg-chatbot-rg --location eastus

# Create App Service plan
az appservice plan create \
  --name kpmg-chatbot-plan \
  --resource-group kpmg-chatbot-rg \
  --sku B2 --is-linux

# Deploy directly from source [NOPE]
az webapp up \
  --name kpmg-chatbot-app \
  --resource-group kpmg-chatbot-rg \
  --plan kpmg-chatbot-plan \
  --runtime "PYTHON:3.11"

# Set environment variables
az webapp config appsettings set \
  --name kpmg-chatbot-app \
  --resource-group kpmg-chatbot-rg \
  --settings GROQ_API_KEY="your-key" EMBEDDING_MODEL="all-MiniLM-L6-v2"
```

### Option B — Docker + Azure Container Registry. [YES]

```bash
# Build and push to ACR
az acr create --name kpmgchatbotacr --resource-group kpmg-chatbot-rg --sku Basic
az acr login --name kpmgchatbotacr
docker build -t kpmgchatbotacr.azurecr.io/kpmg-chatbot:v1 .
docker push kpmgchatbotacr.azurecr.io/kpmg-chatbot:v1

# Deploy to App Service from container
az webapp create \
  --name kpmg-chatbot-app \
  --resource-group kpmg-chatbot-rg \
  --plan kpmg-chatbot-plan \
  --deployment-container-image-name kpmgchatbotacr.azurecr.io/kpmg-chatbot:v1
```

### Option C — GitHub Actions CI/CD. [NOPE]

```yaml
# .github/workflows/deploy.yml
name: Deploy to Azure
on:
  push:
    branches: [main]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: azure/webapps-deploy@v2
        with:
          app-name: kpmg-chatbot-app
          publish-profile: ${{ secrets.AZURE_PUBLISH_PROFILE }}
```

---

## Phase 2 — Azure Scaling (when ready)

| Phase 1 (Local) | Phase 2 (Azure) |
|---|---|
| FAISS local index | Azure AI Search |
| Local file folder | Azure Blob Storage |
| python-dotenv .env | Azure Key Vault |
| smtplib email | Azure Logic Apps O365 |
| Manual ingestion | Azure Functions timer trigger |

Zero agent code changes needed — only connection strings change.

---

## Tech Stack

| Component | Technology |
|---|---|
| LLM | Groq API — llama3-8b-8192 (free) |
| Embeddings | HuggingFace all-MiniLM-L6-v2 (local, free) |
| Vector Store | FAISS (local) |
| Agent Orchestration | LangGraph StateGraph |
| Backend API | FastAPI + uvicorn |
| Frontend | Streamlit |
| Document Parsing | PyMuPDF, python-docx, pandas |
| Deployment | Docker + Azure App Service |

---

**Built by Papiya Mazumder · Capgemini · KPMG PMO AI Project**
