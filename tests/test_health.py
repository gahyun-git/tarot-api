from fastapi import status
from fastapi.testclient import TestClient

from app.main import app


def test_health():
    client = TestClient(app)
    resp = client.get("/health/")
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["status"] == "ok"
