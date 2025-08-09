from fastapi.testclient import TestClient
from app.main import app


def test_request_id_header():
    client = TestClient(app)
    r = client.get("/health/")
    assert r.status_code == 200
    assert "x-request-id" in r.headers


def test_health_rate_limit_burst():
    client = TestClient(app)
    ok = 0
    for _ in range(5):
        resp = client.get("/health/")
        if resp.status_code == 200:
            ok += 1
    assert ok >= 1
