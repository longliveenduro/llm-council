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
import json

# Directory to store browser profile (keeps you logged in)
BROWSER_DATA_DIR = Path(__file__).parent / ".claude_browser_data"

# Turndown JS Library Content (Loaded locally to bypass CSP)
TURNDOWN_LIB_PATH = Path(__file__).parent / "turndown.min.js"
TURNDOWN_LIB = TURNDOWN_LIB_PATH.read_text()

# Combined JS script for extraction (uses Turndown for proper markdown)
CLAUDE_JS = r'''
(() => {
    // Find potential message containers
    const candidates = Array.from(document.querySelectorAll('.font-claude-message, .font-claude-response'));
    if (candidates.length === 0) return null;
    
    // Filter to keep only top-level containers
    const topLevelMessages = candidates.filter(el => 
        !el.parentElement.closest('.font-claude-message, .font-claude-response')
    );
    
    if (topLevelMessages.length === 0) return null;
    
    const lastMessage = topLevelMessages[topLevelMessages.length - 1];
    
    // Clone to avoid side effects
    const clone = lastMessage.cloneNode(true);

    // 1. Process Math Elements - convert to LaTeX syntax before Turndown
    // Claude uses KaTeX. LaTeX source is usually in <annotation encoding="application/x-tex">
    const mathElements = clone.querySelectorAll('.katex, .math, .math-inline, .math-display');
    mathElements.forEach(el => {
        const annotation = el.querySelector('annotation[encoding="application/x-tex"]');
        if (annotation) {
            const latex = annotation.textContent;
            const isBlock = el.classList.contains('math-display') || el.closest('.math-display');
            // Use HTML elements that Turndown will preserve
            el.innerHTML = isBlock ? `<pre>$$\n${latex}\n$$</pre>` : `<code>$${latex}$</code>`;
        }
    });

    // 2. Remove thinking sections before conversion
    const thinkingSelectors = [
        'details',
        '[class*="thinking"]',
        '[class*="Thinking"]',
        '[data-testid*="thinking"]',
        'summary',
        '.border-border-300.rounded-lg',
    ];
    
    for (const selector of thinkingSelectors) {
        const elements = clone.querySelectorAll(selector);
        elements.forEach(el => el.remove());
    }

    clone.style.position = 'absolute';
    clone.style.left = '-9999px';
    clone.style.whiteSpace = 'pre-wrap';
    document.body.appendChild(clone);

    // 3. Use Turndown to convert HTML to Markdown
    let resultText = null;
    
    try {
        // Strategy 1: Look for the standard markdown container
        const allMarkdown = clone.querySelectorAll('.standard-markdown');
        let targetEl = null;
        
        if (allMarkdown.length > 0) {
            targetEl = allMarkdown[allMarkdown.length - 1];
        } else {
            targetEl = clone.querySelector('.prose') || clone;
        }
        
        if (typeof TurndownService !== 'undefined') {
            const turndownService = new TurndownService({
                headingStyle: 'atx',
                codeBlockStyle: 'fenced',
                bulletListMarker: '-',
                emDelimiter: '*',
                strongDelimiter: '**'
            });
            resultText = turndownService.turndown(targetEl.innerHTML).trim();
        } else {
            // Fallback to innerText if Turndown not loaded
            resultText = targetEl.innerText.trim();
        }
    } catch (e) {
        // Fallback on error
        const prose = clone.querySelector('.prose');
        resultText = prose ? prose.innerText.trim() : clone.innerText.trim();
    }
    
    return resultText;
})()
'''


def print_json_output(response=None, error_msgs=None, error=False, error_type=None):
    """Print structured JSON output for the backend to parse."""
    output = {
        "response": response,
        "error_msgs": error_msgs,
        "error": error,
        "error_type": error_type
    }
    print(f"\nJSON_OUTPUT: {json.dumps(output)}")


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

    # Check for broken conversation state (e.g. Conversation not found)
    try:
        # Check specific error toasts or messages
        # We check for text content that indicates a dead end
        content = await page.content()
        if "Conversation not found" in content or "Page not found" in content:
            print("Detected error page/broken conversation. Redirecting to home...")
            await page.goto("https://claude.ai/")
            await asyncio.sleep(2)
            
            if await detect_captcha(page):
                await wait_for_user_intervention(page)
    except Exception as e:
        print(f"Error checking for error page: {e}")

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


