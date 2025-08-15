from fastapi import status
from fastapi.testclient import TestClient

from app.main import app


def test_reading_validation_group_order_unique():
    client = TestClient(app)
    payload = {
        "question": "q",
        "group_order": ["A", "A", "B"],
        "shuffle_times": 1,
        "seed": None,
        "allow_reversed": True,
    }
    r = client.post("/reading/", json=payload)
    assert r.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    body = r.json()
    assert body["error"]["code"] == "validation_error"


def test_reading_validation_shuffle_times_bounds():
    client = TestClient(app)
    payload = {
        "question": "q",
        "group_order": ["A", "B", "C"],
        "shuffle_times": 0,
        "seed": None,
        "allow_reversed": True,
    }
    r = client.post("/reading/", json=payload)
    assert r.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
