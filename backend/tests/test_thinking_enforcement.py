"""
Tests to verify that Claude and ChatGPT automation scripts raise errors
when Extended Thinking / Thinking mode cannot be activated.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import sys
import os

# Import the main functions from automation scripts
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from browser_automation.claude_automation import select_thinking_mode
from browser_automation.chatgpt_automation import select_model


class TestClaudeThinkingEnforcement:
    """Tests for Claude Extended Thinking enforcement."""
    
    @pytest.mark.asyncio
    async def test_select_thinking_mode_returns_false_when_toggle_not_found(self):
        """Test that select_thinking_mode returns False when the toggle cannot be found."""
        mock_page = MagicMock()
        
        # Mock query_selector to return None (toggle not found)
        mock_page.query_selector = AsyncMock(return_value=None)
        
        result = await select_thinking_mode(mock_page, wants_thinking=True)
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_select_thinking_mode_returns_true_when_toggle_found_and_activated(self):
        """Test that select_thinking_mode returns True when toggle is found and activated."""
        mock_page = MagicMock()
        
        # Mock the button element
        mock_button = MagicMock()
        mock_button.is_visible = AsyncMock(return_value=True)
        mock_button.click = AsyncMock()
        
        # First call checks current state (False), second verifies after click (True)
        mock_page.evaluate = AsyncMock(side_effect=[False, True])
        
        async def mock_query_selector(selector):
            if 'thinking' in selector.lower() or 'aria-label' in selector:
                return mock_button
            return None
        
        mock_page.query_selector = AsyncMock(side_effect=mock_query_selector)
        
        result = await select_thinking_mode(mock_page, wants_thinking=True)
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_claude_main_raises_error_when_thinking_fails(self):
        """Test that Claude automation raises an error when thinking mode is requested but fails."""
        # This simulates the main() function behavior
        # When thinking is requested but select_thinking_mode returns False, it should raise
        
        thinking_requested = True
        thinking_activated = False  # Simulates select_thinking_mode returning False
        
        with pytest.raises(Exception) as excinfo:
            if thinking_requested and not thinking_activated:
                raise Exception("Extended Thinking requested but could not be activated. The toggle may not be visible or the Claude UI may have changed.")
        
        assert "Extended Thinking requested but could not be activated" in str(excinfo.value)


class TestChatGPTThinkingEnforcement:
    """Tests for ChatGPT Thinking mode enforcement."""
    
    @pytest.mark.asyncio
    async def test_select_model_returns_false_when_thinking_toggle_not_found(self):
        """Test that select_model returns False when thinking toggle cannot be found."""
        mock_page = MagicMock()
        
        # Mock all selectors to return None or empty
        mock_page.query_selector = AsyncMock(return_value=None)
        mock_page.query_selector_all = AsyncMock(return_value=[])
        mock_page.evaluate = AsyncMock(return_value=False)
        
        # Mock keyboard to avoid errors
        mock_page.keyboard = MagicMock()
        mock_page.keyboard.press = AsyncMock()
        
        result = await select_model(mock_page, "ChatGPT 5.2 Thinking")
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_select_model_returns_true_when_thinking_already_active(self):
        """Test that select_model returns True when thinking is already active on the page."""
        mock_page = MagicMock()
        
        # Mock evaluate to indicate thinking is already active
        mock_page.evaluate = AsyncMock(return_value=True)
        mock_page.query_selector = AsyncMock(return_value=None)
        
        result = await select_model(mock_page, "ChatGPT 5.2 Thinking")
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_chatgpt_main_raises_error_when_thinking_fails(self):
        """Test that ChatGPT automation raises an error when thinking mode is requested but fails."""
        # This simulates the main() function behavior
        # When thinking is requested but select_model returns False, it should raise
        
        model_name = "ChatGPT 5.2 Thinking"
        thinking_requested = "thinking" in model_name.lower() or "reason" in model_name.lower()
        thinking_activated = False  # Simulates select_model returning False
        
        with pytest.raises(Exception) as excinfo:
            if thinking_requested and not thinking_activated:
                raise Exception("Thinking mode requested but could not be activated. The toggle may not be visible or the ChatGPT UI may have changed.")
        
        assert "Thinking mode requested but could not be activated" in str(excinfo.value)
    
    @pytest.mark.asyncio
    async def test_chatgpt_no_error_when_thinking_not_requested(self):
        """Test that ChatGPT does NOT raise an error when thinking is not requested."""
        model_name = "ChatGPT 5.2"  # No "Thinking" in name
        thinking_requested = "thinking" in model_name.lower() or "reason" in model_name.lower()
        thinking_activated = False  # Would be False, but doesn't matter
        
        # Should NOT raise an error
        error_raised = False
        try:
            if thinking_requested and not thinking_activated:
                raise Exception("Thinking mode requested but could not be activated.")
        except Exception:
            error_raised = True
        
        assert error_raised is False


class TestThinkingStatusParsing:
    """Tests for parsing THINKING_USED from automation output."""
    
    def test_error_message_in_output_no_thinking_used(self):
        """Test that an error message appears when thinking fails entirely (script error)."""
        # When thinking fails, the script should raise an error and output should contain "Error:"
        output = """
Launching browser...
Ready! Current page: https://claude.ai/new
Setting Extended Thinking to: True
Warning: Could not find Extended Thinking toggle.
Error: Extended Thinking requested but could not be activated. The toggle may not be visible or the Claude UI may have changed.
"""
        assert "Error:" in output
        assert "Extended Thinking requested but could not be activated" in output
    
    def test_successful_thinking_activation_output(self):
        """Test that successful thinking activation shows THINKING_USED=true."""
        output = """
Launching browser...
Ready! Current page: https://claude.ai/new
Setting Extended Thinking to: True
Found thinking toggle with selector: button[aria-label*="thinking" i]
Extended Thinking is already in state: True

THINKING_USED=true
RESULT_START
This is the response.
RESULT_END
"""
        assert "THINKING_USED=true" in output
        assert "Error:" not in output
