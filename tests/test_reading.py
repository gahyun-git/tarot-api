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
    # id는 매 요청마다 달라질 수 있으므로 제외하고 비교
    r1_no_id = {k: v for k, v in r1.items() if k != "id"}
    r2_no_id = {k: v for k, v in r2.items() if k != "id"}
    assert r1_no_id == r2_no_id


def test_reading_create_and_get():
    client = TestClient(app)
    payload = {
        "question": "저장 후 조회",
        "group_order": ["A", "B", "C"],
        "shuffle_times": 1,
        "seed": 42,
        "allow_reversed": True,
    }
    created = client.post("/reading/", json=payload).json()
    assert created.get("id")
    rid = created["id"]
    got = client.get(f"/reading/{rid}").json()
    assert got == created


def test_reading_get_not_found():
    client = TestClient(app)
    resp = client.get("/reading/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404
