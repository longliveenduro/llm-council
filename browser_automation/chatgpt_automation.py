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

# Combined JS script for extraction
CHATGPT_JS = r'''
(() => {
    const assistantMessages = document.querySelectorAll('[data-message-author-role="assistant"]');
    if (assistantMessages.length === 0) return null;
    
    const lastMessage = assistantMessages[assistantMessages.length - 1];
    
    // Clone to avoid side effects
    const clone = lastMessage.cloneNode(true);
    
    // 1. Process Math Elements (KaTeX)
    const mathContainers = clone.querySelectorAll('.katex-display, .math-display, :not(.katex-display) > .katex, :not(.math-display) > .math');
    mathContainers.forEach(container => {
        const annotation = container.querySelector('annotation[encoding="application/x-tex"]');
        if (annotation) {
            const latex = annotation.textContent.trim();
            const isBlock = container.classList.contains('katex-display') || container.classList.contains('math-display');
            container.textContent = isBlock ? `\n$$\n${latex}\n$$\n` : `$${latex}$`;
        }
    });
    
    clone.querySelectorAll('.katex, .math').forEach(el => {
        if (el.textContent.includes('$')) return;
        const ann = el.querySelector('annotation');
        if (ann) el.textContent = ann.textContent;
    });

    const allElements = clone.querySelectorAll('button, span, .cit-button, [data-testid*="citation"]');
    allElements.forEach(el => {
        const text = (el.textContent || "").trim();
        if (/^\[?\+\d+\]?$/.test(text) || /^\[\d+\]$/.test(text)) el.remove();
        if (el.getAttribute('data-testid') && el.getAttribute('data-testid').includes('citation')) el.remove();
    });

    const artifacts = clone.querySelectorAll('.flex.items-center.justify-between.mt-2, .sr-only, .mt-2.flex.gap-3');
    artifacts.forEach(a => a.remove());

    clone.style.position = 'absolute';
    clone.style.left = '-9999px';
    clone.style.whiteSpace = 'pre-wrap';
    document.body.appendChild(clone);
    
    let resultText = null;
    try {
        const content = clone.querySelector('.markdown, .prose') || clone;
        resultText = content.innerText.trim();
    } finally {
        document.body.removeChild(clone);
    }
    
    return resultText;
})()
'''


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
        if "cf-challenge" in content or "cf-turnstile-wrapper" in content:
            return True
            
        return False
    except:
        return False

async def wait_for_user_intervention(page: Page):
    """Wait for the user to solve a captcha or login."""
    print("\n" + "!"*50)
    print("ACTION REQUIRED: Captcha or human verification detected.")
    print("Please go to the browser window and complete the verification.")
    print("The script will resume once the chat interface is visible.")
    print("!"*50 + "\n")
    
    # Wait until chat interface is visible
    while await detect_captcha(page):
        await asyncio.sleep(2)
    
    print("Verification completed. Resuming...")

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
            element = await page.wait_for_selector(selector, timeout=2000)
            if element:
                print(f"Found input element with selector: {selector}")
                return selector
        except:
            continue
    
    raise Exception("Could not find chat input element")


