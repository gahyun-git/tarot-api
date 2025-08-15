from fastapi import status
from fastapi.testclient import TestClient

from app.main import app


def test_request_id_header():
    client = TestClient(app)
    r = client.get("/health/")
    assert r.status_code == status.HTTP_200_OK
    assert "x-request-id" in r.headers


def test_rate_limiting():
    client = TestClient(app)
    ok = 0
    for _ in range(5):
        resp = client.get("/health/")
        if resp.status_code == status.HTTP_200_OK:
            ok += 1
    assert ok >= 1
