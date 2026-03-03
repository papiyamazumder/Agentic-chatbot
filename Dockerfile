# ─────────────────────────────────────────────────────────────────
#  KPMG PMO AI Chatbot — Dockerfile
#  Runs BOTH FastAPI backend (port 8000) + Streamlit (port 8501)
#  via a startup shell script.
#
#  Local:  docker build -t kpmg-chatbot . && docker run -p 8000:8000 -p 8501:8501 --env-file .env kpmg-chatbot
#  Azure:  Push to Azure Container Registry → deploy to App Service
# ─────────────────────────────────────────────────────────────────

FROM python:3.11-slim

# System deps for PyMuPDF and sentence-transformers
RUN apt-get update && apt-get install -y \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Working directory
WORKDIR /app

# Copy requirements first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download HuggingFace embedding model into image
# (so container starts fast — no download delay on Azure)
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# Copy full project
COPY . .

# Create data dirs (in case not present)
RUN mkdir -p data/raw_docs data/vector_store

# Expose ports
EXPOSE 8000 8501

# Startup script — runs both backend + frontend
COPY start.sh .
RUN chmod +x start.sh

CMD ["./start.sh"]
