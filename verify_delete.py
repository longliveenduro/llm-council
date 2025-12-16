import asyncio
from fastapi.testclient import TestClient
from backend.main import app
from backend import storage
import os

def test_delete_flow():
    client = TestClient(app)
    
    # 1. Create a conversation
    print("\n--- Creating Conversation ---")
    resp = client.post("/api/conversations", json={})
    assert resp.status_code == 200
    conv_id = resp.json()["id"]
    print(f"Created conversation: {conv_id}")
    
    # Verify file exists
    path = storage.get_conversation_path(conv_id)
    assert os.path.exists(path)
    print("File exists.")
    
    # 2. Delete it
    print("\n--- Deleting Conversation ---")
    resp = client.delete(f"/api/conversations/{conv_id}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"
    print("Delete request successful.")
    
    # Verify file is gone
    assert not os.path.exists(path)
    print("File deleted from disk.")
    
    # 3. Try deleting again (should fail)
    print("\n--- Testing 404 on Repeat Delete ---")
    resp = client.delete(f"/api/conversations/{conv_id}")
    assert resp.status_code == 404
    print("Got 404 as expected for missing conversation.")

    print("\n✓ Delete Endpoint verification passed!")

if __name__ == "__main__":
    test_delete_flow()