async def send_prompt(page: Page, prompt: str, input_selector: str = None, image_paths: list = None) -> str:
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
    
    # Note: Model selection and thinking mode are now handled in main() before calling send_prompt

    # Handle image uploads
    if image_paths:
        print(f"[DEBUG] Processing {len(image_paths)} images for ChatGPT...")
        attached_direct = False
        # 1. Try direct upload via hidden input first
        try:
            file_input = await page.query_selector('input[type="file"]')
            if file_input:
                print("[DEBUG] Found hidden file input in ChatGPT, setting all files...")
                await file_input.set_input_files(image_paths)
                # Wait for any thumbnail
                await page.wait_for_selector('button[aria-label="Remove attachment"], [data-testid="attachment-thumbnail"], [data-testid="bubble-file"], div[class*="attachment"]', timeout=10000)
                print("[DEBUG] Images attached via hidden input in ChatGPT.")
                attached_direct = True
            else:
                print("[DEBUG] No hidden file input found initially in ChatGPT.")
        except Exception as e:
            print(f"[DEBUG] Direct upload attempt in ChatGPT failed: {e}")

        # 2. Sequential fallback (only if direct didn't work)
        if not attached_direct:
            for image_path in image_paths:
                if not image_path: continue
                
                print(f"Uploading image to ChatGPT: {image_path}")
                try:
                    # Try to find attachment button
                    attach_btn = await page.wait_for_selector('button[aria-label="Add photos and files"], button[aria-label="Attach files"], [data-testid="attach-button"]', timeout=5000)
                    
                    if attach_btn:
                         async with page.expect_file_chooser() as fc_info:
                             await attach_btn.click()
                         file_chooser = await fc_info.value
                         await file_chooser.set_files(image_path)
                         print("[DEBUG] Image set via file chooser.")
                    else:
                        # Fallback to direct input inside loop
                        file_input = await page.query_selector('input[type="file"]')
                        if file_input:
                            await file_input.set_input_files(image_path)
                            print("[DEBUG] Image set via hidden input in loop.")
                        else:
                            print("[ERROR] Could not find attachment mechanism.")
                    
                    # Wait for upload to complete
                    await page.wait_for_selector('button[aria-label="Remove attachment"], [data-testid="attachment-thumbnail"], [data-testid="bubble-file"], div[class*="attachment"]', timeout=30000)
                    print(f"Image {image_path} uploaded successfully to ChatGPT.")
                    
                except Exception as e:
                    print(f"[ERROR] Failed to upload image {image_path}: {e}")
                    try:
                        html = await page.content()
                        with open("chatgpt_dump.html", "w") as f:
                            f.write(html)
                        print("Dumped HTML to chatgpt_dump.html")
                    except:
                        pass

    # Click on the input to focus it
    await page.click(input_selector, timeout=10000)
    await asyncio.sleep(0.1)
    
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
        await asyncio.sleep(0.05)
        
        # Paste
        await page.keyboard.press("Control+v")
        
        # Fallback verification: if empty, try fill
        await asyncio.sleep(0.2)
        # Determine if it's a textarea or contenteditable div to check value properly
        val = await page.input_value(input_selector) if await page.evaluate(f"document.querySelector('{input_selector}').tagName === 'TEXTAREA'") else await page.inner_text(input_selector)

        if not val or len(val) < 1:
             print("Warning: Paste might have failed, trying fill fallback...")
             await page.fill(input_selector, prompt)

    except Exception as e:
        print(f"Paste failed ({e}), falling back to fill...")
        await page.fill(input_selector, prompt)
    
    print(f"Typed prompt: {prompt[:50]}...")
    await asyncio.sleep(0.2)
    
    # Click Send button
    send_button_selectors = [
        '[data-testid="send-button"]',
        'button[aria-label*="Send" i]',
        'button:has-text("Send")',
    ]
    
    send_button = None
    for selector in send_button_selectors:
        try:
            send_button = await page.wait_for_selector(selector, timeout=1000)
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
    await asyncio.sleep(1)
    
    # Wait for streaming to finish (stop button disappears)
    try:
        # Wait for potential stop button to appear (it might appear briefly)
        # We don't error if it doesn't appear, as short responses might be instant
        await page.wait_for_selector('[data-testid="stop-button"]', timeout=2000)
        # Then wait for it to disappear
        await page.wait_for_selector('[data-testid="stop-button"]', state="hidden", timeout=120000)
        print("Response generation completed (stop button missing)")
    except:
        # If we didn't see a stop button, maybe it was too fast or selector changed
        # We'll rely on text stability
        print("Did not detect stop button, waiting for stability...")
        await asyncio.sleep(2)

    return await extract_response(page)


