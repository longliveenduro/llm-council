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


async def send_prompt(page: Page, prompt: str, input_selector: str = None, model: str = "auto") -> str:
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
    
    # Handle Extended Thinking
    if model and "thinking" in model.lower():
        await select_thinking_mode(page, wants_thinking=True)
    
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

    return await extract_response(page, prompt, model)


async def extract_response(page: Page, prompt: str = None, model: str = "auto") -> str:
    """Extract the latest response from the chat."""
    
    # Wait a bit for initial content
    await asyncio.sleep(1)
    
    # Helper function to get current text length from the last Claude message
    async def get_current_text_length() -> int:
        try:
            elements = await page.query_selector_all('div.font-claude-message .prose')
            if elements:
                text = await elements[-1].inner_text()
                return len(text) if text else 0
        except:
            pass
        return 0

    # Content stabilization: wait until text length stops growing
    print("DEBUG: Waiting for content to stabilize...")
    prev_len = 0
    stable_count = 0
    max_stabilization_wait = 5  # seconds (reduced from 10)
    stabilization_interval = 0.5  # seconds
    elapsed = 0
    
    while elapsed < max_stabilization_wait:
        current_len = await get_current_text_length()
        
        if current_len > 0 and current_len == prev_len:
            stable_count += 1
            # Content is stable if length hasn't changed for 2 consecutive checks (1.0s)
            if stable_count >= 2:
                print(f"DEBUG: Content stabilized at {current_len} characters after {elapsed:.1f}s")
                break
        else:
            stable_count = 0
            
        prev_len = current_len
        await asyncio.sleep(stabilization_interval)
        elapsed += stabilization_interval
    
    if elapsed >= max_stabilization_wait:
        print(f"DEBUG: Stabilization timeout reached, proceeding with extraction (length: {prev_len})")
    
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
                        return clean_claude_text(text, prompt, model)
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
        return clean_claude_text(text, prompt, model)
        
    return "Error: Could not extract response."


