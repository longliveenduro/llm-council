#!/usr/bin/env python3
"""
AI Studio Browser Automation Script

This script automates interactions with Google AI Studio using Playwright.
It can input prompts, send them, and extract responses from Gemini models.

Usage:
    First run (to log in):
       python ai_studio_automation.py --interactive
    
    Subsequent runs:
       python ai_studio_automation.py "Your prompt here"
       
    Interactive mode:
       python ai_studio_automation.py --interactive
"""

import asyncio
import argparse
import sys
import os
from pathlib import Path
from playwright.async_api import async_playwright, Page, BrowserContext

# Directory to store browser profile (keeps you logged in)
BROWSER_DATA_DIR = Path(__file__).parent / ".browser_data"


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
    
    # Navigate to AI Studio if not already there
    if "aistudio.google.com" not in page.url:
        await page.goto("https://aistudio.google.com/prompts/new_chat")
        try:
            await page.wait_for_load_state("networkidle", timeout=60000)
        except:
            print("Warning: Network idle timeout, proceeding potentially without full load.")
    
    return context, page


async def wait_for_chat_interface(page: Page, timeout: int = 30000):
    """Wait for the chat interface to be ready."""
    # Wait for the prompt input area to be available
    # AI Studio uses a contenteditable div or textarea
    selectors = [
        'textarea[aria-label*="prompt" i]',
        'textarea[placeholder*="type" i]',
        '[contenteditable="true"]',
        'textarea',
        '.prompt-input',
        '[data-placeholder*="message" i]',
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
    Send a prompt to AI Studio and wait for the response.
    
    Args:
        page: Playwright page object
        prompt: The prompt text to send
        input_selector: Optional specific selector for the input
        
    Returns:
        The response text from Gemini
    """
    
    # Find the input element if not specified
    if not input_selector:
        input_selector = await wait_for_chat_interface(page)
    
    # Click on the input to focus it
    await page.click(input_selector)
    await asyncio.sleep(0.3)
    
    # Clear any existing text and type the prompt
    # Clear any existing text
    await page.keyboard.press("Control+a")
    await page.keyboard.press("Backspace")

    try:
        # Use clipboard paste for speed (avoid timeout on long prompts)
        # Grant permissions first (context level)
        try:
             await page.context.grant_permissions(['clipboard-read', 'clipboard-write'])
        except:
             pass
        
        # Write to clipboard
        await page.evaluate("navigator.clipboard.writeText(arguments[0])", prompt)
        await asyncio.sleep(0.1)
        
        # Paste
        await page.keyboard.press("Control+v")
        
        # Fallback verification: if empty, try fill
        await asyncio.sleep(0.5)
        val = await page.input_value(input_selector)
        if len(val) < 10:
             print("Warning: Paste might have failed, trying fill fallback...")
             await page.fill(input_selector, prompt)

    except Exception as e:
        print(f"Paste failed ({e}), falling back to fill (instant)...")
        # Use fill instead of type to prevent timeouts on massive prompts
        await page.fill(input_selector, prompt)
    
    print(f"Typed prompt: {prompt[:50]}...")
    
    # Find and click the send/run button
    send_button_selectors = [
        'button[aria-label*="run" i]',
        'button[aria-label*="send" i]',
        'button[aria-label*="submit" i]',
        'button:has-text("Run")',
        'button:has-text("Send")',
        '[data-testid="send-button"]',
        'button[type="submit"]',
    ]
    
    send_button = None
    for selector in send_button_selectors:
        try:
            send_button = await page.wait_for_selector(selector, timeout=2000)
            if send_button and await send_button.is_visible():
                print(f"Found send button with selector: {selector}")
                break
        except:
            continue
    
    if not send_button:
        # Try pressing Enter as fallback
        print("No send button found, trying Enter key...")
        await page.keyboard.press("Enter")
    else:
        await send_button.click()
    
    print("Prompt sent, waiting for response...")
    
    # Wait for response to complete
    # Look for indicators that the model is still generating
    await asyncio.sleep(2)  # Initial wait for response to start
    
    # Wait for any loading/generating indicators to disappear
    loading_selectors = [
        '[aria-label*="loading" i]',
        '[aria-label*="generating" i]',
        '.loading',
        '[data-loading="true"]',
        'button[aria-label*="stop" i]',
    ]
    
    for selector in loading_selectors:
        try:
            # Wait for loading indicator to appear then disappear
            # Increased timeout to 10s to account for initial latency
            await page.wait_for_selector(selector, timeout=10000)
            await page.wait_for_selector(selector, state="hidden", timeout=120000)
            print("Response generation completed")
            break
        except:
            continue
    
    # Additional wait for response to fully render
    await asyncio.sleep(1)
    
    # Extract the response
    response = await extract_response(page)
    
    return response


async def extract_response(page: Page) -> str:
    """Extract the latest response from the chat."""
    
    # Wait a bit more for content to stabilize
    await asyncio.sleep(2)
    
    # Check for error toasts/snackbars first
    try:
        error_toast = await page.query_selector("mat-snack-bar-container, .mat-mdc-snack-bar-container")
        if error_toast:
            error_text = await error_toast.inner_text()
            print(f"DEBUG: Found error toast: {error_text}")
            return f"Error: {error_text}"
    except:
        pass
    
    # Check for in-chat error messages
    error_selectors = [
        '.error-message',
        'ms-chat-turn .error',
        'ms-chat-turn:last-of-type .error',
        '.mat-error',
        '.error-text',
        'ms-chat-turn:last-of-type span[class*="error"]'
    ]
    
    for selectors in error_selectors:
         try:
            elements = await page.query_selector_all(selectors)
            if elements:
                error_text = await elements[-1].inner_text()
                print(f"DEBUG: Found in-chat error: {error_text}")
                return f"Error: {error_text}"
         except:
             pass

    # Try Clipboard Extraction first (High Fidelity for formatted text)
    try:
        # Grant permissions if possible
        try:
            await context.grant_permissions(['clipboard-read', 'clipboard-write'])
        except:
             pass

        turn_selector = 'ms-chat-turn:last-of-type'
        turn = await page.query_selector(turn_selector)
        
        if turn:
            # Hover to potentially reveal buttons
            await turn.hover()
            
            # 1. Try direct copy button
            copy_btn = await turn.query_selector('button[aria-label*="copy" i]')
            
            # 2. Try 'more_vert' menu if direct button missing
            if not copy_btn:
                menu_btn = await turn.query_selector('button[aria-label="Open options"]')
                if menu_btn:
                    await menu_btn.click()
                    # Wait/Find menu
                    try:
                        await page.wait_for_selector('div[role="menu"]', timeout=2000)
                        menu_items = await page.query_selector_all('div[role="menu"] button')
                        for item in menu_items:
                            txt = await item.text_content()
                            if "copy" in txt.lower():
                                copy_btn = item
                                break
                    except:
                        pass
            
            if copy_btn:
                await copy_btn.click()
                # Short wait for clipboard write
                await asyncio.sleep(0.5)
                clipboard_text = await page.evaluate("navigator.clipboard.readText()")
                if clipboard_text and len(clipboard_text) > 5:
                    print("DEBUG: Extracted response via Clipboard")
                    return clipboard_text

    except Exception as e:
        print(f"DEBUG: Clipboard extraction failed: {e}")

    # Fallback to AI Studio specific selectors based on HTML analysis
    print("DEBUG: Falling back to visual extraction...")
    response_selectors = [
        # Precise selector for the text content (ignoring thoughts)
        'ms-chat-turn:last-of-type ms-text-chunk',
        'ms-chat-turn:last-of-type .model-prompt-container ms-text-chunk', 
        '.model-prompt-container ms-text-chunk',
        
        # Fallbacks
        '[data-message-author="model"] ms-text-chunk',
        '.model-turn ms-text-chunk',
        'ms-text-chunk',
    ]
    
    print("DEBUG: Attempting to extract response...")
    
    for selector in response_selectors:
        try:
            elements = await page.query_selector_all(selector)
            if elements:
                # Get the last (most recent) response
                last_element = elements[-1]
                text = await last_element.inner_text()
                text = text.strip()
                
                print(f"DEBUG: Found candidate with selector '{selector}': '{text[:50]}...'")
                
                # Filter out obvious UI noise
                if text and not text.startswith(('thumb_', 'more_vert', 'edit', 'menu')):
                    return text
        except Exception as e:
            print(f"DEBUG: Error with selector {selector}: {e}")
            continue
    
    # Broader fallback: Look for ANY text content in the main area
    try:
        # Get all text blocks on the page
        all_paragraphs = await page.query_selector_all('p, .text-content, [class*="content"], div')
        texts = []
        for p in all_paragraphs:
            text = await p.inner_text()
            text = text.strip()
            # Heuristic: keep non-empty lines that don't look like button labels
            if text and len(text) > 1 and not text in ['Run', 'Cancel', 'Stop', 'Edit']:
                texts.append(text)
        
        if texts:
            # Print the last few chunks to help debug
            print("DEBUG: Fallback text chunks found:", texts[-5:])
            # Return the last chunk that looks like a real response (heuristic)
            return texts[-1]
    except Exception as e:
        print(f"DEBUG: Error in fallback: {e}")
    
    return "Could not extract response. Check 'aistudio_debug.html'"


async def select_model(page: Page, model_name: str):
    """
    Selects the specified model from the dropdown.
    """
    print(f"DEBUG: Attempting to select model: {model_name}")
    
    # Map friendly names to partial IDs
    # IDs based on HTML analysis
    model_map = {
        "Gemini 3 Flash": "gemini-3-flash-preview",
        "Gemini 3 Pro": "gemini-3-pro-preview",
        "Gemini 2.5 Flash": "gemini-flash-latest",
        "Gemini 2.5 Flash-Lite": "gemini-flash-lite-latest",
        "Imagen 3": "imagen-3", # Guessing/Placeholder
    }
    
    target_id_suffix = model_map.get(model_name)
    
    try:
        # 1. Open the model selector
        selector_btn = "ms-model-selector button"
        # Wait a bit for page to be fully interactive
        await asyncio.sleep(1)
        
        await page.wait_for_selector(selector_btn)
        # Check if model is already selected (optimization)
        # The button text usually contains the model name
        current_model_el = await page.query_selector(selector_btn)
        current_text = await current_model_el.inner_text()
        if model_name in current_text:
            print(f"DEBUG: Model '{model_name}' is already selected.")
            return

        print("DEBUG: Opening model selector dropdown...")
        await page.click(selector_btn)
        
        # 2. Wait for carousel to appear
        # The carousel has tag <ms-model-carousel>
        await page.wait_for_selector("ms-model-carousel", state="visible")
        
        # 3. Find the right model
        if target_id_suffix:
            # Construct ID selector: [id*='gemini-3-flash-preview']
            full_id_selector = f"[id*='{target_id_suffix}']"
            print(f"DEBUG: Clicking model with selector {full_id_selector}")
            await page.wait_for_selector(full_id_selector)
            await page.click(full_id_selector)
        else:
            # Text based fallback
            print(f"DEBUG: Clicking model by text: {model_name}")
            await page.click(f"text={model_name}")
            
        # 4. Wait for dropdown to close
        await asyncio.sleep(1)
        print(f"DEBUG: Selected model {model_name}")
        
    except Exception as e:
        print(f"ERROR: Failed to select model {model_name}: {e}")


async def interactive_mode(page: Page):
    """Run in interactive mode, accepting prompts from stdin."""
    print("\n=== AI Studio Interactive Mode ===")
    print("Enter prompts to send to Gemini. Type 'quit' to exit.\n")
    
    input_selector = await wait_for_chat_interface(page)
    
    while True:
        try:
            prompt = input("\nYou: ").strip()
            if prompt.lower() in ['quit', 'exit', 'q']:
                print("Goodbye!")
                break
            
            if not prompt:
                continue
            
            response = await send_prompt(page, prompt, input_selector)
            print(f"\nGemini: {response}")
            
        except KeyboardInterrupt:
            print("\n\nInterrupted. Goodbye!")
            break
        except Exception as e:
            print(f"\nError: {e}")


async def main():
    parser = argparse.ArgumentParser(description="Automate Google AI Studio")
    parser.add_argument("prompt", nargs="?", help="The prompt to send")
    parser.add_argument("--interactive", "-i", action="store_true", 
                        help="Run in interactive mode")
    parser.add_argument("--model", "-m", default="Gemini 3 Flash",
                        help="Model to use (default: Gemini 3 Flash)")
    
    args = parser.parse_args()
    
    if not args.prompt and not args.interactive:
        parser.print_help()
        print("\nError: Please provide a prompt or use --interactive mode")
        sys.exit(1)
    
    context = None
    try:
        print("Launching browser...")
        print("(First run: Log in to Google when prompted. Your login will be saved.)")
        context, page = await get_browser_context()
        
        print(f"Ready! Current page: {page.url}")
        
        # Check if we need to log in
        if "accounts.google.com" in page.url:
            print("\n>>> Please log in to your Google account in the browser <<<")
            print(">>> Press Enter here once you're logged in and on AI Studio <<<")
            input()
            # Navigate to AI Studio after login
            await page.goto("https://aistudio.google.com/prompts/new_chat")
            await page.wait_for_load_state("networkidle")
        
        # Select the requested model
        if args.model:
            await select_model(page, args.model)

        if args.interactive:
            await interactive_mode(page)
        else:
            response = await send_prompt(page, args.prompt)
            print(f"\nResponse:\n{response}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        if context:
            await context.close()


if __name__ == "__main__":
    asyncio.run(main())

