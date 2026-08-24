import os
import sys
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mktemp(suffix='.db')}"
os.environ["UPLOAD_DIR"] = tempfile.mkdtemp()
os.environ["AI_MODE"] = "demo"
os.environ["JWT_SECRET"] = "test_secret"

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import app  # noqa: E402


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def auth_headers(client):
    client.post("/api/auth/register", json={"name": "Test User", "email": "test@example.com", "password": "password123"})
    res = client.post("/api/auth/login", json={"email": "test@example.com", "password": "password123"})
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
