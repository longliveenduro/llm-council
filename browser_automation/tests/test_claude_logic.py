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

@pytest.mark.asyncio
async def test_select_thinking_mode_opens_menu_if_needed():
    mock_page = AsyncMock()
    
    # Mock elements
    mock_model_selector = AsyncMock()
    mock_model_selector.is_visible.return_value = True
    
    # Menu structure: Label wrapping an Input
    mock_menu_label = AsyncMock()
    mock_menu_label.is_visible.return_value = True
    mock_menu_label.evaluate.return_value = "label" # It's a label
    
    mock_input_inside_label = AsyncMock()
    mock_input_inside_label.is_visible.return_value = False # Invisible/sr-only
    mock_input_inside_label.evaluate.return_value = "input"
    mock_input_inside_label.is_checked.return_value = False # Currently OFF
    
    # When querying input inside label
    mock_menu_label.query_selector.return_value = mock_input_inside_label
    
    
    async def side_effect_qsa(selector):
        # Top level toggles - return empty
        if 'thinking-toggle' in selector or 'aria-label="thinking"' in selector:
            return []
        if 'name*="thinking"' in selector:
            return []
            
        if 'model-selector' in selector or 'Sonnet' in selector:
            return [mock_model_selector]
            
        # Menu discovery
        # We search for label:has(input[role="switch"])
        if 'label:has(input' in selector:
             return [mock_menu_label]
             
        return []

    mock_page.query_selector_all.side_effect = side_effect_qsa
    mock_page.query_selector.return_value = None # No "is on" text

    with patch("browser_automation.claude_automation.wait_for_chat_interface", new_callable=AsyncMock), \
         patch("browser_automation.claude_automation.detect_captcha", AsyncMock(return_value=False)), \
         patch("browser_automation.claude_automation.check_login_required", AsyncMock(return_value=False)), \
         patch("browser_automation.claude_automation.asyncio.sleep", new_callable=AsyncMock):
        
        # We want thinking to be True
        result = await select_thinking_mode(mock_page, wants_thinking=True)
        
        assert result is True
        
        # Verify flow:
        # 1. Clicked model selector
        mock_model_selector.click.assert_called()
        
        # 2. Clicked the LABEL (because input is invisible)
        mock_menu_label.click.assert_called()
        
        # 3. Pressed Escape to close menu
        mock_page.keyboard.press.assert_called_with("Escape")
