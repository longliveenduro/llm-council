import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import sys
import os

# Add the project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from browser_automation import ai_studio_automation
from browser_automation import chatgpt_automation
from browser_automation import claude_automation

@pytest.mark.asyncio
async def test_ai_studio_cli_args():
    with patch("browser_automation.ai_studio_automation.get_browser_context", return_value=(AsyncMock(), AsyncMock())), \
         patch("browser_automation.ai_studio_automation.send_prompt", new_callable=AsyncMock) as mock_send_prompt, \
         patch("sys.argv", ["ai_studio_automation.py", "test prompt", "--image", "img1.png", "--image", "img2.png"]):
        
        await ai_studio_automation.main()
        
        # Verify send_prompt was called with multiple image paths
        mock_send_prompt.assert_called_once()
        args, kwargs = mock_send_prompt.call_args
        assert kwargs["image_paths"] == ["img1.png", "img2.png"]

@pytest.mark.asyncio
async def test_chatgpt_cli_args():
    mock_context = AsyncMock()
    mock_page = AsyncMock()
    mock_page.url = "https://chatgpt.com/"
    
    with patch("browser_automation.chatgpt_automation.get_browser_context", return_value=(mock_context, mock_page)), \
         patch("browser_automation.chatgpt_automation.select_model", return_value=True), \
         patch("browser_automation.chatgpt_automation.send_prompt", new_callable=AsyncMock) as mock_send_prompt, \
         patch("sys.argv", ["chatgpt_automation.py", "test prompt", "--image", "img1.png", "--image", "img2.png"]):
        
        await chatgpt_automation.main()
        
        # Verify send_prompt was called with multiple image paths
        mock_send_prompt.assert_called_once()
        args, kwargs = mock_send_prompt.call_args
        assert kwargs["image_paths"] == ["img1.png", "img2.png"]

@pytest.mark.asyncio
async def test_claude_cli_args():
    mock_context = AsyncMock()
    mock_page = AsyncMock()
    mock_page.url = "https://claude.ai/"
    
    with patch("browser_automation.claude_automation.get_browser_context", return_value=(mock_context, mock_page)), \
         patch("browser_automation.claude_automation.send_prompt", new_callable=AsyncMock) as mock_send_prompt, \
         patch("sys.argv", ["claude_automation.py", "test prompt", "--image", "img1.png", "--image", "img2.png"]):
        
        await claude_automation.main()
        
        # Verify send_prompt was called with multiple image paths
        mock_send_prompt.assert_called_once()
        args, kwargs = mock_send_prompt.call_args
        # Claude uses image_paths now too
        assert kwargs["image_paths"] == ["img1.png", "img2.png"]
