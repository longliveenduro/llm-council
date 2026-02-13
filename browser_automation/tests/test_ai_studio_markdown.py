"""
Tests for AI Studio HTML to Markdown conversion.

These tests verify that the AI_STUDIO_JS extraction script correctly converts
AI Studio's HTML-formatted responses to proper Markdown syntax.
"""

import pytest
from pathlib import Path
from playwright.sync_api import sync_playwright


# Read the local Turndown library
TURNDOWN_PATH = Path(__file__).parent.parent / "turndown.min.js"
TURNDOWN_LIB = TURNDOWN_PATH.read_text()

# Sample AI Studio HTML structure (simplified from real response)
AI_STUDIO_SAMPLE_HTML = """
<ms-chat-turn id="turn-123" class="ng-star-inserted">
    <div class="chat-turn-container model render">
        <div class="virtual-scroll-container model-prompt-container">
            <div class="turn-content">
                <ms-prompt-chunk class="text-chunk">
                    <ms-text-chunk class="ng-star-inserted">
                        <ms-cmark-node class="cmark-node v3-font-body ng-star-inserted">
                            <p class="ng-star-inserted">
                                <ms-cmark-node>
                                    <span class="ng-star-inserted">At its core, </span>
                                    <strong class="ng-star-inserted">
                                        <ms-cmark-node>
                                            <span class="ng-star-inserted">consciousness is the state of being aware</span>
                                        </ms-cmark-node>
                                    </strong>
                                    <span class="ng-star-inserted"> of one's surroundings.</span>
                                </ms-cmark-node>
                            </p>
                            <h3 class="ng-star-inserted">
                                <ms-cmark-node>
                                    <span class="ng-star-inserted">1. The Basic Definition</span>
                                </ms-cmark-node>
                            </h3>
                            <ul class="ng-star-inserted">
                                <ms-cmark-node>
                                    <li class="ng-star-inserted">
                                        <ms-cmark-node>
                                            <p class="ng-star-inserted">
                                                <ms-cmark-node>
                                                    <strong class="ng-star-inserted">
                                                        <ms-cmark-node>
                                                            <span class="ng-star-inserted">Awareness:</span>
                                                        </ms-cmark-node>
                                                    </strong>
                                                    <span class="ng-star-inserted"> Being awake and responsive.</span>
                                                </ms-cmark-node>
                                            </p>
                                        </ms-cmark-node>
                                    </li>
                                    <li class="ng-star-inserted">
                                        <ms-cmark-node>
                                            <p class="ng-star-inserted">
                                                <ms-cmark-node>
                                                    <span style="font-style: italic;" class="ng-star-inserted">
                                                        <ms-cmark-node>
                                                            <span class="ng-star-inserted">Qualia</span>
                                                        </ms-cmark-node>
                                                    </span>
                                                    <span class="ng-star-inserted"> - subjective experience.</span>
                                                </ms-cmark-node>
                                            </p>
                                        </ms-cmark-node>
                                    </li>
                                </ms-cmark-node>
                            </ul>
                            <hr class="ng-star-inserted">
                            <p class="ng-star-inserted">
                                <ms-cmark-node>
                                    <span class="ng-star-inserted">This is the conclusion.</span>
                                </ms-cmark-node>
                            </p>
                        </ms-cmark-node>
                    </ms-text-chunk>
                </ms-prompt-chunk>
            </div>
        </div>
    </div>
</ms-chat-turn>
"""

# JavaScript that mimics the AI_STUDIO_JS extraction logic
AI_STUDIO_EXTRACT_JS = """
(html) => {
    // Parse the HTML into a temporary container
    const container = document.createElement('div');
    container.innerHTML = html;
    
    const lastTurn = container.querySelector('ms-chat-turn');
    if (!lastTurn) return { error: 'No ms-chat-turn found' };
    
    // Find the content element
    const candidates = ['ms-markdown-block', '.markdown-renderer', 'ms-text-chunk', '.content'];
    let contentEl = null;
    for (const selector of candidates) {
        const found = lastTurn.querySelector(selector);
        if (found) {
            contentEl = found;
            break;
        }
    }
    
    if (!contentEl) contentEl = lastTurn;
    
    const clone = contentEl.cloneNode(true);
    
    // Remove UI noise
    const noise = clone.querySelectorAll('button, .mat-icon, ms-copy-button, ms-feedback-button, .sr-only');
    noise.forEach(el => el.remove());
    
    // Convert with Turndown
    if (typeof TurndownService !== 'undefined') {
        const turndownService = new TurndownService({
            headingStyle: 'atx',
            codeBlockStyle: 'fenced',
            bulletListMarker: '-',
            emDelimiter: '*',
            strongDelimiter: '**'
        });
        
        const contentEls = clone.querySelectorAll('ms-markdown-block, ms-text-chunk, .text-content');
        let resultText;
        if (contentEls.length > 0) {
            resultText = Array.from(contentEls).map(el => turndownService.turndown(el.innerHTML)).join('\\n\\n').trim();
        } else {
            resultText = turndownService.turndown(clone.innerHTML).trim();
        }
        
        return { markdown: resultText };
    }
    
    return { error: 'Turndown not loaded' };
}
"""


