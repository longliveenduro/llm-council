import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from backend.council import run_chatgpt_automation, run_claude_automation, run_ai_studio_automation
import json

@pytest.mark.asyncio
async def test_run_chatgpt_automation_parses_json_output():
    """Test that run_chatgpt_automation correctly parses JSON_OUTPUT from stdout."""
    mock_process = MagicMock()
    mock_process.communicate = AsyncMock(return_value=(
        b"Standard logging message\nJSON_OUTPUT: " + 
        json.dumps({
            "response": "Hello from ChatGPT",
            "error_msgs": None,
            "error": False,
            "error_type": None
        }).encode() + b"\nMore logging",
        b""
    ))
    mock_process.returncode = 0
    
    with patch("asyncio.create_subprocess_exec", return_value=mock_process), \
         patch("backend.council.CHATGPT_LOCK", AsyncMock()):
        result = await run_chatgpt_automation("test prompt")
        
        assert result["response"] == "Hello from ChatGPT"
        assert result["error"] is False
        assert result["error_type"] is None

@pytest.mark.asyncio
async def test_run_chatgpt_automation_handles_error_json():
    """Test that run_chatgpt_automation correctly parses error JSON_OUTPUT."""
    mock_process = MagicMock()
    mock_process.communicate = AsyncMock(return_value=(
        b"JSON_OUTPUT: " + 
        json.dumps({
            "response": None,
            "error_msgs": "Quota exceeded",
            "error": True,
            "error_type": "quota_exceeded"
        }).encode() + b"\n",
        b""
    ))
    mock_process.returncode = 1
    
    with patch("asyncio.create_subprocess_exec", return_value=mock_process), \
         patch("backend.council.CHATGPT_LOCK", AsyncMock()):
        result = await run_chatgpt_automation("test prompt")
        
        assert result["response"] is None
        assert result["error"] is True
        assert result["error_type"] == "quota_exceeded"
        assert result["error_msgs"] == "Quota exceeded"

@pytest.mark.asyncio
async def test_run_claude_automation_parses_json_output():
    """Test that run_claude_automation correctly parses JSON_OUTPUT."""
    mock_process = MagicMock()
    mock_process.communicate = AsyncMock(return_value=(
        b"JSON_OUTPUT: " + 
        json.dumps({
            "response": "Hello from Claude",
            "error_msgs": None,
            "error": False,
            "error_type": None
        }).encode() + b"\n",
        b""
    ))
    mock_process.returncode = 0
    
    with patch("asyncio.create_subprocess_exec", return_value=mock_process), \
         patch("backend.council.CLAUDE_LOCK", AsyncMock()):
        result = await run_claude_automation("test prompt")
        
        assert result["response"] == "Hello from Claude"
        assert result["error"] is False

@pytest.mark.asyncio
async def test_run_ai_studio_automation_parses_json_output():
    """Test that run_ai_studio_automation correctly parses JSON_OUTPUT."""
    mock_process = MagicMock()
    mock_process.communicate = AsyncMock(return_value=(
        b"JSON_OUTPUT: " + 
        json.dumps({
            "response": "Hello from Gemini",
            "error_msgs": None,
            "error": False,
            "error_type": None
        }).encode() + b"\n",
        b""
    ))
    mock_process.returncode = 0
    
    with patch("asyncio.create_subprocess_exec", return_value=mock_process), \
         patch("backend.council.AI_STUDIO_LOCK", AsyncMock()):
        result = await run_ai_studio_automation("test prompt", "gemini-pro")
        
        assert result["response"] == "Hello from Gemini"
        assert result["error"] is False

@pytest.mark.asyncio
async def test_run_automation_fallback_to_legacy():
    """Test that run_chatgpt_automation falls back to legacy parsing if JSON_OUTPUT is missing but RESULT_START/END is present."""
    mock_process = MagicMock()
    mock_process.communicate = AsyncMock(return_value=(
        b"Some logs\nRESULT_START\nLegacy Response\nRESULT_END\nMore logs",
        b""
    ))
    mock_process.returncode = 0
    
    with patch("asyncio.create_subprocess_exec", return_value=mock_process), \
         patch("backend.council.CHATGPT_LOCK", AsyncMock()):
        result = await run_chatgpt_automation("test prompt")
        
        assert result["response"] == "Legacy Response"
        assert result["error"] is False
        assert result["error_type"] is None

@pytest.mark.asyncio
async def test_run_automation_subprocess_error_no_json():
    """Test handling of subprocess failure without any structured output."""
    mock_process = MagicMock()
    mock_process.communicate = AsyncMock(return_value=(
        b"Critical error happened",
        b"Stderr details"
    ))
    mock_process.returncode = 1
    
    with patch("asyncio.create_subprocess_exec", return_value=mock_process), \
         patch("backend.council.CHATGPT_LOCK", AsyncMock()):
        result = await run_chatgpt_automation("test prompt")
        
        assert result["error"] is True
        assert result["error_type"] == "generic_error"
        assert "(Code 1)" in result["error_msgs"]
