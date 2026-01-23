
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock
import sys
import os

# Add project root to path (one level up from backend)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.main import app

client = TestClient(app)

@pytest.mark.asyncio
async def test_run_automation_passes_image():
    """Verify that run-automation endpoint passes image_base64 to council functions."""
    
    # Mock the automation functions in council.py - NOTE: We mock where they are IMPORTED in main.py
    with patch("backend.main.run_chatgpt_automation", new_callable=AsyncMock) as mock_chatgpt, \
         patch("backend.main.run_claude_automation", new_callable=AsyncMock) as mock_claude, \
         patch("backend.main.run_ai_studio_automation", new_callable=AsyncMock) as mock_ai_studio:
        
        mock_chatgpt.return_value = {"response": "Response", "error": False, "error_msgs": None, "error_type": None}
        mock_claude.return_value = {"response": "Response", "error": False, "error_msgs": None, "error_type": None}
        mock_ai_studio.return_value = {"response": "Response", "error": False, "error_msgs": None, "error_type": None}
        
        image_data = "data:image/png;base64,TEST_DATA"
        
        # Test ChatGPT
        response = client.post("/api/web-chatbot/run-automation", json={
            "prompt": "Test Prompt",
            "model": "gpt-4o",
            "provider": "chatgpt",
            "image": image_data
        })
        assert response.status_code == 200
        mock_chatgpt.assert_called_once()
        args, kwargs = mock_chatgpt.call_args
        # Check args/kwargs
        assert args[0] == "Test Prompt"
        assert args[1] == "gpt-4o"
        assert kwargs["images"] == [image_data]

        # Test Claude
        response = client.post("/api/web-chatbot/run-automation", json={
            "prompt": "Test Prompt",
            "model": "claude-3-5-sonnet",
            "provider": "claude",
            "image": image_data
        })
        assert response.status_code == 200
        mock_claude.assert_called_once()
        args, kwargs = mock_claude.call_args
        assert args[0] == "Test Prompt"
        assert args[1] == "claude-3-5-sonnet"
        assert kwargs["images"] == [image_data]

        # Test AI Studio
        response = client.post("/api/web-chatbot/run-automation", json={
            "prompt": "Test Prompt",
            "model": "gemini-1.5-pro",
            "provider": "ai_studio",
            "image": image_data
        })
        assert response.status_code == 200
        mock_ai_studio.assert_called_once()
        args, kwargs = mock_ai_studio.call_args
        assert args[0] == "Test Prompt"
        assert args[1] == "gemini-1.5-pro"
        assert kwargs["images"] == [image_data]

@pytest.mark.asyncio
@patch("backend.main.run_ai_studio_automation", new_callable=AsyncMock)
async def test_run_automation_multiple_images(mock_run):
    """Test that multiple images are correctly passed from the API to the automation function."""
    mock_run.return_value = {"response": "Response with multiple images", "error": False, "error_msgs": None, "error_type": None}
    
    test_images = ["data:image/png;base64,img1...", "data:image/jpeg;base64,img2..."]
    
    response = client.post(
        "/api/web-chatbot/run-automation",
        json={
            "prompt": "Test multi-image",
            "model": "Gemini 2.5 Flash",
            "provider": "ai_studio",
            "images": test_images
        }
    )
    
    assert response.status_code == 200
    assert response.json() == {"response": "Response with multiple images", "error": False, "error_msgs": None, "error_type": None}
    
    # Verify that run_ai_studio_automation was called with the images list
    mock_run.assert_called_once()
    args, kwargs = mock_run.call_args
    assert kwargs["images"] == test_images

@pytest.mark.asyncio
@patch("backend.main.run_chatgpt_automation", new_callable=AsyncMock)
async def test_run_automation_thinking_failure(mock_run):
    """Test that thinking mode activation failure returns the correct error JSON."""
    mock_run.return_value = {
        "response": None,
        "error": True,
        "error_msgs": "Thinking mode requested but could not be activated.",
        "error_type": "thinking_not_activated"
    }
    
    response = client.post(
        "/api/web-chatbot/run-automation",
        json={
            "prompt": "Test thinking failure",
            "model": "gpt-4o-thinking",
            "provider": "chatgpt"
        }
    )
    
    assert response.status_code == 200
    assert response.json() == {
        "response": None,
        "error": True,
        "error_msgs": "Thinking mode requested but could not be activated.",
        "error_type": "thinking_not_activated"
    }
    
    mock_run.assert_called_once()
