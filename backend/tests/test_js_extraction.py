import pytest
import os
from pathlib import Path
from playwright.async_api import async_playwright
from browser_automation.js_utils import HTML_TO_MARKDOWN_JS

@pytest.mark.asyncio
async def test_js_extraction_logic():
    """
    Verifies that the shared HTML_TO_MARKDOWN_JS correctly converts
    HTML structures (including Shadow DOM) to Markdown.
    """
    fixture_path = Path(__file__).parent / "fixtures" / "reproduce_extraction.html"
    file_url = f"file://{fixture_path.absolute()}"
    
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto(file_url)
        
        # Inject the utility function definition
        await page.evaluate(HTML_TO_MARKDOWN_JS)
        
        # --- Test 1: Standard Formatting ---
        result_standard = await page.evaluate("""
            const el = document.getElementById('standard-test');
            window.domToMarkdown(el);
        """)
        print(f"\n--- Standard Result ---\n{result_standard}")
        
        assert "# Heading 1" in result_standard
        assert "**bold**" in result_standard
        assert "_italic_" in result_standard
        assert "- Item 1" in result_standard
        assert "```python" in result_standard
        
        # --- Test 2: Shadow DOM ---
        # Note: We need to target the host element for extraction
        # Since our script handles Shadow DOM traversal, it should extract content inside it.
        # But we need to select the HOST element from the main document.
        # In the fixture, the host is the #shadow-host div (which became open shadow root host)
        # Wait, the fixture script attaches shadow to #shadow-host.
        
        result_shadow = await page.evaluate("""
            const el = document.getElementById('shadow-host');
            window.domToMarkdown(el);
        """)
        print(f"\n--- Shadow Result ---\n{result_shadow}")
        
        assert "## Shadow Heading" in result_shadow
        assert "**Shadow DOM**" in result_shadow
        
        # --- Test 3: Slots ---
        result_slot = await page.evaluate("""
            const el = document.querySelector('my-element');
            window.domToMarkdown(el);
        """)
        print(f"\n--- Slot Result ---\n{result_slot}")
        
        assert "Slotted Content" in result_slot
        
        # --- Test 4: Computed Styles ---
        result_computed = await page.evaluate("""
            const el = document.getElementById('computed-style-test');
            window.domToMarkdown(el);
        """)
        print(f"\n--- Computed Style Result ---\n{result_computed}")
        
        assert "**computed bold**" in result_computed
        assert "_computed italic_" in result_computed
        
        # --- Test 5: Edge Cases ---
        result_edge = await page.evaluate("""
            const el = document.getElementById('edge-cases');
            window.domToMarkdown(el);
        """)
        print(f"\n--- Edge Result ---\n{result_edge}")
        
        # We expect these to BE formatted if our script works perfectly.
        # If it fails, we have reproduced the issue.
        
        # 1. Custom tag with bold style
        assert "**Custom Bold**" in result_edge
        
        # 2. Block level style (div)
        # Note: 'Block Bold' inside a div might return as **Block Bold** or ** Block Bold ** depending on implementation
        assert "**Block Bold**" in result_edge
        
        # 3. Inherited Bold
        # The parent div is bold, the span inside is plain but inherits bold.
        # computedStyle on span should show bold.
        assert "**Inherited Bold**" in result_edge
        
        # 4. MS Bold (Custom block)
        assert "**MS Bold**" in result_edge
        
        # 5. Medium Weight (500) - Should act as bold for AI Studio emphasis
        # This is expected to FAIL currently, confirming the bug
        assert "**Medium Emphasis**" in result_edge

        await browser.close()
