#!/usr/bin/env python3
"""
ChatGPT Browser Automation Script

This script automates interactions with ChatGPT (chatgpt.com) using Playwright.
It can input prompts, send them, and extract responses.

Usage:
    First run (to log in):
       python chatgpt_automation.py --interactive
    
    Subsequent runs:
       python chatgpt_automation.py "Your prompt here"
       
    Interactive mode:
       python chatgpt_automation.py --interactive
"""

import asyncio
import argparse
import sys
import os
from pathlib import Path
from playwright.async_api import async_playwright, Page, BrowserContext

# Directory to store browser profile (keeps you logged in)
BROWSER_DATA_DIR = Path(__file__).parent / ".chatgpt_browser_data"


async def get_browser_context() -> tuple[BrowserContext, Page]:
    """Get a browser context with persistent storage (keeps login state)."""
    playwright = await async_playwright().start()
    
    # Create data dir if it doesn't exist
    BROWSER_DATA_DIR.mkdir(exist_ok=True)
    
    # Use persistent context - this saves cookies/login between runs
    context = await playwright.chromium.launch_persistent_context(
        user_data_dir=str(BROWSER_DATA_DIR),
        headless=False,
        viewport={"width": 1400, "height": 900},
        args=["--disable-blink-features=AutomationControlled"],
    )
    
    # Get existing page or create new one
    if context.pages:
        page = context.pages[0]
    else:
        page = await context.new_page()
    
    # Navigate to ChatGPT if not already there
    if "chatgpt.com" not in page.url:
        await page.goto("https://chatgpt.com/")
        try:
            await page.wait_for_load_state("networkidle", timeout=60000)
        except:
            print("Warning: Network idle timeout, proceeding potentially without full load.")
    
    return context, page


async def check_login_required(page: Page) -> bool:
    """Check if a login modal is blocking the interface."""
    login_modal_selectors = [
        '[data-testid="modal-no-auth-login"]',
        '[data-testid="login-modal"]',
        'button:has-text("Log in")',
        'button:has-text("Sign up")',
    ]
    
    for selector in login_modal_selectors:
        try:
            element = await page.query_selector(selector)
            if element and await element.is_visible():
                return True
        except:
            continue
    
    return False


async def wait_for_chat_interface(page: Page, timeout: int = 30000):
    """Wait for the chat interface to be ready."""
    
    # First check if login is required
    if await check_login_required(page):
        raise Exception("Login required. Please log in to ChatGPT first using the Login button in the sidebar.")
    
    # Wait for the prompt input area to be available
    selectors = [
        '#prompt-textarea',
        'textarea[placeholder*="Message" i]',
        'div[contenteditable="true"]',
        'textarea',
    ]
    
    for selector in selectors:
        try:
            element = await page.wait_for_selector(selector, timeout=5000)
            if element:
                print(f"Found input element with selector: {selector}")
                return selector
        except:
            continue
    
    raise Exception("Could not find chat input element")


async def send_prompt(page: Page, prompt: str, input_selector: str = None) -> str:
    """
    Send a prompt to ChatGPT and wait for the response.
    
    Args:
        page: Playwright page object
        prompt: The prompt text to send
        input_selector: Optional specific selector for the input
        
    Returns:
        The response text
    """
    
    # Check if login modal is blocking
    if await check_login_required(page):
        raise Exception("Login required. Please log in to ChatGPT first using the Login button in the sidebar.")
    
    # Find the input element if not specified
    if not input_selector:
        input_selector = await wait_for_chat_interface(page)
    
    # Click on the input to focus it
    await page.click(input_selector, timeout=10000)
    await asyncio.sleep(0.3)
    
    # Clear and fill
    await page.fill(input_selector, "")
    
    try:
        # Use clipboard paste for speed and reliability with complex text
        # Grant permissions first (context level)
        try:
             await page.context.grant_permissions(['clipboard-read', 'clipboard-write'])
        except:
             pass
        
        # Write to clipboard
        await page.evaluate("text => navigator.clipboard.writeText(text)", prompt)
        await asyncio.sleep(0.1)
        
        # Paste
        await page.keyboard.press("Control+v")
        
        # Fallback verification: if empty, try fill
        await asyncio.sleep(0.5)
        # Determine if it's a textarea or contenteditable div to check value properly
        val = await page.input_value(input_selector) if await page.evaluate(f"document.querySelector('{input_selector}').tagName === 'TEXTAREA'") else await page.inner_text(input_selector)

        if not val or len(val) < 1:
             print("Warning: Paste might have failed, trying fill fallback...")
             await page.fill(input_selector, prompt)

    except Exception as e:
        print(f"Paste failed ({e}), falling back to fill...")
        await page.fill(input_selector, prompt)
    
    print(f"Typed prompt: {prompt[:50]}...")
    await asyncio.sleep(0.5)
    
    # Click Send button
    send_button_selectors = [
        '[data-testid="send-button"]',
        'button[aria-label*="Send" i]',
        'button:has-text("Send")',
    ]
    
    send_button = None
    for selector in send_button_selectors:
        try:
            send_button = await page.wait_for_selector(selector, timeout=2000)
            if send_button and await send_button.is_visible() and not await send_button.is_disabled():
                print(f"Found send button with selector: {selector}")
                break
        except:
            continue
            
    if send_button:
        await send_button.click()
    else:
        print("No send button found, trying Enter key...")
        await page.keyboard.press("Enter")
    
    print("Prompt sent, waiting for response...")
    
    # Wait for response generation to complete
    # ChatGPT usually shows a "Stop generating" button or similar while working
    await asyncio.sleep(2)
    
    # Wait for streaming to finish (stop button disappears)
    try:
        # Wait for potential stop button to appear (it might appear briefly)
        # We don't error if it doesn't appear, as short responses might be instant
        await page.wait_for_selector('[data-testid="stop-button"]', timeout=3000)
        # Then wait for it to disappear
        await page.wait_for_selector('[data-testid="stop-button"]', state="hidden", timeout=120000)
        print("Response generation completed (stop button missing)")
    except:
        # If we didn't see a stop button, maybe it was too fast or selector changed
        # We'll rely on text stability
        print("Did not detect stop button, waiting for stability...")
        await asyncio.sleep(3)

    return await extract_response(page)


