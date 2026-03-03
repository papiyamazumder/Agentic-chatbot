from fastapi.testclient import TestClient
import pytest

def test_health_check(client: TestClient):
    """Test the /health endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data

def test_root_endpoint(client: TestClient):
    """Test the root / endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    assert "KPMG PMO AI Chatbot API" in response.json()["message"]

def test_chat_endpoint_invalid_payload(client: TestClient):
    """Test /chat with missing query."""
    response = client.post("/chat", json={"session_id": "test"})
    assert response.status_code == 422  # Pydantic validation error

def test_upload_endpoint_no_file(client: TestClient):
    """Test /upload without a file."""
    response = client.post("/upload", data={"session_id": "test"})
    assert response.status_code == 422
