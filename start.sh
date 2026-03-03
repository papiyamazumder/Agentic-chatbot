#!/bin/bash
# ─────────────────────────────────────────────────────
#  KPMG PMO Chatbot — Container Startup Script
#  Starts FastAPI backend (port 8000) in background
#  then Streamlit frontend (port 8501) in foreground
# ─────────────────────────────────────────────────────

echo "Starting KPMG PMO AI Chatbot..."

# Start FastAPI backend in background
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 2 &
FASTAPI_PID=$!
echo "FastAPI started (PID: $FASTAPI_PID) on port 8000"

# Wait for FastAPI to be ready
sleep 3

# Start Streamlit in foreground (keeps container alive)
streamlit run frontend/app.py \
    --server.port 8501 \
    --server.address 0.0.0.0 \
    --server.headless true \
    --browser.gatherUsageStats false
