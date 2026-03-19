import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_ai_studio_model_mapping():
    """Test that Gemini 3.1 Pro Preview maps correctly to its URL parameter and click selector."""
    
    # We will import the main function which parses args
    # But since it's an async script, we can just test the mapping logic directly or run the script with a mock
    from browser_automation.ai_studio_automation import select_model
    
    # Mock the playwright page
    mock_page = AsyncMock()
    mock_element = AsyncMock()
    mock_element.inner_text.return_value = "Some Other Model"
    mock_page.query_selector.return_value = mock_element
    mock_page.inner_text.return_value = "Gemini 3.1 Pro Preview"
    
    # Call select_model with Gemini 3.1 Pro Preview
    await select_model(mock_page, "Gemini 3.1 Pro Preview")
    
    # Ensure it clicked the combo box
    mock_page.click.assert_any_call("ms-model-selector button")
    
    # Ensure it waited for the carousel
    mock_page.wait_for_selector.assert_any_call("ms-model-carousel", state="visible")
    
    # Ensure it tried to click the correct ID
    mock_page.wait_for_selector.assert_any_call("[id*='gemini-3.1-pro-preview']", timeout=2000)
    mock_page.click.assert_any_call("[id*='gemini-3.1-pro-preview']")

@pytest.mark.asyncio
async def test_ai_studio_url_param():
    """Test that Gemini 3.1 Pro Preview generates correct URL param."""
    
    # We can mock get_browser_context to prevent launching actual browser
    with patch("browser_automation.ai_studio_automation.get_browser_context", new_callable=AsyncMock) as mock_ctx:
        mock_page = AsyncMock()
        mock_page.url = "https://aistudio.google.com/prompts/new_chat"
        mock_ctx.return_value = (AsyncMock(), mock_page)
        
        with patch("sys.argv", ["ai_studio_automation.py", "test prompt", "--model", "Gemini 3.1 Pro Preview"]):
            from browser_automation.ai_studio_automation import main
            
            # Mock the interactive parts
            with patch("browser_automation.ai_studio_automation.wait_for_chat_interface", new_callable=AsyncMock):
                with patch("browser_automation.ai_studio_automation.send_prompt", new_callable=AsyncMock) as mock_send:
                    mock_send.return_value = "Test response"
                    await main()
                    
            # Gemini 3.1 Pro Preview should add a ?model parameter now
            mock_page.goto.assert_any_call("https://aistudio.google.com/prompts/new_chat?model=gemini-3.1-pro-preview")
