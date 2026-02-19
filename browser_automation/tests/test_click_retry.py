import pytest
import sys
from unittest.mock import AsyncMock, MagicMock
from pathlib import Path

# Add the directory containing chatgpt_automation to the path
sys.path.append(str(Path(__file__).parent.parent))

from chatgpt_automation import robust_click_send_button

@pytest.mark.asyncio
async def test_robust_click_success_first_try():
    """Test standard success case where button is found and clickable immediately."""
    mock_page = AsyncMock()
    mock_btn = AsyncMock()
    mock_btn.is_disabled.return_value = False
    
    # wait_for_selector returns the button
    mock_page.wait_for_selector.return_value = mock_btn
    
    result = await robust_click_send_button(mock_page)
    
    assert result is True
    # Should have called wait_for_selector at least once
    mock_page.wait_for_selector.assert_called()
    # Should have called click on the page with the selector
    mock_page.click.assert_called()

@pytest.mark.asyncio
async def test_robust_click_retry_logic():
    """Test retry logic: first attempt fails (raises or button not found), second attempt succeeds."""
    mock_page = AsyncMock()
    mock_btn = AsyncMock()
    mock_btn.is_disabled.return_value = False
    
    # Side effect for wait_for_selector: 
    # 1. Raise exception (first selector attempt)
    # 2. Return None (second selector attempt)
    # 3. Return btn (third attempt / next retry iteration)
    
    # Note: robust_click iterates through 3 selectors in a loop, repeated 3 times.
    # We want to simulate failure on first few calls.
    
    # Let's say first loop (3 selectors) all fail
    failures = [Exception("Timeout"), Exception("Timeout"), Exception("Timeout")]
    success = mock_btn
    
    mock_page.wait_for_selector.side_effect = failures + [success]
    
    result = await robust_click_send_button(mock_page)
    
    assert result is True
    # Verify multiple calls were made
    assert mock_page.wait_for_selector.call_count >= 4
    mock_page.click.assert_called_once()

@pytest.mark.asyncio
async def test_robust_click_reattach_simulation():
    """Test scenario where button is found but click fails (simulating detachment), then retry succeeds."""
    mock_page = AsyncMock()
    mock_btn = AsyncMock()
    mock_btn.is_disabled.return_value = False
    
    mock_page.wait_for_selector.return_value = mock_btn
    
    # Click raises exception first time, succeeds second time
    mock_page.click.side_effect = [Exception("Element detached"), None]
    
    result = await robust_click_send_button(mock_page)
    
    assert result is True
    # Should have called click twice
    assert mock_page.click.call_count == 2
