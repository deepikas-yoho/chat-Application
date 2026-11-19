# Basic smoke tests. Set TEST_DATABASE_URL to a disposable PostgreSQL database
# and configure .env before running pytest.
from fastapi.testclient import TestClient
from app.main import app
from app.config import get_settings

client = TestClient(app)
HEADERS = {"X-API-Key": get_settings().api_key}


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_api_key_required():
    response = client.post("/sessions")
    assert response.status_code == 401


def test_create_and_read_session():
    created = client.post("/sessions", headers=HEADERS)
    assert created.status_code == 200
    session_id = created.json()["id"]

    messages = client.get(f"/sessions/{session_id}/messages", headers=HEADERS)
    assert messages.status_code == 200
    assert messages.json() == []

    deleted = client.delete(f"/sessions/{session_id}", headers=HEADERS)
    assert deleted.status_code == 200
