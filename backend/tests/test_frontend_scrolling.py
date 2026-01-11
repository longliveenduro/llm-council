
import pytest
from playwright.async_api import async_playwright
import asyncio

# This test assumes the frontend is running on localhost:5173
# You may need to ensure 'npm run dev' is running in the frontend directory.

@pytest.mark.asyncio
async def test_preview_scrolling():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        
        try:
            # Navigate to the app
            await page.goto("http://localhost:5173", timeout=10000)
        except Exception as e:
            pytest.skip(f"Frontend not accessible: {e}")

        # Wait for app to load
        # Check if we are in empty state or have conversations
        try:
            # Wait for either new conv button or input area
            await page.wait_for_selector(".new-conv-empty-btn, .input-area", timeout=5000)
        except:
             print("DEBUG: Page content:", await page.content())
             pytest.fail("Could not find new conv button or input area")

        # If we see empty state button, click it
        if await page.is_visible(".new-conv-empty-btn"):
             await page.click(".new-conv-empty-btn")
        
        # Now we should have input area
        await page.wait_for_selector(".input-area", timeout=5000)

        # Toggle Web ChatBot mode
        mode_toggle = page.locator(".input-area .mode-toggle .slider")
        await mode_toggle.click()

        # Wait for Wizard Step 1 header
        await page.wait_for_selector("text=Step 1: Initial Opinions", timeout=5000)

        # Enter a question
        await page.fill("#user-query", "Test Question for Scrolling")

        # Locate the write textarea in the add response form
        textarea = page.locator(".input-content-wrapper textarea")
        
        # Generate long content: 200 lines to be sure
        long_text = "\n".join([f"Line {i} content for scrolling test" for i in range(200)])
        await textarea.fill(long_text)

        # Enable Preview tab
        await page.click("button:has-text('Preview')")

        # Wait for preview content to appear
        preview_content = page.locator(".input-preview-content")
        await preview_content.wait_for()
        
        # Allow a moment for rendering layout
        await page.wait_for_timeout(500)

        # Get scroll properties
        scroll_height = await preview_content.evaluate("el => el.scrollHeight")
        client_height = await preview_content.evaluate("el => el.clientHeight")
        overflow_y = await preview_content.evaluate("el => window.getComputedStyle(el).overflowY")

        print(f"DEBUG: scrollHeight={scroll_height}, clientHeight={client_height}, overflowY={overflow_y}")

        # Assertion 1: Content should be taller than container (proving it needs scrolling)
        # If this fails, the container might be expanding to fit content (the bug)
        # or the viewport is huge.
        # But if clientHeight == scrollHeight for huge content, it means the container grew.
        # We expect clientHeight < scrollHeight.
        
        # However, checking if it GREW too much is also a valid check.
        # Let's check if clientHeight is constrained. 
        # The container should reasonably fit in the viewport.
        viewport_height = page.viewport_size['height']
        
        # If clientHeight is larger than, say, 80% of viewport, it likely pushed the bounds.
        # But specifically, we want scrollHeight > clientHeight.
        
        if scroll_height <= client_height:
             # This implies NO scrollbar needed. 
             # If content is large, this means container expanded.
             pytest.fail(f"Container expanded to fit content! scrollHeight({scroll_height}) == clientHeight({client_height}). Expected scrollHeight > clientHeight.")

        # Assertion 2: Overflow should be auto or scroll
        assert overflow_y in ['auto', 'scroll'], f"overflow-y was {overflow_y}, expected 'auto' or 'scroll'"

        await browser.close()
