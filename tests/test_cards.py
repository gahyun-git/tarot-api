from fastapi import status
from fastapi.testclient import TestClient

from app.main import app


def test_get_cards():
    client = TestClient(app)
    resp = client.get("/cards/")
    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    assert body["total"] >= 1
    assert len(body["items"]) >= 1


def test_get_card_not_found():
    client = TestClient(app)
    resp = client.get("/cards/9999")
    assert resp.status_code == status.HTTP_404_NOT_FOUND
