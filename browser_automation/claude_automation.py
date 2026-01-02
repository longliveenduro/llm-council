#!/usr/bin/env python3
"""
Claude Browser Automation Script

This script automates interactions with Claude (claude.ai) using Playwright.
It can input prompts, send them, and extract responses.

Usage:
    First run (to log in):
       python claude_automation.py --interactive
    
    Subsequent runs:
       python claude_automation.py "Your prompt here"
       
    Interactive mode:
       python claude_automation.py --interactive
"""

import asyncio
import argparse
import sys
import os
from pathlib import Path
from playwright.async_api import async_playwright, Page, BrowserContext

# Directory to store browser profile (keeps you logged in)
BROWSER_DATA_DIR = Path(__file__).parent / ".claude_browser_data"


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
    
    # Navigate to Claude if not already there
    if "claude.ai" not in page.url:
        await page.goto("https://claude.ai/")
    
    # Check for Captcha immediately
    if await detect_captcha(page):
        await wait_for_user_intervention(page)

    try:
        await page.wait_for_load_state("load", timeout=30000)
    except:
        print("Warning: Page load timeout, proceeding...")
    
    return context, page


async def detect_captcha(page: Page) -> bool:
    """Detect if a captcha or human verification is blocking the page."""
    try:
        # Check title and common captcha text
        title = await page.title()
        if "Just a moment" in title or "Verify you are human" in title:
            return True
        
        # Check for Cloudflare/hCaptcha iframe or text
        content = await page.content()
        if "cf-challenge" in content or "cf-turnstile-wrapper" in content or "challenge-form" in content:
            return True
            
        # Check for specific Cloudflare elements
        if await page.query_selector("#challenge-running") or await page.query_selector("#challenge-stage"):
            return True

        return False
    except:
        return False

async def wait_for_user_intervention(page: Page):
    """Wait for the user to solve a captcha or login."""
    print("\n" + "!"*50)
    print("ACTION REQUIRED: Captcha or human verification detected.")
    print("Please go to the browser window and complete the verification / click the checkbox.")
    print("The script will resume once the chat interface is visible.")
    print("!"*50 + "\n")
    
    # Wait until chat interface is visible
    while await detect_captcha(page):
        await asyncio.sleep(2)
        # Also check if we are redirected to the main page or login page
        if "claude.ai" in page.url and "Just a moment" not in await page.title():
             # Do a second check to be sure
             await asyncio.sleep(1)
             if not await detect_captcha(page):
                  break
    
    print("Verification completed. Resuming...")

async def check_login_required(page: Page) -> bool:
    """Check if a login is required."""
    try:
        # If we are on /login or see login buttons
        if "/login" in page.url:
            return True
        
        login_selectors = [
            'button:has-text("Sign in")',
            'button:has-text("Log in")',
            'input[type="email"]',
            'a[href*="login"]',
        ]
        
        for selector in login_selectors:
            element = await page.query_selector(selector)
            if element and await element.is_visible():
                return True
        
        return False
    except:
        return False


