
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from browser_automation.ai_studio_automation import extract_response

@pytest.mark.asyncio
async def test_ai_studio_truncation_repro_split_chunks():
    """
    Reproduce truncation where text is split between ms-text-chunk elements 
    but only the last one or a subset is picked up, OR where some text is in 
    other elements that are NOT ms-text-chunk but are part of the last turn.
    """
    mock_page = MagicMock()
    mock_last_turn = MagicMock()
    
    # Simulate first part of the response in a standard chunk
    mock_chunk1 = MagicMock()
    mock_chunk1.inner_text = AsyncMock(return_value="Part 1: The model explains why something exists.")
    
    # Simulate a second part that might be in a DIFFERENT element type (e.g. a div or p)
    # The current extract_response only looks for 'ms-text-chunk'
    mock_missing_chunk = MagicMock()
    mock_missing_chunk.inner_text = AsyncMock(return_value="Part 2: This is the missing information that is being truncated.")
    
    async def mock_query_selector(selector):
        if selector == 'ms-chat-turn:last-of-type':
            return mock_last_turn
        return None

    mock_page.query_selector = AsyncMock(side_effect=mock_query_selector)
    
    # Current implementation: chunks = await last_turn.query_selector_all('ms-text-chunk')
    # Let's say chunk1 is ms-text-chunk, but chunk2 is just a div inside the turn.
    async def mock_query_selector_all_scoped(selector):
        if 'ms-text-chunk' in selector:
            return [mock_chunk1]
        if 'p' in selector or 'div' in selector:
            return [mock_missing_chunk]
        return []

    mock_last_turn.query_selector_all = AsyncMock(side_effect=mock_query_selector_all_scoped)
    
    # Also simulate that there are OTHER elements in the last turn that contain text
    # but aren't 'ms-text-chunk'.
    mock_last_turn.get_attribute = AsyncMock(return_value=None)
    
    # Mock clipboard failure to force visual extraction
    mock_page.evaluate = AsyncMock(return_value=None) 
    
    # We also need to mock broadly for the fallback
    mock_page.query_selector_all = AsyncMock(return_value=[])

    response = await extract_response(mock_page)
    
    print(f"\nExtracted Response: {response}")
    
    # EXPECTED FAILURE: Currently, "Part 2" will likely be missing if it's not in ms-text-chunk
    # or if the logic for finding chunks is too restrictive.
    assert "Part 1" in response
    assert "Part 2" in response, "REPRODUCTION SUCCESSFUL: Part 2 was truncated!"

@pytest.mark.asyncio
async def test_ai_studio_truncation_repro_nested_chunks():
    """
    Test if nested chunks are missed.
    """
    mock_page = MagicMock()
    mock_last_turn = MagicMock()
    
    # A chunk that is nested deeper
    mock_nested_chunk = MagicMock()
    mock_nested_chunk.inner_text = AsyncMock(return_value="Deeply nested text.")
    
    async def mock_query_selector(selector):
        if selector == 'ms-chat-turn:last-of-type':
            return mock_last_turn
        return None

    mock_page.query_selector = AsyncMock(side_effect=mock_query_selector)
    
    # If the selector is 'ms-text-chunk', and it's nested, query_selector_all('ms-text-chunk') SHOULD find it
    # unless it's in a shadow DOM or something (AI Studio doesn't seem to use much shadow DOM here).
    # But let's assume it's NOT an 'ms-text-chunk' but contains the text.
    
    mock_other_element = MagicMock()
    mock_other_element.inner_text = AsyncMock(return_value="Text in a div.")
    
    async def mock_query_selector_all_scoped(selector):
        if 'div' in selector:
            return [mock_other_element]
        return []

    mock_last_turn.query_selector_all = AsyncMock(side_effect=mock_query_selector_all_scoped)
    
    # Mock broadly
    mock_page.evaluate = AsyncMock(return_value=None)
    mock_page.query_selector_all = AsyncMock(return_value=[])
    
    response = await extract_response(mock_page)
    
    print(f"\nExtracted Response: {response}")
    
    # If it returns the 'Could not extract response' or omits the div text, it reproduces the issue.
    assert "Text in a div" in response, "REPRODUCTION SUCCESSFUL: Non ms-text-chunk content was missed!"