async def extract_response(page: Page) -> str:
    """Extract the latest response from the chat."""
    
    # Wait a bit for initial content
    await asyncio.sleep(0.5)
    
    # Helper function to get current text length from the last assistant message
    async def get_current_text_length() -> int:
        try:
            elements = await page.query_selector_all('[data-message-author-role="assistant"]')
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
    max_stabilization_wait = 5  # seconds
    stabilization_interval = 0.5  # seconds
    elapsed = 0
    
    while elapsed < max_stabilization_wait:
        current_len = await get_current_text_length()
        
        if current_len > 0 and current_len == prev_len:
            stable_count += 1
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
    
    # Use JavaScript for intelligent extraction
    try:
        text = await page.evaluate(CHATGPT_JS)

        
        if text:
            print("SUCCESS: Extracted response using JS with math/citation handling")
            return clean_chatgpt_text(text)
    except Exception as e:
        print(f"DEBUG: JS extraction failed: {e}")

    # Fallback to simple extraction
    response_selectors = [
        '[data-message-author-role="assistant"]',
        '.markdown', 
        '.agent-turn'
    ]
    
    for selector in response_selectors:
        try:
            elements = await page.query_selector_all(selector)
            if elements:
                last_element = elements[-1]
                text = await last_element.inner_text()
                if text:
                    return clean_chatgpt_text(text.strip())
        except:
            continue
    
    return "Error: Could not extract response."


def clean_chatgpt_text(text: str) -> str:
    """Clean UI noise and artifacts from ChatGPT responses."""
    import re
    
    if not text:
        return ""
        
    lines = text.split('\n')
    clean_lines = []
    
    # List of strings that are likely UI noise when they appear alone on a line
    noise_patterns = [
        r'^\+\d+$',                # +1, +2, etc.
        r'^NobelPrize\.org$',      # Common citation source
        r'^NASA Science$',         # Common citation source
        r'^scientificamerican\.com$', # Common citation source
        r'^arXiv$',                # Common citation source
        r'^reuters\.com$',         # Common citation source
        r'^britannica\.com$',      # Common citation source
        r'^wikipedia\.org$',       # Common citation source
    ]
    
    for line in lines:
        stripped = line.strip()
        if not stripped:
            clean_lines.append("")
            continue
            
        # Skip lines that match noise patterns
        is_noise = False
        for pattern in noise_patterns:
            if re.match(pattern, stripped, re.IGNORECASE):
                is_noise = True
                break
        
        if is_noise:
            continue
            
        clean_lines.append(line)
        
    result = '\n'.join(clean_lines).strip()
    
    # Final cleanup of multiple newlines
    result = re.sub(r'\n{3,}', '\n\n', result)
    
    return result



