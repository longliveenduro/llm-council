import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from browser_automation.chatgpt_automation import check_image_upload_quota_error

@pytest.mark.asyncio
async def test_check_image_upload_quota_error_detects_limit_message():
    """Test that it detects the quota limit message in the body text."""
    mock_page = MagicMock()
    
    # Simulate page text containing the specific quota error
    mock_page.evaluate = AsyncMock(return_value="Some text... You've reached your file upload limit. More text...")
    mock_page.query_selector = AsyncMock(return_value=None)
    
    result = await check_image_upload_quota_error(mock_page)
    
    assert result is True

@pytest.mark.asyncio
async def test_check_image_upload_quota_error_detects_quota_exceeded():
    """Test that it detects "quota exceeded" message."""
    mock_page = MagicMock()
    
    mock_page.evaluate = AsyncMock(return_value="Error: User quota exceeded.")
    mock_page.query_selector = AsyncMock(return_value=None)
    
    result = await check_image_upload_quota_error(mock_page)
    
    assert result is True

@pytest.mark.asyncio
async def test_check_image_upload_quota_error_no_error_present():
    """Test that it returns False when no quota error is on the page."""
    mock_page = MagicMock()
    
    mock_page.evaluate = AsyncMock(return_value="Welcome to ChatGPT. How can I help you today?")
    mock_page.query_selector = AsyncMock(return_value=None)
    
    result = await check_image_upload_quota_error(mock_page)
    
    assert result is False

@pytest.mark.asyncio
async def test_check_image_upload_quota_error_detects_in_toast_element():
    """Test that it detects the error message even if it's only in an error toast element."""
    mock_page = MagicMock()
    
    # No error in main body text
    mock_page.evaluate = AsyncMock(return_value="Main content...")
    
    # Mock an error toast element
    mock_error_element = MagicMock()
    mock_error_element.inner_text = AsyncMock(return_value="You've reached your file upload limit for today.")
    
    async def mock_query_selector(selector):
        if '[role="alert"]' in selector:
            return mock_error_element
        return None
        
    mock_page.query_selector = AsyncMock(side_effect=mock_query_selector)
    
    result = await check_image_upload_quota_error(mock_page)
    
    assert result is True

@pytest.mark.asyncio
async def test_check_image_upload_quota_error_handles_exception_gracefully():
    """Test that it returns False if an exception occurs during check (to avoid crashing main flow)."""
    mock_page = MagicMock()
    mock_page.evaluate = AsyncMock(side_effect=Exception("Browser disconnected"))
    
    result = await check_image_upload_quota_error(mock_page)
    
    assert result is False

@pytest.mark.asyncio
async def test_send_prompt_raises_on_quota_error():
    """Test that send_prompt raises an Exception when quota error is detected."""
    from browser_automation.chatgpt_automation import send_prompt
    
    mock_page = MagicMock()
    mock_page.url = "https://chatgpt.com/"
    
    # Mock input selector finding
    mock_page.wait_for_selector = AsyncMock(return_value=MagicMock())
    
    # Mock image upload flow - we need it to continue till the end of image paths handling
    mock_page.query_selector = AsyncMock(return_value=None)
    
    # Mock evaluate to return quota error after images "upload"
    # First call in send_prompt might be for model verification, we need to be careful with side_effects
    # In check_image_upload_quota_error, it calls:
    # page.evaluate('() => document.body.innerText.toLowerCase()')
    
    mock_page.evaluate = AsyncMock(return_value="you've reached your file upload limit")
    
    # Other mocks needed for send_prompt to run
    mock_page.click = AsyncMock()
    mock_page.fill = AsyncMock()
    
    with pytest.raises(Exception) as excinfo:
        await send_prompt(mock_page, "test prompt", image_paths=["fake.jpg"])
        
    assert "ChatGPT image upload quota exceeded" in str(excinfo.value)
