from fastapi.testclient import TestClient
from backend.main import app
from backend import storage

def test_rename_flow():
    client = TestClient(app)
    
    # 1. Create conversation
    resp = client.post("/api/conversations", json={})
    assert resp.status_code == 200
    conv_id = resp.json()["id"]
    
    # 2. Rename it
    new_title = "My Super Cool Council"
    resp = client.patch(f"/api/conversations/{conv_id}/title", json={"title": new_title})
    assert resp.status_code == 200
    assert resp.json()["title"] == new_title
    
    # 3. Verify in List
    resp = client.get("/api/conversations")
    convs = resp.json()
    target = next(c for c in convs if c["id"] == conv_id)
    assert target["title"] == new_title
    
    # 4. Verify persistence
    stored = storage.get_conversation(conv_id)
    assert stored["title"] == new_title