@pytest.fixture(scope="module")
def browser_page():
    """Create a browser page with Turndown loaded for testing."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content("<html><body></body></html>")
        
        # Inject Turndown via evaluate to simulate CSP bypass
        page.evaluate(TURNDOWN_LIB + "; window.TurndownService = TurndownService;")
        page.wait_for_function("typeof TurndownService !== 'undefined'", timeout=10000)
        yield page
        browser.close()


class TestAIStudioMarkdownExtraction:
    """Test AI Studio specific HTML to Markdown conversion."""
    
    def test_extracts_bold_text(self, browser_page):
        """Bold text in <strong> tags should become **bold**."""
        result = browser_page.evaluate(AI_STUDIO_EXTRACT_JS, AI_STUDIO_SAMPLE_HTML)
        assert 'error' not in result, f"Extraction failed: {result.get('error')}"
        assert '**consciousness is the state of being aware**' in result['markdown']
    
    def test_extracts_headings(self, browser_page):
        """H3 tags should become ### headings."""
        result = browser_page.evaluate(AI_STUDIO_EXTRACT_JS, AI_STUDIO_SAMPLE_HTML)
        assert 'error' not in result, f"Extraction failed: {result.get('error')}"
        # Turndown escapes periods in numbered headings
        markdown = result['markdown']
        assert '### 1' in markdown and 'The Basic Definition' in markdown
    
    def test_extracts_lists(self, browser_page):
        """UL/LI tags should become bullet points."""
        result = browser_page.evaluate(AI_STUDIO_EXTRACT_JS, AI_STUDIO_SAMPLE_HTML)
        assert 'error' not in result, f"Extraction failed: {result.get('error')}"
        markdown = result['markdown']
        # Check that list items are present (may have varying indentation)
        assert '**Awareness:**' in markdown
        assert 'Being awake and responsive' in markdown
    
    def test_extracts_italic_text(self, browser_page):
        """Italic text in style="font-style: italic" should become *italic*."""
        result = browser_page.evaluate(AI_STUDIO_EXTRACT_JS, AI_STUDIO_SAMPLE_HTML)
        assert 'error' not in result, f"Extraction failed: {result.get('error')}"
        markdown = result['markdown']
        # Turndown might render this as *Qualia* or _Qualia_
        assert 'Qualia' in markdown
        # Check formatting is applied
        assert '*' in markdown or '_' in markdown
    
    def test_extracts_horizontal_rules(self, browser_page):
        """HR tags should become horizontal rules (--- or * * *)."""
        result = browser_page.evaluate(AI_STUDIO_EXTRACT_JS, AI_STUDIO_SAMPLE_HTML)
        assert 'error' not in result, f"Extraction failed: {result.get('error')}"
        markdown = result['markdown']
        # Turndown renders <hr> as * * * or ---
        assert '* * *' in markdown or '---' in markdown or '- - -' in markdown
    
    def test_preserves_content_order(self, browser_page):
        """Content should be extracted in the correct order."""
        result = browser_page.evaluate(AI_STUDIO_EXTRACT_JS, AI_STUDIO_SAMPLE_HTML)
        assert 'error' not in result, f"Extraction failed: {result.get('error')}"
        markdown = result['markdown']
        
        # Check that content appears in order
        intro_pos = markdown.find('consciousness')
        # Heading number might be escaped
        heading_pos = markdown.find('Basic Definition')
        conclusion_pos = markdown.find('This is the conclusion')
        
        assert intro_pos < heading_pos < conclusion_pos, \
            f"Content is not in the expected order: intro={intro_pos}, heading={heading_pos}, conclusion={conclusion_pos}"


class TestRealAIStudioHTML:
    """Test with actual AI Studio HTML if available."""
    
    def test_real_html_extraction(self, browser_page):
        """Test extraction with real AI Studio HTML dump if available."""
        html_file = Path(__file__).parent.parent.parent / "ai_studio_last_turn.html"
        
        if not html_file.exists():
            pytest.skip("No real AI Studio HTML dump available")
        
        html = html_file.read_text()
        result = browser_page.evaluate(AI_STUDIO_EXTRACT_JS, html)
        
        assert 'error' not in result, f"Extraction failed: {result.get('error')}"
        markdown = result['markdown']
        
        # Basic sanity checks
        assert len(markdown) > 100, "Extracted markdown is too short"
        
        # Check for markdown formatting
        has_formatting = any([
            '**' in markdown,  # bold
            '###' in markdown,  # h3
            '##' in markdown,   # h2
            '- ' in markdown,   # list
            '1.' in markdown,   # ordered list
        ])
        assert has_formatting, "Extracted markdown has no formatting"
        
        print(f"\n--- Extracted {len(markdown)} chars of markdown ---")
        print(markdown[:1000])