async def extract_response(page: Page) -> str:
    """Extract the latest response from the chat."""
    
    # Wait a bit for final render
    await asyncio.sleep(1)
    
    # Selectors for assistant messages
    response_selectors = [
        '[data-message-author-role="assistant"]',
        '.markdown', 
        '.agent-turn'
    ]
    
    for selector in response_selectors:
        try:
            elements = await page.query_selector_all(selector)
            if elements:
                # Get the last one
                last_element = elements[-1]
                text = await last_element.inner_text()
                if text:
                    return text.strip()
        except Exception as e:
            print(f"Extraction error with {selector}: {e}")
            continue
            
    return "Error: Could not extract response."


async def select_model(page: Page, model_name: str):
    """
    Attempt to select a model (placeholder mostly, as ChatGPT 
    often remembers last used or requires URL param).
    """
    # Simple URL based switching could be added here
    # e.g. if model_name == "gpt-4", goto https://chatgpt.com/?model=gpt-4
    pass 



def get_multiline_input() -> str:
    """Read multi-line input from stdin."""
    print("\nYou (Type 'END' on a new line to send, 'quit' to exit):")
    lines = []
    while True:
        try:
            line = input()
            if line.strip() == "END":
                break
            if line.lower() in ['quit', 'exit'] and not lines:
                return "quit"
            lines.append(line)
        except EOFError:
            break
    return "\n".join(lines)


async def interactive_mode(page: Page):
    """Run in interactive mode."""
    print("\n=== ChatGPT Interactive Mode ===")
    print("Type your prompt. press Enter for new lines.")
    print("To SEND, type 'END' on a new line.")
    print("To EXIT, type 'quit' at the start.\n")
    
    input_selector = await wait_for_chat_interface(page)
    
    while True:
        try:
            prompt = get_multiline_input()
            if prompt == "quit":
                print("Goodbye!")
                break
            
            if not prompt.strip():
                continue
            
            response = await send_prompt(page, prompt, input_selector)
            print(f"\nChatGPT: {response}")
            
        except KeyboardInterrupt:
            print("\n\nInterrupted. Goodbye!")
            break
        except Exception as e:
            print(f"\nError: {e}")


async def main():
    parser = argparse.ArgumentParser(description="Automate ChatGPT")
    parser.add_argument("prompt", nargs="?", help="The prompt to send")
    parser.add_argument("--interactive", "-i", action="store_true", 
                        help="Run in interactive mode")
    parser.add_argument("--model", "-m", default="auto",
                        help="Model to use (default: auto)")
    
    args = parser.parse_args()
    
    if not args.prompt and not args.interactive:
        parser.print_help()
        print("\nError: Please provide a prompt or use --interactive mode")
        sys.exit(1)
    
    context = None
    try:
        print("Launching browser...")
        context, page = await get_browser_context()
        
        print(f"Ready! Current page: {page.url}")
        
        # Check for login redirection
        if "auth" in page.url or "login" in page.url:
            print("\n>>> Please log in to ChatGPT in the browser <<<")
            print(">>> Press Enter here once you're logged in and on the chat interface <<<")
            input()
        
        if args.interactive:
            await interactive_mode(page)
        else:
            response = await send_prompt(page, args.prompt)
            print(f"\nResponse:\n{response}")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if context:
            await context.close()


if __name__ == "__main__":
    asyncio.run(main())
