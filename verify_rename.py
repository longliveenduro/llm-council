import asyncio
from fastapi.testclient import TestClient
from backend.main import app
from backend import storage

def test_rename_flow():
    client = TestClient(app)
    
    # 1. Create conversation
    print("\n--- Creating Conversation ---")
    resp = client.post("/api/conversations", json={})
    assert resp.status_code == 200
    conv_id = resp.json()["id"]
    print(f"Created: {conv_id}")
    
    # 2. Rename it
    print("\n--- Renaming Conversation ---")
    new_title = "My Super Cool Council"
    resp = client.patch(f"/api/conversations/{conv_id}/title", json={"title": new_title})
    assert resp.status_code == 200
    assert resp.json()["title"] == new_title
    print("Rename successful.")
    
    # 3. Verify in List
    print("\n--- Verifying in List ---")
    resp = client.get("/api/conversations")
    convs = resp.json()
    target = next(c for c in convs if c["id"] == conv_id)
    assert target["title"] == new_title
    print(f"Title verified in list: {target['title']}")
    
    # 4. Verify persistence
    print("\n--- Verifying Persistence ---")
    stored = storage.get_conversation(conv_id)
    assert stored["title"] == new_title
    print("Persistence verified.")
    
    print("\n✓ Rename Endpoint verification passed!")

if __name__ == "__main__":
    test_rename_flow()
