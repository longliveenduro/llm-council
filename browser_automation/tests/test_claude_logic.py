import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from browser_automation.claude_automation import select_thinking_mode, send_prompt

@pytest.mark.asyncio
async def test_select_thinking_mode_searches_and_clicks():
    mock_page = AsyncMock()
    mock_el = AsyncMock()
    mock_el.is_visible.return_value = True
    mock_el.get_attribute.return_value = "false" # aria-checked=false
    
    mock_page.query_selector_all.return_value = [mock_el]
    mock_page.query_selector.return_value = None # For the "is on" text check
    
    with patch("browser_automation.claude_automation.wait_for_chat_interface", new_callable=AsyncMock), \
         patch("browser_automation.claude_automation.detect_captcha", AsyncMock(return_value=False)), \
         patch("browser_automation.claude_automation.check_login_required", AsyncMock(return_value=False)), \
         patch("browser_automation.claude_automation.asyncio.sleep", new_callable=AsyncMock):
        # We want thinking to be True
        result = await select_thinking_mode(mock_page, wants_thinking=True)
        
        assert result is True
        # Should have clicked the toggle
        mock_el.click.assert_called_once()

@pytest.mark.asyncio
async def test_send_prompt_focuses_and_sends():
    mock_page = AsyncMock()
    mock_page.context = AsyncMock()
    
    with patch("browser_automation.claude_automation.wait_for_chat_interface", AsyncMock(return_value="#input")), \
         patch("browser_automation.claude_automation.detect_captcha", AsyncMock(return_value=False)), \
         patch("browser_automation.claude_automation.check_login_required", AsyncMock(return_value=False)), \
         patch("browser_automation.claude_automation.asyncio.sleep", new_callable=AsyncMock), \
         patch("browser_automation.claude_automation.extract_response", AsyncMock(return_value="done")):
        await send_prompt(mock_page, "Hello", input_selector="#input")
