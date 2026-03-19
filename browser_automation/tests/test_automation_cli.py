import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import sys
import os
import tempfile

# Add the project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from browser_automation import ai_studio_automation
from browser_automation import chatgpt_automation
from browser_automation import claude_automation

@pytest.mark.asyncio
async def test_ai_studio_cli_args():
    with patch("browser_automation.ai_studio_automation.get_browser_context", return_value=(AsyncMock(), AsyncMock())), \
         patch("browser_automation.ai_studio_automation.send_prompt", new_callable=AsyncMock, return_value="mock response") as mock_send_prompt, \
         patch("sys.argv", ["ai_studio_automation.py", "test prompt", "--image", "img1.png", "--image", "img2.png"]):
        
        await ai_studio_automation.main()
        
        # Verify send_prompt was called with multiple image paths
        mock_send_prompt.assert_called_once()
        args, kwargs = mock_send_prompt.call_args
        assert kwargs["image_paths"] == ["img1.png", "img2.png"]

@pytest.mark.asyncio
async def test_ai_studio_prompt_file():
    """Test that --prompt-file reads prompt from file and deletes it."""
    # Create temp file with a large prompt
    prompt_text = "This is a very large prompt " * 1000
    tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False)
    tmp.write(prompt_text)
    tmp.close()
    
    with patch("browser_automation.ai_studio_automation.get_browser_context", return_value=(AsyncMock(), AsyncMock())), \
         patch("browser_automation.ai_studio_automation.send_prompt", new_callable=AsyncMock, return_value="mock response") as mock_send_prompt, \
         patch("sys.argv", ["ai_studio_automation.py", "--prompt-file", tmp.name]):
        
        await ai_studio_automation.main()
        
        # Verify send_prompt was called with the prompt from the file
        mock_send_prompt.assert_called_once()
        args, kwargs = mock_send_prompt.call_args
        assert args[1] == prompt_text  # prompt is 2nd positional arg to send_prompt
        
        # Verify temp file was cleaned up
        assert not os.path.exists(tmp.name)

@pytest.mark.asyncio
async def test_chatgpt_cli_args():
    mock_context = AsyncMock()
    mock_page = AsyncMock()
    mock_page.url = "https://chatgpt.com/"
    
    with patch("browser_automation.chatgpt_automation.get_browser_context", return_value=(mock_context, mock_page)), \
         patch("browser_automation.chatgpt_automation.select_model", return_value=True), \
         patch("browser_automation.chatgpt_automation.send_prompt", new_callable=AsyncMock, return_value="mock response") as mock_send_prompt, \
         patch("sys.argv", ["chatgpt_automation.py", "test prompt", "--image", "img1.png", "--image", "img2.png"]):
        
        await chatgpt_automation.main()
        
        # Verify send_prompt was called with multiple image paths
        mock_send_prompt.assert_called_once()
        args, kwargs = mock_send_prompt.call_args
        assert kwargs["image_paths"] == ["img1.png", "img2.png"]

@pytest.mark.asyncio
async def test_chatgpt_prompt_file():
    """Test that --prompt-file reads prompt from file for ChatGPT."""
    prompt_text = "Large ChatGPT prompt " * 500
    tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False)
    tmp.write(prompt_text)
    tmp.close()
    
    mock_context = AsyncMock()
    mock_page = AsyncMock()
    mock_page.url = "https://chatgpt.com/"
    
    with patch("browser_automation.chatgpt_automation.get_browser_context", return_value=(mock_context, mock_page)), \
         patch("browser_automation.chatgpt_automation.select_model", return_value=True), \
         patch("browser_automation.chatgpt_automation.send_prompt", new_callable=AsyncMock, return_value="mock response") as mock_send_prompt, \
         patch("sys.argv", ["chatgpt_automation.py", "--prompt-file", tmp.name]):
        
        await chatgpt_automation.main()
        
        mock_send_prompt.assert_called_once()
        args, kwargs = mock_send_prompt.call_args
        assert args[1] == prompt_text
        assert not os.path.exists(tmp.name)

@pytest.mark.asyncio
async def test_claude_cli_args():
    mock_context = AsyncMock()
    mock_page = AsyncMock()
    mock_page.url = "https://claude.ai/"
    
    with patch("browser_automation.claude_automation.get_browser_context", return_value=(mock_context, mock_page)), \
         patch("browser_automation.claude_automation.send_prompt", new_callable=AsyncMock, return_value="mock response") as mock_send_prompt, \
         patch("sys.argv", ["claude_automation.py", "test prompt", "--image", "img1.png", "--image", "img2.png"]):
        
        await claude_automation.main()
        
        # Verify send_prompt was called with multiple image paths
        mock_send_prompt.assert_called_once()
        args, kwargs = mock_send_prompt.call_args
        # Claude uses image_paths now too
        assert kwargs["image_paths"] == ["img1.png", "img2.png"]

@pytest.mark.asyncio
async def test_claude_prompt_file():
    """Test that --prompt-file reads prompt from file for Claude."""
    prompt_text = "Large Claude prompt " * 500
    tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False)
    tmp.write(prompt_text)
    tmp.close()
    
    mock_context = AsyncMock()
    mock_page = AsyncMock()
    mock_page.url = "https://claude.ai/"
    
    with patch("browser_automation.claude_automation.get_browser_context", return_value=(mock_context, mock_page)), \
         patch("browser_automation.claude_automation.send_prompt", new_callable=AsyncMock, return_value="mock response") as mock_send_prompt, \
         patch("sys.argv", ["claude_automation.py", "--prompt-file", tmp.name]):
        
        await claude_automation.main()
        
        mock_send_prompt.assert_called_once()
        args, kwargs = mock_send_prompt.call_args
        assert args[1] == prompt_text
        assert not os.path.exists(tmp.name)
