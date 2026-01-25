from fastapi.testclient import TestClient
from backend.main import app
from backend import storage
import os

def test_delete_flow():
    client = TestClient(app)
    
    # 1. Create a conversation
    resp = client.post("/api/conversations", json={})
    assert resp.status_code == 200
    conv_id = resp.json()["id"]
    
    # Verify file exists
    path = storage.get_conversation_path(conv_id)
    assert os.path.exists(path)
    
    # 2. Delete it
    resp = client.delete(f"/api/conversations/{conv_id}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"
    
    # Verify file is gone
    assert not os.path.exists(path)
    
    # 3. Try deleting again (should fail)
    resp = client.delete(f"/api/conversations/{conv_id}")
    assert resp.status_code == 404
