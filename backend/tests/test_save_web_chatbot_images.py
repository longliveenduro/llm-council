import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock
import sys
import os
import json
import base64

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.main import app
from backend import storage

client = TestClient(app)

@pytest.fixture
def test_conversation():
    conv_id = "test-images-conv"
    # Ensure cleanup before and after
    storage.delete_conversation(conv_id)
    storage.create_conversation(conv_id)
    yield conv_id
    storage.delete_conversation(conv_id)

def test_save_web_chatbot_mixed_images(test_conversation):
    """Verify that save_web_chatbot_message correctly handles both URLs and Base64 images."""
    conv_id = test_conversation
    
    existing_url = "/api/images/existing-image.jpg"
    b64_data = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAAAAAA6fptVAAAACklEQVR4nGP6DwABBAEbnB1W7AAAAABJRU5ErkJggg=="
    b64_image = f"data:image/png;base64,{b64_data}"
    
    payload = {
        "user_query": "Test query with mixed images",
        "stage1": [],
        "stage2": [],
        "stage3": {"model": "Model A", "response": "Synthesis"},
        "metadata": {},
        "images": [existing_url, b64_image],
        "title": "Test Title"
    }
    
    response = client.post(f"/api/conversations/{conv_id}/message/web-chatbot", json=payload)
    assert response.status_code == 200
    
    # Verify stored message
    conv = storage.get_conversation(conv_id)
    user_msg = next(m for m in conv["messages"] if m["role"] == "user")
    
    urls = user_msg["metadata"]["image_urls"]
    assert len(urls) == 2
    assert urls[0] == existing_url
    assert urls[1].startswith("/api/images/")
    assert urls[1] != existing_url
    assert urls[1].endswith(".png")
    
    # Verify legacy single image_url
    assert user_msg["metadata"]["image_url"] == existing_url

def test_save_web_chatbot_only_url(test_conversation):
    """Verify that save_web_chatbot_message correctly handles only URLs (no re-saving)."""
    conv_id = test_conversation
    
    existing_url = "/api/images/already-there.jpg"
    
    payload = {
        "user_query": "Test query with only URL",
        "stage1": [],
        "stage2": [],
        "stage3": {"model": "Model A", "response": "Synthesis"},
        "metadata": {},
        "images": [existing_url],
        "title": "Test Title"
    }
    
    # We want to make sure NO new files are created if possible, 
    # but at least check that the URL is preserved.
    response = client.post(f"/api/conversations/{conv_id}/message/web-chatbot", json=payload)
    assert response.status_code == 200
    
    conv = storage.get_conversation(conv_id)
    user_msg = next(m for m in conv["messages"] if m["role"] == "user")
    
    urls = user_msg["metadata"]["image_urls"]
    assert len(urls) == 1
    assert urls[0] == existing_url
    assert user_msg["metadata"]["image_url"] == existing_url

if __name__ == "__main__":
    # Allow running directly
    pytest.main([__file__])
