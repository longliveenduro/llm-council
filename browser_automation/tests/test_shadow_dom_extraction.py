
import pytest
from pathlib import Path
from playwright.sync_api import sync_playwright
from browser_automation.ai_studio_automation import AI_STUDIO_JS

# Read local Turndown lib
TURNDOWN_LIB = (Path(__file__).parent.parent / "turndown.min.js").read_text()

@pytest.fixture(scope="module")
def browser_page():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.evaluate(TURNDOWN_LIB + "; window.TurndownService = TurndownService;")
        yield page
        browser.close()

def test_shadow_dom_extraction(browser_page):
    # Create a structure that mimics AI Studio with Shadow DOM
    # ms-chat-turn -> shadowRoot -> ms-message-content -> shadowRoot -> ms-markdown-block -> Content
    
    html_setup = """
    document.body.innerHTML = '';
    const turn = document.createElement('ms-chat-turn');
    document.body.appendChild(turn);
    
    const shadow1 = turn.attachShadow({mode: 'open'});
    const content = document.createElement('ms-message-content');
    shadow1.appendChild(content);
    
    const shadow2 = content.attachShadow({mode: 'open'});
    const block = document.createElement('ms-markdown-block');
    block.innerHTML = '<h1>Hello World</h1><p>This is <strong>bold</strong>.</p>';
    shadow2.appendChild(block);
    """
    
    browser_page.evaluate(html_setup)
    result = browser_page.evaluate(AI_STUDIO_JS)
    
    print(f"Extraction Result: {result}")
    
    assert "# Hello World" in result
    assert "**bold**" in result

def test_shadow_dom_extraction_fallback(browser_page):
    # Test fallback to ms-text-chunk if ms-markdown-block is missing
    html_setup = """
    document.body.innerHTML = '';
    const turn = document.createElement('ms-chat-turn');
    document.body.appendChild(turn);
    
    const shadow1 = turn.attachShadow({mode: 'open'});
    // ms-text-chunk inside shadow
    const chunk = document.createElement('ms-text-chunk');
    chunk.innerHTML = '<h1>Fallback Content</h1><p>Text</p>';
    shadow1.appendChild(chunk);
    """
    
    browser_page.evaluate(html_setup)
    
    # Run extraction
    result = browser_page.evaluate(AI_STUDIO_JS)
    
    print(f"Fallback Result: {result}")
    
    # Verify
    assert "# Fallback Content" in result
    assert "Text" in result
