import pytest
import urllib.request
import urllib.parse
import json
import base64
import os
from pathlib import Path
import mimetypes

BASE_URL = "http://localhost:8001"
TEST_TEXT_FILE = Path("backend/tests/temp_test.txt")
TEST_LARGE_FILE = Path("backend/tests/temp_test_large.jpg")

import pytest

# Ensure test files exist
@pytest.fixture(scope="module", autouse=True)
def setup_test_files():
    print("Setting up temporary test files...")
    # 1. Text file
    with open(TEST_TEXT_FILE, "w") as f:
        f.write("This is not an image.")
        
    # 2. Large file (approx 6MB)
    with open(TEST_LARGE_FILE, "wb") as f:
        f.write(os.urandom(6 * 1024 * 1024))
    
    yield
    
    print("\nCleaning up temporary test files...")
    if TEST_TEXT_FILE.exists(): 
        os.remove(TEST_TEXT_FILE)
        print(f"Removed {TEST_TEXT_FILE}")
    if TEST_LARGE_FILE.exists(): 
        os.remove(TEST_LARGE_FILE)
        print(f"Removed {TEST_LARGE_FILE}")

def upload_file(url, file_path, content_type=None):
    boundary = '---BOUNDARY' + os.urandom(16).hex()
    data = []
    
    filename = os.path.basename(file_path)
    mime_type = content_type or mimetypes.guess_type(file_path)[0] or 'application/octet-stream'
    
    data.append(f'--{boundary}'.encode())
    data.append(f'Content-Disposition: form-data; name="file"; filename="{filename}"'.encode())
    data.append(f'Content-Type: {mime_type}'.encode())
    data.append(b'')
    with open(file_path, 'rb') as f:
        data.append(f.read())
    data.append(b'')
    data.append(f'--{boundary}--'.encode())
    data.append(b'')
    
    body = b'\r\n'.join(data)
    req = urllib.request.Request(url, data=body, method='POST')
    req.add_header('Content-Type', f'multipart/form-data; boundary={boundary}')
    
    try:
        with urllib.request.urlopen(req) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()
    except Exception as e:
        return 500, str(e)

def post_json(url, payload):
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, method='POST')
    req.add_header('Content-Type', 'application/json')
    
    try:
        with urllib.request.urlopen(req) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()
    except Exception as e:
        return 500, str(e)

def test_invalid_file_type():
    print("\n--- Testing Invalid File Type (.txt) ---")
    url = f"{BASE_URL}/api/upload-image"
    status, result = upload_file(url, TEST_TEXT_FILE)
    print(f"Status: {status}")
    print(f"Result: {result}")
    
    if status == 200:
        print("NOTE: Backend accepted text file. (This confirms current behavior)")
    else:
        print("SUCCESS: Backend rejected text file.")

def test_large_file_upload():
    print("\n--- Testing Large File Upload (6MB) ---")
    url = f"{BASE_URL}/api/upload-image"
    status, result = upload_file(url, TEST_LARGE_FILE)
    print(f"Status: {status}")
    if status == 200 and 'url' in result:
        print(f"SUCCESS: Uploaded large file. URL: {result['url']}")
    else:
        print(f"FAILED: Large file upload failed. {result}")

def test_broken_image_path_automation():
    print("\n--- Testing Broken Image Path in Automation ---")
    url = f"{BASE_URL}/api/web-chatbot/run-automation"
    
    # Passing a path that shouldn't exist
    payload = {
        "prompt": "Test broken path",
        "model": "Gemini 2.5 Flash",
        "provider": "ai_studio",
        "images": ["/api/images/non_existent_uuid.jpg"]
    }
    
    status, result = post_json(url, payload)
    print(f"Status: {status}")
    
    if status == 200:
        print("SUCCESS: Automation ran (backend gracefully handled missing image).")
    else:
        print(f"FAILED: Automation crashed on broken image. {result}")

def test_legacy_base64_automation():
    print("\n--- Testing Legacy Base64 Automation ---")
    url = f"{BASE_URL}/api/web-chatbot/run-automation"
    
    # Tiny 1x1 pixel base64
    b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAAAAAA6fptVAAAACklEQVR4nGP6DwABBAEbnB1W7AAAAABJRU5ErkJggg=="
    
    payload = {
        "prompt": "Test base64",
        "model": "Gemini 2.5 Flash",
        "provider": "ai_studio",
        "image": b64 # Legacy field
    }
    
    status, result = post_json(url, payload)
    print(f"Status: {status}")
    
    if status == 200:
         print("SUCCESS: Automation ran with legacy base64.")
    else:
         print(f"FAILED: Legacy base64 failed. {result}")

if __name__ == "__main__":
    try:
        # In manual mode, we need to run setup manually if not using pytest
        # But we replaced setup_files with a fixture. 
        # Ideally, this script should just be run with pytest.
        pass
    except Exception as e:
        print(f"\nAn error occurred during testing: {e}")
