from fastapi.testclient import TestClient
from app.main import app


def test_reading_post_basic():
    client = TestClient(app)
    payload = {
        "question": "올해 커리어 방향?",
        "group_order": ["A", "B", "C"],
        "shuffle_times": 3,
        "seed": 123,
        "allow_reversed": True,
    }
    resp = client.post("/reading/", json=payload)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["count"] == 8
    assert body["question"] == payload["question"]
    assert body["order"] == payload["group_order"]
    positions = [i["position"] for i in body["items"]]
    assert positions == list(range(1, 9))


def test_reading_seed_stability():
    client = TestClient(app)
    payload = {
        "question": "재현성 체크",
        "group_order": ["C", "A", "B"],
        "shuffle_times": 2,
        "seed": 999,
        "allow_reversed": False,
    }
    r1 = client.post("/reading/", json=payload).json()
    r2 = client.post("/reading/", json=payload).json()
    assert r1 == r2