async def wait_for_chat_interface(page: Page, timeout: int = 30000):
    """Wait for the chat interface to be ready."""
    
    # If we hit Cloudflare, wait
    if await detect_captcha(page):
        await wait_for_user_intervention(page)

    # First check if login is required
    if await check_login_required(page):
        raise Exception("Login required. Please log in to Claude first using the Login button in the sidebar.")
    
    # Wait for the prompt input area to be available
    selectors = [
        '[contenteditable="true"]',
        'div[aria-label*="prompt" i]',
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
    Send a prompt to Claude and wait for the response.
    """
    
    # If we hit Cloudflare, wait
    if await detect_captcha(page):
        await wait_for_user_intervention(page)

    # Check if login required
    if await check_login_required(page):
        raise Exception("Login required. Please log in to Claude first using the Login button in the sidebar.")
    
    # Find the input element if not specified
    if not input_selector:
        input_selector = await wait_for_chat_interface(page)
    
    # Click on the input to focus it
    await page.click(input_selector, timeout=10000)
    await asyncio.sleep(0.1)
    
    # Clear and fill
    try:
        # Grant permissions first (context level)
        try:
             await page.context.grant_permissions(['clipboard-read', 'clipboard-write'])
        except:
             pass
        
        # Write to clipboard
        await page.evaluate("text => navigator.clipboard.writeText(text)", prompt)
        await asyncio.sleep(0.05)
        
        # Paste
        await page.keyboard.press("Control+v")
        
        # Fallback check
        await asyncio.sleep(0.5)
        content = await page.inner_text(input_selector)
        if not content or len(content) < 1:
             print("Warning: Paste might have failed, trying fill fallback...")
             await page.fill(input_selector, prompt)

    except Exception as e:
        print(f"Paste failed ({e}), falling back to fill...")
        await page.fill(input_selector, prompt)
    
    print(f"Typed prompt: {prompt[:50]}...")
    await asyncio.sleep(0.2)
    
    # Click Send button
    # Claude usually has a button with aria-label "Send Message" or an arrow icon
    send_button_selectors = [
        'button[aria-label*="Send" i]',
        'button:has(svg)',
        'button:has-text("Send")',
        'button[data-testid*="send" i]',
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
    # Claude shows a "Stop" button typically
    await asyncio.sleep(3) # Give it 3 seconds to start
    
    # Wait for streaming to finish
    try:
        # Look for the stop button
        stop_selector = 'button[aria-label*="Stop" i]'
        # It might take a moment to appear
        try:
            await page.wait_for_selector(stop_selector, timeout=10000)
            print("Detected stop button (generating...)")
        except:
            print("No stop button seen yet, checking for stability...")

        # Then wait for it to disappear
        await page.wait_for_selector(stop_selector, state="hidden", timeout=300000) # 5 min max
        print("Response generation completed (stop button gone)")
    except Exception as e:
        print(f"Did not detect completion via stop button ({e}), waiting for stability...")
        await asyncio.sleep(10) # Fallback wait

    return await extract_response(page, prompt)


async def extract_response(page: Page, prompt: str = None) -> str:
    """Extract the latest response from the chat."""
    
    # Wait a bit for final render
    await asyncio.sleep(3)
    
    # Selectors for Claude messages - ordered by preference
    response_selectors = [
        'div.font-claude-message .prose', # Specific Claude message prose
        '.font-claude-message',
        '[data-testid="message-container"] .prose',
        '[data-testid="message-container"]',
        '.claude-message',
        'div.prose',
        '.prose',
        'article div.prose',
    ]
    
    for selector in response_selectors:
        try:
            elements = await page.query_selector_all(selector)
            if elements:
                # Iterate from end to find the last assistant message
                for i in range(len(elements) - 1, -1, -1):
                    element = elements[i]
                    text = await element.inner_text()
                    if text and len(text.strip()) > 30:
                        # Check if this looks like a response vs UI
                        if "New chat" in text[:50] or "Chats" in text[:50]:
                            continue
                            
                        print(f"SUCCESS: Extracted response using selector: {selector}")
                        return clean_claude_text(text, prompt)
        except Exception:
            continue
    
    # Final attempt: use evaluate to find the last assistant message specifically
    try:
        text = await page.evaluate('''() => {
            // Find all prose blocks
            const proseBlocks = Array.from(document.querySelectorAll('.prose'));
            if (proseBlocks.length > 0) {
                // Return the last one
                return proseBlocks[proseBlocks.length - 1].innerText;
            }
            
            // Fallback: look for data-testid="message-container" and find the one that doesn't have a user avatar
            const containers = Array.from(document.querySelectorAll('[data-testid="message-container"]'));
            for (let i = containers.length - 1; i >= 0; i--) {
                const container = containers[i];
                const text = container.innerText || "";
                if (text.length > 50 && !text.includes('Chris')) { // Chris is the user name
                    return text.trim();
                }
            }
            
            // Heuristic: Last large block of text that isn't the whole body or sidebar
            const allElements = Array.from(document.querySelectorAll('div, section, article'));
            let bestMatch = null;
            let maxLen = 0;
            
            for (const el of allElements) {
                const text = el.innerText || "";
                // Filter out UI noise by checking content
                if (text.length > 100 && text.length < 20000 && !text.includes('New chat') && !text.includes('Join Pro')) {
                    if (text.length > maxLen) {
                        maxLen = text.length;
                        bestMatch = text;
                    }
                }
            }
            return bestMatch || null;
        }''')
    except Exception as e:
        print(f"DEBUG: Broad evaluation failed: {e}")
        text = None

    if text:
        return clean_claude_text(text, prompt)
        
    return "Error: Could not extract response."


def clean_claude_text(text: str, prompt: str = None) -> str:
    """Clean UI noise, disclaimers, and redundant prompt text."""
    import re
    
    text = text.strip()
    
    # Post-process to remove known UI noise/disclaimers
    garbage_strings = [
        "Claude is AI and can make mistakes. Please double-check responses.",
        "Sonnet 4.5",
        "Claude 3.5 Sonnet",
        "Claude 3 Opus",
        "Claude 3 Haiku",
        "Subscribe to Pro",
        "Copy to clipboard",
        "Share",
    ]
    
    lines = text.split('\n')
    clean_lines = []
    
    # Redundant prompt check
    normalized_prompt = prompt.strip().lower() if prompt else ""
    
    for line in lines:
        stripped_line = line.strip()
        if not stripped_line:
            clean_lines.append("")
            continue
            
        # Skip garbage strings
        if any(g in stripped_line for g in garbage_strings):
            continue
            
        # Skip timestamps like "3:29 AM"
        if re.match(r'^\d{1,2}:\d{2}\s+(AM|PM)$', stripped_line, re.IGNORECASE):
            continue
            
        # Skip redundant prompt lines
        if normalized_prompt and stripped_line.lower() == normalized_prompt:
            continue
            
        clean_lines.append(line)
    
    # Rejoin and strip leading/trailing whitespace
    text = '\n'.join(clean_lines).strip()
    
    # Remove large chunks of empty lines
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    print("SUCCESS: Cleaned response text.")
    return text


async def select_model(page: Page, model_name: str):
    """
    Select specific model if possible. 
    Claude's UI for model selection is often behind a menu.
    """
    # Not implemented yet as it varys a lot by UI version
    pass


async def main():
    parser = argparse.ArgumentParser(description="Automate Claude")
    parser.add_argument("prompt", nargs="?", help="The prompt to send")
    parser.add_argument("--interactive", "-i", action="store_true", 
                        help="Run in interactive mode")
    parser.add_argument("--model", "-m", default="auto",
                        help="Model to use (default: auto)")
    
    args = parser.parse_args()
    
    if not args.prompt and not args.interactive:
        parser.print_help()
        sys.exit(1)
    
    context = None
    try:
        context, page = await get_browser_context()
        
        if args.interactive:
            print("\n=== Claude Interactive Mode ===")
            print("Type your prompt. press Enter for new lines.")
            print("To SEND, type 'END' on a new line.")
            print("To EXIT, type 'quit' at the start.\n")
            
            while True:
                lines = []
                while True:
                    line = input()
                    if line.strip() == "END": break
                    if line.lower() == "quit": sys.exit(0)
                    lines.append(line)
                prompt = "\n".join(lines)
                if prompt:
                    response = await send_prompt(page, prompt)
                    print(f"\nClaude: {response}\n")
        else:
            response = await send_prompt(page, args.prompt)
            print("\nRESULT_START")
            print(response)
            print("RESULT_END")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if context:
            await context.close()


if __name__ == "__main__":
    asyncio.run(main())
