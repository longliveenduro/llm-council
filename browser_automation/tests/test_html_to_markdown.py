"""
Tests for HTML to Markdown conversion in browser automation scripts.

These tests verify that the Turndown library integration correctly converts
HTML-formatted LLM responses to proper Markdown syntax.
"""

import pytest
from pathlib import Path
from playwright.sync_api import sync_playwright


# Read the local Turndown library
TURNDOWN_PATH = Path(__file__).parent.parent / "turndown.min.js"
TURNDOWN_LIB = TURNDOWN_PATH.read_text()

# JavaScript that creates a configured Turndown instance and converts HTML
TURNDOWN_CONVERT_JS = """
(html) => {
    const turndownService = new TurndownService({
        headingStyle: 'atx',
        codeBlockStyle: 'fenced',
        bulletListMarker: '-',
        emDelimiter: '*',
        strongDelimiter: '**'
    });
    return turndownService.turndown(html);
}
"""


@pytest.fixture(scope="module")
def browser_page():
    """Create a browser page with Turndown loaded for testing."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        # Load a minimal page
        page.set_content("<html><body></body></html>")
        
        # Inject Turndown via evaluate to simulate CSP bypass
        # We append an assignment to window to ensure global availability
        page.evaluate(TURNDOWN_LIB + "; window.TurndownService = TurndownService;")
        
        page.wait_for_function("typeof TurndownService !== 'undefined'", timeout=10000)
        yield page
        browser.close()


class TestHeadingConversion:
    """Test that HTML headings convert to Markdown headings."""
    
    def test_h1_converts_to_hash(self, browser_page):
        html = "<h1>Main Title</h1>"
        result = browser_page.evaluate(TURNDOWN_CONVERT_JS, html)
        assert result.strip() == "# Main Title"
    
    def test_h2_converts_to_double_hash(self, browser_page):
        html = "<h2>Subtitle</h2>"
        result = browser_page.evaluate(TURNDOWN_CONVERT_JS, html)
        assert result.strip() == "## Subtitle"
    
    def test_h3_converts_to_triple_hash(self, browser_page):
        html = "<h3>Section</h3>"
        result = browser_page.evaluate(TURNDOWN_CONVERT_JS, html)
        assert result.strip() == "### Section"
    
    def test_multiple_headings(self, browser_page):
        html = "<h1>Title</h1><h2>Subtitle</h2><p>Content</p>"
        result = browser_page.evaluate(TURNDOWN_CONVERT_JS, html)
        assert "# Title" in result
        assert "## Subtitle" in result
        assert "Content" in result


class TestBoldItalicConversion:
    """Test that bold and italic HTML converts to Markdown."""
    
    def test_strong_converts_to_double_asterisk(self, browser_page):
        html = "<p>This is <strong>bold text</strong> here.</p>"
        result = browser_page.evaluate(TURNDOWN_CONVERT_JS, html)
        assert "**bold text**" in result
    
    def test_b_converts_to_double_asterisk(self, browser_page):
        html = "<p>This is <b>bold text</b> here.</p>"
        result = browser_page.evaluate(TURNDOWN_CONVERT_JS, html)
        assert "**bold text**" in result
    
    def test_em_converts_to_single_asterisk(self, browser_page):
        html = "<p>This is <em>italic text</em> here.</p>"
        result = browser_page.evaluate(TURNDOWN_CONVERT_JS, html)
        assert "*italic text*" in result
    
    def test_i_converts_to_single_asterisk(self, browser_page):
        html = "<p>This is <i>italic text</i> here.</p>"
        result = browser_page.evaluate(TURNDOWN_CONVERT_JS, html)
        assert "*italic text*" in result
    
    def test_nested_bold_italic(self, browser_page):
        html = "<p>This is <strong><em>bold italic</em></strong> text.</p>"
        result = browser_page.evaluate(TURNDOWN_CONVERT_JS, html)
        # Should contain both markers
        assert "***bold italic***" in result or "**_bold italic_**" in result or "*bold italic*" in result


class TestListConversion:
    """Test that HTML lists convert to Markdown lists."""
    
    def test_unordered_list(self, browser_page):
        html = "<ul><li>Item One</li><li>Item Two</li><li>Item Three</li></ul>"
        result = browser_page.evaluate(TURNDOWN_CONVERT_JS, html)
        # Turndown may add extra spaces for alignment
        assert "-   Item One" in result or "- Item One" in result
        assert "-   Item Two" in result or "- Item Two" in result
        assert "-   Item Three" in result or "- Item Three" in result
    
    def test_ordered_list(self, browser_page):
        html = "<ol><li>First</li><li>Second</li><li>Third</li></ol>"
        result = browser_page.evaluate(TURNDOWN_CONVERT_JS, html)
        assert "1. First" in result or "1.  First" in result
        assert "2. Second" in result or "2.  Second" in result
        assert "3. Third" in result or "3.  Third" in result
    
    def test_nested_list(self, browser_page):
        html = "<ul><li>Parent<ul><li>Child</li></ul></li></ul>"
        result = browser_page.evaluate(TURNDOWN_CONVERT_JS, html)
        assert "Parent" in result
        assert "Child" in result


class TestCodeBlockConversion:
    """Test that code blocks convert to fenced code blocks."""
    
    def test_inline_code(self, browser_page):
        html = "<p>Use the <code>print()</code> function.</p>"
        result = browser_page.evaluate(TURNDOWN_CONVERT_JS, html)
        assert "`print()`" in result
    
    def test_code_block(self, browser_page):
        html = "<pre><code>def hello():\n    print('Hello')</code></pre>"
        result = browser_page.evaluate(TURNDOWN_CONVERT_JS, html)
        assert "```" in result
        assert "def hello():" in result
        assert "print('Hello')" in result


class TestLinkConversion:
    """Test that HTML links convert to Markdown links."""
    
    def test_simple_link(self, browser_page):
        html = '<p>Visit <a href="https://example.com">Example</a> for more.</p>'
        result = browser_page.evaluate(TURNDOWN_CONVERT_JS, html)
        assert "[Example](https://example.com)" in result
    
    def test_link_with_title(self, browser_page):
        html = '<p><a href="https://example.com" title="Example Site">Link</a></p>'
        result = browser_page.evaluate(TURNDOWN_CONVERT_JS, html)
        assert "[Link](https://example.com" in result


class TestMixedContent:
    """Test conversion of complex HTML with multiple element types."""
    
    def test_realistic_llm_response(self, browser_page):
        html = """
        <div>
            <h1>Understanding Consciousness</h1>
            <p>Consciousness is a <strong>complex phenomenon</strong> that philosophers and scientists have debated for centuries.</p>
            <h2>Key Aspects</h2>
            <ul>
                <li><strong>Subjective Experience</strong> - What it feels like to be aware</li>
                <li><em>Qualia</em> - The individual instances of subjective experience</li>
            </ul>
            <h2>Example Code</h2>
            <pre><code>def think():
    return "I think, therefore I am"</code></pre>
            <p>For more information, visit <a href="https://plato.stanford.edu">Stanford Encyclopedia</a>.</p>
        </div>
        """
        result = browser_page.evaluate(TURNDOWN_CONVERT_JS, html)
        
        # Check headings
        assert "# Understanding Consciousness" in result
        assert "## Key Aspects" in result
        assert "## Example Code" in result
        
        # Check bold/italic
        assert "**complex phenomenon**" in result
        assert "**Subjective Experience**" in result
        assert "*Qualia*" in result
        
        # Check list
        assert "- " in result
        
        # Check code block
        assert "```" in result
        assert "def think():" in result
        
        # Check link
        assert "[Stanford Encyclopedia](https://plato.stanford.edu)" in result
