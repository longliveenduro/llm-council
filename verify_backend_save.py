import requests
import base64
import uuid
import os
import sys

# Constants
BASE_URL = "http://localhost:8000"
TEST_IMAGE_PATH = "/home/chris/.gemini/antigravity/brain/974b107e-5c0e-4f04-8261-546455d74792/test_bone.png"

def test_image_save():
    # 1. Read and encode image
    with open(TEST_IMAGE_PATH, "rb") as f:
        image_data = f.read()
        encoded = base64.b64encode(image_data).decode("utf-8")
        # Add header to mimic frontend
        image_string = f"data:image/png;base64,{encoded}"

    # 2. Create requests
    conversation_id = str(uuid.uuid4())
    
    # Create conversation first (if needed, but storage.py auto-creates usually? 
    # Let's check storage.py: add_user_message checks if conv exists? 
    # Actually main.py loads conversation. If it doesn't exist, it might error.
    # Let's try creating it first.)
    
    # Actually, let's just use a random ID and see if storage handles it or if I need to POST /api/conversations first.
    # main.py: @app.post("/api/conversations") -> create_conversation
    
    print(f"Creating conversation {conversation_id}...")
    resp = requests.post(f"{BASE_URL}/api/conversations", json={"title": "Test Image Upload"})
    if resp.status_code != 200:
        print(f"Failed to create conversation: {resp.text}")
        sys.exit(1)
        
    created_id = resp.json().get("id")
    print(f"Conversation created: {created_id}")

    # 3. Call save_web_chatbot_message
    payload = {
        "stage1": [{"role": "user", "content": "test prompt"}],
        "stage2": [],
        "stage3": {"response": "test response", "model": "test-model"},
        "metadata": {},
        "user_query": "What animal is this bone from?",
        "title": "Test Upload",
        "image": image_string
    }
    
    print("Sending message with image...")
    resp = requests.post(f"{BASE_URL}/api/conversations/{created_id}/message/web-chatbot", json=payload)
    
    if resp.status_code != 200:
        print(f"Failed to save message: {resp.text}")
        sys.exit(1)
        
    print("Message saved successfully.")
    
    # 4. Verify image exists in backend/data/images
    # We don't know the exact filename without parsing metadata, but we can list the dir
    images_dir = "/home/chris/prj/llm-council/backend/data/images"
    files = os.listdir(images_dir)
    if not files:
        print(f"Error: No files found in {images_dir}")
        sys.exit(1)
        
    print(f"Found {len(files)} images in storage. Latest might be ours.")
    # In a real test we'd check timestamps, but good enough for now.
    
    # 5. Fetch conversation history to verify metadata
    resp = requests.get(f"{BASE_URL}/api/conversations/{created_id}")
    if resp.status_code != 200:
        print(f"Failed to fetch conversation: {resp.text}")
        sys.exit(1)
        
    data = resp.json()
    messages = data.get("messages", [])
    user_msg = next((m for m in messages if m["role"] == "user"), None)
    
    if user_msg and "metadata" in user_msg and "image_url" in user_msg["metadata"]:
        print(f"SUCCESS: Image URL found in metadata: {user_msg['metadata']['image_url']}")
    else:
        print("FAILURE: Image URL not found in message metadata.")
        print(f"Messages: {messages}")
        sys.exit(1)

if __name__ == "__main__":
    try:
        test_image_save()
    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)
