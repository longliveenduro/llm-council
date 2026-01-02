import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from browser_automation.ai_studio_automation import extract_response as extract_ai_studio
from browser_automation.chatgpt_automation import extract_response as extract_chatgpt
from browser_automation.claude_automation import extract_response as extract_claude

@pytest.mark.asyncio
async def test_ai_studio_extraction_multiple_chunks():
    """Test that AI Studio extraction joins multiple ms-text-chunk elements."""
    mock_page = MagicMock()
    
    # Precise mock for query_selector
    async def mock_query_selector(selector):
        if selector == 'ms-chat-turn:last-of-type':
            mock_last_turn = MagicMock()
            
            mock_chunk1 = MagicMock()
            mock_chunk1.inner_text = AsyncMock(return_value="Chunk 1")
            mock_chunk2 = MagicMock()
            mock_chunk2.inner_text = AsyncMock(return_value="Chunk 2")
            
            mock_last_turn.query_selector_all = AsyncMock(return_value=[mock_chunk1, mock_chunk2])
            return mock_last_turn
        return None

    mock_page.query_selector = AsyncMock(side_effect=mock_query_selector)
    mock_page.query_selector_all = AsyncMock(return_value=[])
    
    response = await extract_ai_studio(mock_page)
    assert response == "Chunk 1\nChunk 2"

@pytest.mark.asyncio
async def test_chatgpt_extraction_multiple_markdown_blocks():
    """Test that ChatGPT extraction joins multiple markdown blocks within an assistant message."""
    mock_page = MagicMock()
    
    # Mock blocks
    mock_block1 = MagicMock()
    mock_block1.inner_text = AsyncMock(return_value="Block 1")
    mock_block2 = MagicMock()
    mock_block2.inner_text = AsyncMock(return_value="Block 2")
    
    # Mock assistant
    mock_assistant = MagicMock()
    mock_assistant.query_selector_all = AsyncMock(return_value=[mock_block1, mock_block2])
    
    async def mock_query_selector(selector, **kwargs):
        if selector == '[data-message-author-role="assistant"]:last-of-type':
            return mock_assistant
        return None

    async def mock_query_selector_all(selector):
        if selector == '.markdown':
            return [mock_block1, mock_block2]
        if selector == '[data-message-author-role="assistant"]':
            return [mock_assistant]
        return []

    mock_page.query_selector = AsyncMock(side_effect=mock_query_selector)
    mock_page.query_selector_all = AsyncMock(side_effect=mock_query_selector_all)
    
    response = await extract_chatgpt(mock_page)
    assert response == "Block 1\n\nBlock 2"

@pytest.mark.asyncio
async def test_claude_extraction():
    """Test that Claude extraction finds the correct prose block."""
    mock_page = MagicMock()
    
    # Mock assistant message prose
    mock_prose = MagicMock()
    mock_prose.inner_text = AsyncMock(return_value="This is a Claude response.")
    
    async def mock_query_selector_all(selector):
        if selector == 'div.font-claude-message .prose':
            return [mock_prose]
        return []

    mock_page.query_selector_all = AsyncMock(side_effect=mock_query_selector_all)
    
    # Also mock evaluate as a fallback
    mock_page.evaluate = AsyncMock(return_value="This is a Claude response.")
    
    response = await extract_claude(mock_page)
    assert "This is a Claude response." in response
