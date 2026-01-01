from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_read_main():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "LLM Council API"}

def test_list_conversations():
    response = client.get("/api/conversations")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