async def select_model(page: Page, model_name: str) -> bool:
    """
    1. Select specific model from top-left (o1, o3, etc.)
    2. Toggle thinking mode if requested (via + menu)
    Returns True if thinking mode was successfully enabled, False otherwise.
    """
    if model_name == "auto" or not model_name:
        return False

    print(f"[DEBUG] Setting up ChatGPT mode: {model_name}")
    
    # 1. TOP-LEFT MODEL SELECTION (Non-critical for Thinking)
    target_model_text = model_name.replace("Thinking", "").replace("Reasoning", "").strip()
    if target_model_text and "ChatGPT" not in target_model_text and len(target_model_text) > 1:
        try:
            selector_btn = await page.query_selector('button[aria-label*="Model selector"]')
            if selector_btn:
                await selector_btn.click()
                await asyncio.sleep(0.5)
                # Try simple text match
                model_item = await page.query_selector(f'button:has-text("{target_model_text}")')
                if model_item:
                    print(f"[DEBUG] Found model '{target_model_text}' in dropdown, selecting...")
                    await model_item.click()
                    await asyncio.sleep(0.5)
                await page.keyboard.press("Escape")
        except:
            pass

    # 2. THINKING MODE TOGGLE (Critical)
    wants_thinking = "thinking" in model_name.lower() or "reason" in model_name.lower()
    if not wants_thinking:
        return False

    print(f"[DEBUG] Thinking mode requested for: {model_name}")
    
    try:
        # Check if already active
        verified = await page.evaluate('''() => {
            const composer = document.querySelector('form, [data-testid*="composer"]');
            const bodyText = document.body.innerText.toLowerCase();
            const composerText = composer ? composer.innerText.toLowerCase() : "";
            return bodyText.includes('think') || bodyText.includes('reason') || composerText.includes('think');
        }''')
        if (verified):
            print("[DEBUG] Thinking/Think indicator already found on page. Proceeding.")
            return True

        # 1. Check for direct toggle button in the composer area
        print("[DEBUG] Checking for direct Thinking toggle in composer...")
        direct_toggle = await page.query_selector('form button:has-text("Think"), form button:has-text("Reason"), [aria-label*="Thinking"], [aria-label*="Reasoning"]')
        if not direct_toggle:
            direct_toggle = await page.query_selector('form button:has(svg path[d*="M12"]), form button:has(svg[class*="sparkle"])')
            
        if direct_toggle and await direct_toggle.is_visible():
            print("[DEBUG] Found potential direct Thinking toggle, clicking...")
            await direct_toggle.click(force=True)
            await asyncio.sleep(1.2)
            
            verified = await page.evaluate('''() => {
                const composer = document.querySelector('form, [data-testid*="composer"]');
                const bodyText = document.body.innerText.toLowerCase();
                const composerText = composer ? composer.innerText.toLowerCase() : "";
                return bodyText.includes('think') || bodyText.includes('reason') || composerText.includes('think');
            }''')
            if verified:
                print("[SUCCESS] Thinking activated via direct toggle!")
                return True
            else:
                print("[DEBUG] Direct toggle didn't seem to work, falling back to menu.")

        # 2. Plus Menu Toggle (Matches user screenshot)
        for attempt in range(3):
            print(f"[DEBUG] Opening Plus menu for Thinking (attempt {attempt+1})...")
            
            plus_btn = await page.query_selector('button[data-testid="composer-plus-btn"]')
            if not plus_btn:
                 plus_btn = await page.query_selector('button[aria-label*="Add files"], button[aria-label*="Attach"], button:has(svg)')
            
            if plus_btn:
                await plus_btn.scroll_into_view_if_needed()
                await plus_btn.click(force=True)
                await asyncio.sleep(1.5) # Wait for menu to fully render
                
                # Scan EVERY potential menu item
                # Based on screenshot, these are likely in a list-like structure
                menu_items = await page.query_selector_all('[role="menuitem"], [role="option"], button, div, li')
                visible_thinking = None
                
                print("[DEBUG] Scanning menu for 'Thinking' option...")
                for item in menu_items:
                    try:
                        if not await item.is_visible(): continue
                        text = await item.inner_text()
                        if text and ("Thinking" in text or "Reasoning" in text):
                            print(f"[DEBUG] Found Thinking option in menu: '{text.strip()}'")
                            visible_thinking = item
                            break
                    except: continue
                
                if visible_thinking:
                    print("[DEBUG] Clicking Thinking option...")
                    # Sometimes a direct click on the item text's parent is more reliable
                    await visible_thinking.click(force=True)
                    await asyncio.sleep(1.5)
                    
                    verified = await page.evaluate('''() => {
                        const composer = document.querySelector('form, [data-testid*="composer"]');
                        const bodyText = document.body.innerText.toLowerCase();
                        const composerText = composer ? composer.innerText.toLowerCase() : "";
                        return bodyText.includes('think') || bodyText.includes('reason') || composerText.includes('think');
                    }''')
                    
                    if verified:
                        print("[SUCCESS] Thinking mode verified on page!")
                        return True
                    else:
                        print("[WARNING] Thinking clicked but indicator not detected. Retrying...")
                else:
                    print("[WARNING] 'Thinking' option not found in the opened menu.")
            
            await page.keyboard.press("Escape")
            await asyncio.sleep(0.5)

        print("[ERROR] Thinking mode activation failed. Proceeding without it.")
        return False
        
    except Exception as e:
        print(f"[ERROR] select_model Thinking error: {e}")
        return False



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
    parser.add_argument("--model", "-m", help="Model to use (default: auto)")
    parser.add_argument("--image", "-img", action="append", help="Path to image file to upload (can be used multiple times)", default=[])
    
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
            thinking_used = await select_model(page, args.model)
            
            # Raise error if thinking was requested but couldn't be activated
            if args.model and ("thinking" in args.model.lower() or "reason" in args.model.lower()):
                if not thinking_used:
                    raise Exception("Thinking mode requested but could not be activated. The toggle may not be visible or the ChatGPT UI may have changed.")
            
            response = await send_prompt(page, args.prompt, image_paths=args.image)
            print(f"\nTHINKING_USED={str(thinking_used).lower()}")
            print("RESULT_START")
            print(response)
            print("RESULT_END")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if context:
            await context.close()


if __name__ == "__main__":
    asyncio.run(main())
