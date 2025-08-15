from fastapi import status
from fastapi.testclient import TestClient

from app.main import app

# Constants
EXPECTED_CARD_COUNT = 8


def test_reading_create():
    client = TestClient(app)
    payload = {
        "question": "test question",
        "group_order": ["A", "B", "C"],
        "shuffle_times": 1,
        "seed": None,
        "allow_reversed": True,
    }
    resp = client.post("/reading/", json=payload)
    assert resp.status_code == status.HTTP_200_OK, resp.text
    body = resp.json()
    assert body["count"] == EXPECTED_CARD_COUNT
    assert body["question"] == payload["question"]
    assert body["order"] == payload["group_order"]
    assert len(body["items"]) == EXPECTED_CARD_COUNT
    for item in body["items"]:
        assert "position" in item
        assert "is_reversed" in item
        assert "card" in item
        assert "id" in item["card"]
        assert "name" in item["card"]


def test_reading_get():
    client = TestClient(app)
    # First create a reading
    payload = {
        "question": "test question",
        "group_order": ["A", "B", "C"],
        "shuffle_times": 1,
        "seed": None,
        "allow_reversed": True,
    }
    resp = client.post("/reading/", json=payload)
    assert resp.status_code == status.HTTP_200_OK
    reading_id = resp.json()["id"]
    # Then get it
    resp = client.get(f"/reading/{reading_id}")
    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    assert body["id"] == reading_id
    assert body["question"] == payload["question"]


def test_reading_get_not_found():
    client = TestClient(app)
    resp = client.get("/reading/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == status.HTTP_404_NOT_FOUND
