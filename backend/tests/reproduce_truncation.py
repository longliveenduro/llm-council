
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from browser_automation.ai_studio_automation import extract_response

@pytest.mark.asyncio
async def test_ai_studio_extraction_gap_repro():
    """
    Reproduce a potential bug where extraction might miss chunks if they are not 
    all children of ms-chat-turn:last-of-type or if they are in different elements.
    """
    mock_page = MagicMock()
    
    # Mock for a turn that contains multiple chunks
    mock_last_turn = MagicMock()
    
    # Simulate first part of the response
    mock_chunk1 = MagicMock()
    mock_chunk1.inner_text = AsyncMock(return_value="Part 1 of the response...")
    
    # Simulate a second part that might be separated or in a different format
    mock_chunk2 = MagicMock()
    mock_chunk2.inner_text = AsyncMock(return_value="Part 2 of the response.")
    
    # This mock will be returned by query_selector('ms-chat-turn:last-of-type')
    async def mock_query_selector(selector):
        if selector == 'ms-chat-turn:last-of-type':
            return mock_last_turn
        return None

    mock_page.query_selector = AsyncMock(side_effect=mock_query_selector)
    mock_last_turn.query_selector_all = AsyncMock(return_value=[mock_chunk1, mock_chunk2])
    
    # We also need to mock clipboard failure to trigger visual extraction
    mock_page.evaluate = AsyncMock(return_value=None) 
    
    response = await extract_response(mock_page)
    
    # If it works, it should join them
    assert "Part 1" in response
    assert "Part 2" in response
    print(f"\nResponse: {response}")

@pytest.mark.asyncio
async def test_ai_studio_extraction_with_markdown_blocks():
    """
    Test extraction if chunks are actually in a different element type.
    """
    mock_page = MagicMock()
    mock_last_turn = MagicMock()
    
    # Supposing AI Studio starts using ms-markdown-block instead of ms-text-chunk
    mock_block = MagicMock()
    mock_block.inner_text = AsyncMock(return_value="This is markdown content")
    
    async def mock_query_selector(selector):
        if selector == 'ms-chat-turn:last-of-type':
            return mock_last_turn
        return None

    mock_page.query_selector = AsyncMock(side_effect=mock_query_selector)
    
    # ms-text-chunk query returns empty
    mock_last_turn.query_selector_all = AsyncMock(return_value=[])
    
    # Broader selectors query
    async def mock_query_selector_all(selector):
        if 'ms-text-chunk' in selector:
            return []
        if 'p' in selector:
            mock_p = MagicMock()
            mock_p.inner_text = AsyncMock(return_value="Last resort paragraph")
            return [mock_p]
        return []

    mock_page.query_selector_all = AsyncMock(side_effect=mock_query_selector_all)
    mock_page.evaluate = AsyncMock(return_value=None)
    
    response = await extract_response(mock_page)
    assert "Last resort" in response

@pytest.mark.asyncio
async def test_delimiter_logic_repro():
    """
    Verify that the new delimiter logic correctly extracts the full response
    even if it contains 'Response:' or 'Exit code:'.
    """
    automation_output = """
DEBUG: Found input element
Typed prompt: ...
Prompt sent, waiting for response...
Response generation completed
DEBUG: Found 1 chunks in last turn. Joined length: 150
-------------------- Automation Output --------------------
DEBUG: Extra garbage
RESULT_START
Response A provides a good evaluation. 
However, in Response: to your earlier question, it might be different.
FINAL RANKING:
1. Response A
RESULT_END
DEBUG: More garbage
Exit code: 0
--------------------
"""
    # The new logic:
    if "RESULT_START" in automation_output and "RESULT_END" in automation_output:
        response = automation_output.split("RESULT_START")[1].split("RESULT_END")[0].strip()
    
    print(f"\nCorrectly Extracted Response: {response}")
    # It should correctly get the whole thing now
    assert "Response A provides" in response
    assert "it might be different" in response
    assert "FINAL RANKING" in response
    assert "RESULT_END" not in response