def clean_claude_text(text: str, prompt: str = None, model: str = "auto") -> str:
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
        "Want to be notified when Claude responds? Notify",
        "Want to be notified when Claude responds?",
        "The user prompt is empty, so I cannot provide a summary in the user's language.",
        "The user is asking about",
        "Acknowledge the profundity",
        "Present different philosophical",
        "Be honest about the limits",
        "Avoid being overly didactic",
    ]
    
    # Specific line-by-line garbage to remove if it's EXACTLY this
    exact_garbage_lines = [
        "Notify",
    ]
    
    lines = text.split('\n')
    clean_lines = []
    
    # Redundant prompt check
    normalized_prompt = prompt.strip().lower() if prompt else ""
    
    # Identify thinking summary and duration
    # Often: [Thinking Summary] -> [Duration] -> [Response]
    # We want to skip the summary and duration if possible
    
    skip_next_lines = 0
    for i, line in enumerate(lines):
        if skip_next_lines > 0:
            skip_next_lines -= 1
            continue
            
        stripped_line = line.strip()
        if not stripped_line:
            clean_lines.append("")
            continue
            
        # Skip exact garbage lines
        if stripped_line in exact_garbage_lines:
            continue

        # Skip garbage strings
        if any(g in stripped_line for g in garbage_strings):
            continue
            
        # Skip timestamps like "3:29 AM"
        if re.match(r'^\d{1,2}:\d{2}\s+(AM|PM)$', stripped_line, re.IGNORECASE):
            continue
            
        # Skip durations like "26s", "2.1m", "1.5h"
        if re.match(r'^\d+(\.\d+)?[smh]$', stripped_line):
            continue
            
        # Skip redundant prompt lines
        if normalized_prompt and stripped_line.lower() == normalized_prompt:
            continue
            
        # Heuristic for thinking summary: 
        # If this is one of the first few non-empty lines, doesn't look like a header,
        # and it's followed by a duration or is very short and followed by a blank line then the response.
        # Claude's thinking summaries are usually single sentences.
        if i < 15 and len(stripped_line) > 10 and len(stripped_line) < 500:
            # Check if it starts with common thinking verbs/phrases
            thinking_starters = [
                "Weighed", "Evaluated", "Analyzed", "Explored", "Considered", 
                "Reflected", "Pondered", "Examined", "Thought", "Researched", 
                "Compare", "Revised", "Simplified", "Drafted", "Identified",
                "Synthesized", "Categorized", "Delved", "Balanced",
                "Let me think", "Let's think", "I will approach",
                "This is one of the", "This is a fundamental", "The question of"
            ]
            
            # Check for specific preamble patterns
            preamble_patterns = [
                r"The user prompt is empty",
                r"Based on the thinking block",
                r"Here is a summary",
                r"Let me think about how to approach",
                r"I should:",
            ]
            
            is_summary = False
            
            # Pattern 1: Starts with thinking verb/phrase
            if any(stripped_line.lower().startswith(s.lower()) for s in thinking_starters):
                # Extra check: if it ends with a question, it might be the start of the response
                if not stripped_line.endswith("?"):
                    is_summary = True
            
            # Pattern 2: Matches preamble patterns
            if any(re.search(pat, stripped_line, re.I) for pat in preamble_patterns):
                is_summary = True
                
            # Pattern 3: Followed by a duration line
            if not is_summary:
                next_non_empty = ""
                for j in range(i + 1, min(i + 5, len(lines))):
                    if lines[j].strip():
                        next_non_empty = lines[j].strip()
                        break
                if next_non_empty and re.match(r'^\d+(\.\d+)?[smh]$', next_non_empty):
                    is_summary = True
            
            if is_summary:
                # One more check: make sure it's not a list item or header
                if not stripped_line.startswith(('-', '*', '#', '1.')):
                    continue

        clean_lines.append(line)
    
    # Rejoin and strip leading/trailing whitespace
    text = '\n'.join(clean_lines).strip()

    # Remove large chunks of empty lines
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    print("SUCCESS: Cleaned response text.")
    return text


async def select_thinking_mode(page: Page, wants_thinking: bool = True):
    """
    Find and click the "stop clock" symbol to toggle Extended Thinking.
    """
    print(f"Setting Extended Thinking to: {wants_thinking}")
    
    # Selectors for the "stop clock" / "timer" button
    thinking_button_selectors = [
        'button:has(svg path[d*="M12 20"])', # Possible path for the clock/timer
        'button:has(svg[class*="timer"])',
        'button:has(svg[class*="clock"])',
        'button[aria-label*="thinking" i]',
        'button:has-text("Thinking")',
        'svg[class*="timer"]', # Sometimes the SVG itself is the target
        'svg[class*="clock"]',
    ]
    
    # Check current state if possible
    # This is tricky without knowing the exact DOM, but we can look for "Thinking" text or active class
    
    for selector in thinking_button_selectors:
        try:
            button = await page.query_selector(selector)
            if button and await button.is_visible():
                print(f"Found thinking toggle with selector: {selector}")
                
                # Check if already active
                is_active = await page.evaluate('''(el) => {
                    // Check for active classes or parent state
                    const btn = el.closest('button') || el;
                    return btn.getAttribute('aria-pressed') === 'true' || 
                           btn.classList.contains('active') ||
                           document.body.innerText.includes('Extended thinking is on');
                }''', button)
                
                if is_active == wants_thinking:
                    print(f"Extended Thinking is already in state: {wants_thinking}")
                    return
                
                await button.click()
                print("Clicked thinking toggle.")
                await asyncio.sleep(1)
                return
        except Exception as e:
            continue
            
    print("Warning: Could not find Extended Thinking toggle.")


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
                    response = await send_prompt(page, prompt, model=args.model)
                    print(f"\nClaude: {response}\n")
        else:
            response = await send_prompt(page, args.prompt, model=args.model)
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