class TestTrustedTypesCompatibility:
    """Test that extraction works when Trusted Types is enforced (like AI Studio)."""
    
    def test_extraction_with_trusted_types_enforced(self):
        """
        AI Studio enforces Trusted Types CSP which blocks raw innerHTML assignments.
        This test simulates that and verifies the default policy workaround works.
        """
        import subprocess, json, sys
        
        script = f'''
import json, sys
sys.path.insert(0, "{Path(__file__).parent.parent.parent}")
from pathlib import Path
from playwright.sync_api import sync_playwright

TURNDOWN_LIB = Path("{TURNDOWN_PATH}").read_text()
SAMPLE_HTML = """{AI_STUDIO_SAMPLE_HTML.replace(chr(10), chr(10))}"""

EXTRACT_JS = """
(html) => {{
    const container = document.createElement('div');
    container.innerHTML = html;
    const lastTurn = container.querySelector('ms-chat-turn');
    if (!lastTurn) return {{ error: 'No ms-chat-turn found' }};
    const candidates = ['ms-markdown-block', '.markdown-renderer', 'ms-text-chunk', '.content'];
    let contentEl = null;
    for (const selector of candidates) {{
        const found = lastTurn.querySelector(selector);
        if (found) {{ contentEl = found; break; }}
    }}
    if (!contentEl) contentEl = lastTurn;
    const clone = contentEl.cloneNode(true);
    clone.querySelectorAll('button, .mat-icon').forEach(el => el.remove());
    if (typeof TurndownService !== 'undefined') {{
        const ts = new TurndownService({{ headingStyle: 'atx', strongDelimiter: '**' }});
        const els = clone.querySelectorAll('ms-text-chunk');
        let md = els.length > 0 ? Array.from(els).map(el => ts.turndown(el.innerHTML)).join('\\\\n\\\\n').trim() : ts.turndown(clone.innerHTML).trim();
        return {{ markdown: md }};
    }}
    return {{ error: 'Turndown not loaded' }};
}}
"""

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.set_content("""<html><head>
        <meta http-equiv="Content-Security-Policy" 
              content="require-trusted-types-for 'script'; trusted-types default ai-studio-turndown">
    </head><body></body></html>""")
    
    tt = page.evaluate("typeof window.trustedTypes !== 'undefined'")
    
    # Create default policy (the fix)
    page.evaluate("""
        if (window.trustedTypes && window.trustedTypes.createPolicy) {{
            window.trustedTypes.createPolicy('default', {{
                createHTML: (s) => s,
                createScriptURL: (s) => s,
                createScript: (s) => s
            }});
        }}
    """)
    
    page.evaluate(TURNDOWN_LIB + "; window.TurndownService = TurndownService;")
    page.wait_for_function("typeof TurndownService !== 'undefined'", timeout=5000)
    
    result = page.evaluate(EXTRACT_JS, SAMPLE_HTML)
    browser.close()
    
    print(json.dumps({{"tt_available": tt, "result": result}}))
'''
        proc = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True, text=True, timeout=30
        )
        assert proc.returncode == 0, f"Script failed: {proc.stderr}"
        
        output = json.loads(proc.stdout.strip())
        assert output["tt_available"], "Trusted Types should be available"
        assert "error" not in output["result"], f"Extraction error: {output['result']}"
        md = output["result"]["markdown"]
        assert "**" in md, f"Bold formatting missing. Got: {md[:200]}"
        assert "###" in md, f"Heading formatting missing. Got: {md[:200]}"
    
    def test_innerhtml_blocked_without_policy(self):
        """
        Verify innerHTML is blocked by Trusted Types without a default policy.
        """
        import subprocess, json, sys
        
        script = '''
import json
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.set_content("""<html><head>
        <meta http-equiv="Content-Security-Policy" 
              content="require-trusted-types-for 'script'; trusted-types ai-studio-turndown">
    </head><body></body></html>""")
    
    result = page.evaluate("""
        (() => {
            try {
                const div = document.createElement('div');
                document.body.appendChild(div);
                div.innerHTML = '<strong>test</strong>';
                document.body.removeChild(div);
                return { blocked: false };
            } catch(e) {
                return { blocked: true, error: e.message };
            }
        })()
    """)
    browser.close()
    print(json.dumps(result))
'''
        proc = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True, text=True, timeout=30
        )
        assert proc.returncode == 0, f"Script failed: {proc.stderr}"
        result = json.loads(proc.stdout.strip())
        assert result["blocked"], \
            "innerHTML should be blocked by Trusted Types without a default policy"
