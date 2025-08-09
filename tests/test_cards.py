from fastapi.testclient import TestClient
from app.main import app

def test_cards_list():
    client = TestClient(app)
    resp = client.get("/cards/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    assert isinstance(body["items"], list)
