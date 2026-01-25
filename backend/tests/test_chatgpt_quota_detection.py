
import pytest
from unittest.mock import AsyncMock, MagicMock
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from browser_automation.chatgpt_automation import check_image_upload_quota_error, send_prompt

@pytest.mark.asyncio
async def test_quota_detection_via_body_text():
    """Test detection of quota patterns in body text."""
    mock_page = AsyncMock()
    mock_page.evaluate.return_value = "some content... upgrade to go for more uploads ... other content"
    mock_page.query_selector.return_value = None
    
    result = await check_image_upload_quota_error(mock_page)
    assert result is True

@pytest.mark.asyncio
async def test_send_prompt_quota_in_menu(monkeypatch):
    """Test that send_prompt fails if 'Upgrade to Go' is in the Plus menu."""
    mock_page = AsyncMock()
    
    # Mock helpers to avoid login check and interface wait
    monkeypatch.setattr("browser_automation.chatgpt_automation.check_login_required", AsyncMock(return_value=False))
    monkeypatch.setattr("browser_automation.chatgpt_automation.wait_for_chat_interface", AsyncMock(return_value="#prompt-textarea"))
    
    # Mock Plus button
    mock_plus_btn = AsyncMock()
    mock_page.wait_for_selector.return_value = mock_plus_btn
    
    # Mock Menu items
    mock_item_upgrade = AsyncMock()
    mock_item_upgrade.is_visible.return_value = True
    mock_item_upgrade.inner_text.return_value = "Upgrade to Go for more uploads"
    
    mock_item_other = AsyncMock()
    mock_item_other.is_visible.return_value = True
    mock_item_other.inner_text.return_value = "Search"
    
    mock_page.query_selector_all.return_value = [mock_item_upgrade, mock_item_other]
    
    # Mock extract_response and other helpers
    with pytest.raises(Exception) as excinfo:
        await send_prompt(mock_page, "Hello", image_paths=["test.png"])
    
    assert "quota exceeded" in str(excinfo.value).lower()

@pytest.mark.asyncio
async def test_send_prompt_upload_missing_in_menu(monkeypatch):
    """Test that send_prompt fails if 'Add photos & files' is missing from menu."""
    mock_page = AsyncMock()
    
    # Mock helpers
    monkeypatch.setattr("browser_automation.chatgpt_automation.check_login_required", AsyncMock(return_value=False))
    monkeypatch.setattr("browser_automation.chatgpt_automation.wait_for_chat_interface", AsyncMock(return_value="#prompt-textarea"))

    # Mock Plus button
    mock_plus_btn = AsyncMock()
    mock_page.wait_for_selector.return_value = mock_plus_btn
    
    # Mock Menu items - NO upload button
    mock_item_other = AsyncMock()
    mock_item_other.is_visible.return_value = True
    mock_item_other.inner_text.return_value = "Search"
    
    mock_page.query_selector_all.return_value = [mock_item_other]
    
    # For the fallback check_image_upload_quota_error
    mock_page.evaluate.return_value = "quota exceeded" 
    
    with pytest.raises(Exception) as excinfo:
        await send_prompt(mock_page, "Hello", image_paths=["test.png"])
    
    assert "quota exceeded" in str(excinfo.value).lower()

@pytest.mark.asyncio
async def test_send_prompt_fails_if_no_thumbnail(monkeypatch):
    """Test that send_prompt fails if no thumbnail appears after upload."""
    mock_page = AsyncMock()
    
    # Mock helpers
    monkeypatch.setattr("browser_automation.chatgpt_automation.check_login_required", AsyncMock(return_value=False))
    monkeypatch.setattr("browser_automation.chatgpt_automation.wait_for_chat_interface", AsyncMock(return_value="#prompt-textarea"))

    # Mock Plus button
    mock_plus_btn = AsyncMock()
    mock_page.wait_for_selector.return_value = mock_plus_btn
    
    # Mock Menu items - Upload button IS present
    mock_item_upload = AsyncMock()
    mock_item_upload.is_visible.return_value = True
    mock_item_upload.inner_text.return_value = "Add photos & files"
    mock_page.query_selector_all.return_value = [mock_item_upload]
    
    # Mock hidden file input
    mock_file_input = AsyncMock()
    mock_page.query_selector.side_effect = lambda s: mock_file_input if 'input[type="file"]' in s else None
    
    # Mock thumbnail wait - FAIL (returns None)

    def wait_side_effect(selector, **kwargs):
        if "attachment" in selector or "thumbnail" in selector:
            return None # Simulate not appearing
        return AsyncMock()

    mock_page.wait_for_selector.side_effect = wait_side_effect
    
    with pytest.raises(Exception) as excinfo:
        await send_prompt(mock_page, "Hello", image_paths=["test.png"])
    
    assert "No attachment detected" in str(excinfo.value) or "Failed to upload" in str(excinfo.value)