async def send_prompt(page: Page, prompt: str, input_selector: str = None, model: str = "auto", image_paths: list = None) -> str:
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
    
    # Note: Extended Thinking is now handled in main() before calling send_prompt
    
    # Handle image uploads
    if image_paths:
        print(f"[DEBUG] Processing {len(image_paths)} images for Claude...")
        attached_direct = False
        # 1. Try direct upload via hidden input first
        try:
            file_input = await page.query_selector('input[type="file"]')
            if file_input:
                print("[DEBUG] Found hidden file input in Claude, setting all files...")
                await file_input.set_input_files(image_paths)
                # Wait for any thumbnail
                # Wait for any thumbnail
                # Enhanced selectors for robustness
                thumbnail_selectors = [
                    'div[data-testid="attachment-thumbnail"]',
                    'div[class*="AttachmentThumbnail"]',
                    '.AttachmentThumbnail',
                    'img[alt*="upload"]', 
                    'button[aria-label="Remove attachment"]',
                    'div.relative img:not([alt="User"])', # Generic image in relative container
                    'div.flex.gap-2 img',
                ]
                combined_selector = ", ".join(thumbnail_selectors)
                await page.wait_for_selector(combined_selector, timeout=10000)
                print("[DEBUG] Images attached via hidden input in Claude.")
                attached_direct = True
            else:
                print("[DEBUG] No hidden file input found initially in Claude.")
        except Exception as e:
            print(f"[DEBUG] Direct upload attempt in Claude failed: {e}")

        # 2. Sequential fallback (only if direct didn't work and no images visible)
        if not attached_direct:
            # Double check: did the direct upload work but just timed out on the specific selector?
            # Or maybe it appeared now?
            try:
                # Same broad selectors
                thumbnail_selectors = [
                    'div[data-testid="attachment-thumbnail"]',
                    'div[class*="AttachmentThumbnail"]',
                    '.AttachmentThumbnail',
                    'img[alt*="upload"]', 
                    'button[aria-label="Remove attachment"]',
                    'div.relative img:not([alt="User"])',
                    'div.flex.gap-2 img',
                ]
                combined_selector = ", ".join(thumbnail_selectors)
                elements = await page.query_selector_all(combined_selector)
                if elements and len(elements) > 0:
                     print(f"[DEBUG] Found {len(elements)} existing attachments, assuming direct upload worked.")
                     attached_direct = True
            except:
                pass
                
        if not attached_direct:
            for image_path in image_paths:
                if not image_path: continue
                
                print(f"Uploading image to Claude: {image_path}")
                try:
                    # Check directly for input[type=file] again inside loop if needed
                    file_input = await page.query_selector('input[type="file"]')
                    if file_input:
                        await file_input.set_input_files(image_path)
                        print("[DEBUG] Image set via hidden file input.")
                    else:
                        # Try to open menu
                        attach_btn = await page.wait_for_selector('button[aria-label="Attach files"], button[data-testid="attach-button"], button:has(svg[data-icon="paperclip"])', timeout=3000)
                        if attach_btn:
                            async with page.expect_file_chooser() as fc_info:
                                await attach_btn.click()
                            file_chooser = await fc_info.value
                            await file_chooser.set_files(image_path)
                            print("[DEBUG] Image set via attach button.")
                        else:
                            print("[ERROR] Attach button not found.")
                         
                    # Wait for upload (thumbnail)
                    await page.wait_for_selector('div[data-testid="attachment-thumbnail"], div[class*="AttachmentThumbnail"]', timeout=30000)
                    print(f"Image {image_path} uploaded successfully to Claude.")
                except Exception as e:
                    print(f"[ERROR] Error uploading image {image_path}: {e}")
                    try:
                        html = await page.content()
                        with open("claude_dump.html", "w") as f:
                            f.write(html)
                        print("Dumped HTML to claude_dump.html")
                    except:
                        pass

    # Click on the input to focus it
    await page.click(input_selector, timeout=10000)
    await asyncio.sleep(0.1)
    
    # Clear and fill
    # Ensure focus
    try:
        await page.click(input_selector)
        await asyncio.sleep(0.5)
        await page.focus(input_selector)
    except Exception as e:
        print(f"DEBUG: Focus failed: {e}")

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
    """Extract the latest response from the chat, excluding thinking sections."""
    
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
    
    # Inject Turndown library for HTML-to-Markdown conversion
    try:
        turndown_loaded = await page.evaluate("typeof TurndownService !== 'undefined'")
        if not turndown_loaded:
            # Use evaluate to inject the code (bypassing CSP script-src 'self')
            await page.evaluate(TURNDOWN_LIB + "; window.TurndownService = TurndownService;")
            await page.wait_for_function("typeof TurndownService !== 'undefined'", timeout=5000)
            print("DEBUG: Turndown library injected successfully via evaluate")
    except Exception as e:
        print(f"DEBUG: Failed to inject Turndown (will use fallback): {e}")

    # Use JavaScript to extract text while excluding thinking sections
    # Claude's Extended Thinking is typically in a <details> element or similar collapsible container
    try:
        text = await page.evaluate(CLAUDE_JS)
        
        if text and len(text.strip()) > 30:
            if "New chat" not in text[:50] and "Chats" not in text[:50]:
                print("SUCCESS: Extracted response using JS with thinking/math handling")
                return clean_claude_text(text, prompt, model)
    except Exception as e:
        print(f"DEBUG: JS extraction with thinking/math handling failed: {e}")

    
    # Fallback: Use original selector-based approach
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
        "Sonnet 4.6",
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
        "PASTED",
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
                "This is one of the", "This is a fundamental", "The question of",
                "This is an interesting", "I need to evaluate", "I need to analyze",
                "Let me analyze", "Let me evaluate", "I'm being asked",
            ]
            
            # Check for specific preamble patterns
            preamble_patterns = [
                r"The user prompt is empty",
                r"Based on the thinking block",
                r"Here is a summary",
                r"Let me think about how to approach",
                r"I should:",
                r"I'm being asked to act as",
                r"Three responses \(A, B, C\)",
                r"I need to evaluate.*responses",
                r"Let me analyze.*carefully",
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


async def select_thinking_mode(page: Page, wants_thinking: bool = True) -> bool:
    """
    Find and click the "stop clock" symbol to toggle Extended Thinking.
    Returns True if thinking mode is confirmed active, False otherwise.
    """
    print(f"Setting Extended Thinking to: {wants_thinking}")
    
    # Selectors for the "stop clock" / "timer" button or the "Extended Thinking" toggle
    # Updated based on recent Claude UI changes
    thinking_button_selectors = [
        'button[aria-label*="Verify your humanity"]', # Sometimes this is confused but unlikely
        'button:has-text("Extended Thinking")',
        'button[aria-label="Enable Extended Thinking"]',
        'button[aria-label="Disable Extended Thinking"]',
        'button:has(svg)', # Too broad?
        'button[class*="thinking"]',
    ]
    
    # Specific targeted approach:
    # The toggle is often inside the model selector or near the input
    # Recent UI: It's a toggle switch or a "clock" icon button near the file attach button
    
    potential_toggles = [
         # The 'thinking' toggle is now often integrated into the model selector or a separate button
         'button[data-testid="thinking-toggle"]',
         '.thinking-toggle',
         '[aria-label*="thinking"]',
         'button:has(svg[data-icon="clock"])',
         'div[role="switch"]', # Sometimes it's a switch
         'input[type="checkbox"][name*="thinking"]',
    ]
    
    # First, wait for chat interface to ensure elements are loaded
    try:
        await wait_for_chat_interface(page, timeout=15000)
    except Exception as e:
        print(f"Warning: wait_for_chat_interface failed in select_thinking_mode: {e}")

    print("DEBUG: Searching for Extended Thinking toggle...")

    # First, try to see if it's already on/off by text on page
    is_active_by_text = False
    try:
        # "Extended thinking is on" usually appears when active
        if await page.query_selector('text="Extended thinking is on"'):
            is_active_by_text = True
    except:
        pass
        
    if is_active_by_text == wants_thinking:
        print(f"DEBUG: Thinking state already matches desire ({wants_thinking}) according to page text.")
        return True

    # Helper to check and click a toggle
    async def check_and_click_toggle(element):
        target_to_click = element
        state_element = element
        
        # If it's a label, find the input inside
        tag_name = await element.evaluate("el => el.tagName.toLowerCase()")
        if tag_name == 'label':
             input_el = await element.query_selector('input')
             if input_el:
                 state_element = input_el
        
        # If it's an input but invisible (sr-only), try to find parent label to click
        if tag_name == 'input' and not await element.is_visible():
             # Check if it has a parent label
             parent = await element.evaluate_handle('el => el.closest("label")')
             if parent:
                 target_to_click = parent
                 state_element = element
             else:
                 return False # Can't click invisible input with no label
        elif not await target_to_click.is_visible():
             return False

        # Determine current state
        is_currently_on = False
        
        # Method 1: Playwright is_checked() (works for checkbox/radio)
        try:
             is_currently_on = await state_element.is_checked()
        except:
             # Method 2: Attributes
             checked = await state_element.get_attribute("checked") # returns string if present, None if not
             aria_checked = await state_element.get_attribute("aria-checked")
             aria_pressed = await state_element.get_attribute("aria-pressed")
             
             is_currently_on = (
                 checked is not None or 
                 aria_checked == "true" or 
                 aria_pressed == "true"
             )
        
        if is_currently_on != wants_thinking:
            print(f"DEBUG: Clicking thinking toggle (current: {is_currently_on})")
            try:
                # Ensure we click the interactive element
                await target_to_click.click(force=True) 
                await asyncio.sleep(1)
                
                # Verify change?
                # Sometimes checking again is good practice
                return True
            except Exception as e:
                print(f"DEBUG: Click failed: {e}")
                return False
        else:
            print(f"DEBUG: Toggle already in correct state ({is_currently_on})")
            return True # Found and correct

    # Strategy 1: Look for the toggle directly (Top level)
    for selector in potential_toggles:
        try:
            elements = await page.query_selector_all(selector)
            for el in elements:
                if await check_and_click_toggle(el):
                    return True
        except:
            continue

    # Strategy 2: Look inside the model selector menu
    # The toggle might be hidden inside the model picker dropdown
    print("DEBUG: Toggle not found at top level. Checking inside model selector menu...")
    
    model_selector_candidates = [
        'button[data-testid="model-selector-dropdown"]',
        'button[aria-label="Model selector"]',
        'div[data-testid="model-selector-dropdown"]',
        # Fallback to finding the button that contains the current model name
        'button:has-text("Sonnet")',
        'button:has-text("Opus")',
        'button:has-text("Haiku")',
        'button:has-text("Claude")',
    ]

    menu_opened = False
    
    for selector in model_selector_candidates:
        try:
            # We want the one that is visible
            els = await page.query_selector_all(selector)
            for el in els:
                if await el.is_visible():
                    print(f"DEBUG: Found likely model selector: {selector}")
                    await el.click()
                    menu_opened = True
                    await asyncio.sleep(1) # Wait for animation
                    break
            if menu_opened:
                break
        except:
            continue
            
    if menu_opened:
        # Now look for the toggle inside the menu
        menu_toggle_selectors = [
            'label:has(input[role="switch"])', # Label wrapping the switch
            'label:has(input[type="checkbox"])', 
            'div[role="switch"]',
            'button[role="switch"]',
            'input[type="checkbox"][role="switch"]', 
            '.thinking-toggle',
            # Fallback text search nearby?
        ]
        
        found_in_menu = False
        for selector in menu_toggle_selectors:
            try:
                elements = await page.query_selector_all(selector)
                for el in elements:
                     if await check_and_click_toggle(el):
                         found_in_menu = True
                         break
                if found_in_menu:
                    break
            except:
                continue
        
        # Close the menu by clicking the model selector again or body
        # Try clicking escape first
        try:
             await page.keyboard.press("Escape")
        except:
             pass
        await asyncio.sleep(0.5)
        
        if found_in_menu:
            print("DEBUG: Successfully toggled thinking in model menu.")
            return True

    print("Warning: Could not definitively find Extended Thinking toggle. detailed debug info below:")
    # Dump HTML of input area for debugging
    try:
        input_area = await page.query_selector('[contenteditable="true"]')
        if input_area:
            input_parent = await input_area.evaluate_handle('el => el.parentElement.parentElement')
            print(await input_parent.evaluate('el => el.outerHTML'))
    except:
        pass
        
    return False


async def run_login_mode():
    """Run in login mode: launch browser, wait for login."""
    print("Launching Claude for login...")
    context, page = await get_browser_context()
    
    print(f"Browser launched. Page: {page.url}")
    print("Please log in checking the browser window...")
    
    # Wait for login to complete
    max_wait = 300 # 5 minutes
    elapsed = 0
    logged_in = False
    
    while elapsed < max_wait:
        if page.is_closed():
            print("Browser closed by user.")
            sys.exit(1)
            
        is_login_modal = await check_login_required(page)
        
        try:
             # Check for chat input as positive signal
            await page.wait_for_selector('[contenteditable="true"], div[aria-label*="prompt"]', timeout=2000)
            chat_input_visible = True
        except:
            chat_input_visible = False
            
        if not is_login_modal and chat_input_visible:
            print("Login detected!")
            logged_in = True
            break
            
        await asyncio.sleep(2)
        elapsed += 2
        
    if logged_in:
        print("Successfully logged in.")
        print("\nLogin complete. You can close the browser or wait for timeout.")
        await asyncio.sleep(5)
    else:
        print("Login timed out.")
        sys.exit(1)


async def main():
    parser = argparse.ArgumentParser(description="Automate Claude")
    parser.add_argument("prompt", nargs="?", help="The prompt to send")
    parser.add_argument("--interactive", "-i", action="store_true", 
                        help="Run in interactive mode")
    parser.add_argument("--login", action="store_true", help="Run in login mode")
    parser.add_argument("--model", "-m", help="Model to use (default: auto)")
    parser.add_argument("--image", "-img", action="append", help="Path to image file to upload (can be used multiple times)", default=[])
    
    args = parser.parse_args()
    
    if args.login:
        await run_login_mode()
        return

    if not args.prompt and not args.interactive:
        parser.print_help()
        print("\nError: Please provide a prompt or use --interactive mode")
        sys.exit(1)
        
    context = None
    try:
        print("Launching browser...")
        context, page = await get_browser_context()
        
        print(f"Ready! Current page: {page.url}")
        
        if args.interactive:
            # Check if interactive_mode exists, otherwise warn
            if 'interactive_mode' in globals():
                await interactive_mode(page)
            else:
                 print("Interactive mode not implemented in this script.")
        else:
            # Track if thinking mode was requested and enabled
            thinking_used = False
            if args.model and "thinking" in args.model.lower():
                thinking_used = await select_thinking_mode(page, wants_thinking=True)
                if not thinking_used:
                    raise Exception("Extended Thinking requested but could not be activated. The toggle may not be visible or the Claude UI may have changed.")
            
            response = await send_prompt(page, args.prompt, model=args.model, image_paths=args.image)
            
            # Print legacy markers for safety
            print("RESULT_START")
            print(response)
            print("RESULT_END")
            
            # Print new structured JSON
            print_json_output(response=response, error=False)
            
    except Exception as e:
        error_str = str(e)
        error_type = "generic_error"
        
        if "extended thinking requested but could not be activated" in error_str.lower():
            error_type = "thinking_not_activated"
        elif "login required" in error_str.lower():
            error_type = "login_required"
        elif "timeout" in error_str.lower():
            error_type = "timeout"
        elif "captcha" in error_str.lower():
            error_type = "site_unavailable"
            
        print(f"Error: {e}")
        print_json_output(error_msgs=error_str, error=True, error_type=error_type)
    finally:
        if context:
            await context.close()


if __name__ == "__main__":
    asyncio.run(main())
