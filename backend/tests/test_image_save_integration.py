import base64
import os
from fastapi.testclient import TestClient
from backend.main import app

# Use a real image from the environment for testing
TEST_IMAGE_PATH = "/home/chris/prj/llm-council/header.png"

def test_image_save_integration():
    client = TestClient(app)
    
    # 1. Read and encode image
    with open(TEST_IMAGE_PATH, "rb") as f:
        image_data = f.read()
        encoded = base64.b64encode(image_data).decode("utf-8")
        image_string = f"data:image/png;base64,{encoded}"

    # 2. Create conversation
    resp = client.post("/api/conversations", json={"title": "Test Image Upload"})
    assert resp.status_code == 200
    created_id = resp.json().get("id")

    # 3. Call save_web_chatbot_message
    payload = {
        "stage1": [{"role": "user", "content": "test prompt"}],
        "stage2": [],
        "stage3": {"response": "test response", "model": "test-model"},
        "metadata": {},
        "user_query": "What is in this image?",
        "title": "Test Upload",
        "image": image_string
    }
    
    resp = client.post(f"/api/conversations/{created_id}/message/web-chatbot", json=payload)
    assert resp.status_code == 200
    
    # 4. Verify image exists in backend/data/images
    images_dir = "/home/chris/prj/llm-council/backend/data/images"
    files = os.listdir(images_dir)
    assert len(files) > 0
    
    # 5. Fetch conversation history to verify metadata
    resp = client.get(f"/api/conversations/{created_id}")
    assert resp.status_code == 200
        
    data = resp.json()
    messages = data.get("messages", [])
    user_msg = next((m for m in messages if m["role"] == "user"), None)
    
    assert user_msg is not None
    assert "metadata" in user_msg
    assert "image_url" in user_msg["metadata"]
    assert user_msg["metadata"]["image_url"].startswith("/api/images/")

    # Clean up
    client.delete(f"/api/conversations/{created_id}")
