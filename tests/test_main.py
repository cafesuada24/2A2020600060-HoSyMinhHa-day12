import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert "AI Agent" in response.json()["app"]

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] in ["ok", "degraded"]
