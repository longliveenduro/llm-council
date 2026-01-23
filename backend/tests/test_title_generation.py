import pytest
from unittest.mock import patch, MagicMock
from backend.council import generate_conversation_title

@pytest.mark.asyncio
async def test_generate_conversation_title_success():
    with patch('backend.council.run_ai_studio_automation') as mock_run:
        mock_run.return_value = "The Future of AI"
        
        title = await generate_conversation_title("What is the future of artificial intelligence?")
        
        assert title == "The Future of AI"
        mock_run.assert_called_once()
        # Verify it used the new Flash model
        args, kwargs = mock_run.call_args
        assert kwargs.get('model') == "Gemini Flash Latest"

@pytest.mark.asyncio
async def test_generate_conversation_title_fallback():
    with patch('backend.council.run_ai_studio_automation') as mock_run:
        mock_run.return_value = "Error: Something went wrong"
        
        title = await generate_conversation_title("Any question?")
        
        assert title == "New Conversation"

@pytest.mark.asyncio
async def test_generate_conversation_title_cleanup():
    with patch('backend.council.run_ai_studio_automation') as mock_run:
        mock_run.return_value = '"A Clean Title"'
        
        title = await generate_conversation_title("Ignore this query")
        
        assert title == "A Clean Title"
