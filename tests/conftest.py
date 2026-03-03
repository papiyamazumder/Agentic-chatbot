import pytest
import os
import sys
from fastapi.testclient import TestClient

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.main import app

@pytest.fixture
def client():
    """FastAPI test client fixture."""
    with TestClient(app) as c:
        yield c

@pytest.fixture(autouse=True)
def mock_env(monitoring_utils=None):
    """Ensure sensitive environment variables are mocked for tests."""
    os.environ["GROQ_API_KEY"] = "gsk_test_key"
    os.environ["BACKEND_URL"] = "http://testserver"
