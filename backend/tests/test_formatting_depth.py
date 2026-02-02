import pytest
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright
from browser_automation.ai_studio_automation import clean_ai_studio_text, AI_STUDIO_JS
from browser_automation.claude_automation import clean_claude_text, CLAUDE_JS
from browser_automation.chatgpt_automation import clean_chatgpt_text, CHATGPT_JS

# Read local Turndown lib
TURNDOWN_LIB = (Path(__file__).parent.parent.parent / "browser_automation" / "turndown.min.js").read_text()

@pytest.mark.asyncio
async def test_complex_formatting_pipeline():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # Inject Turndown for tests
        # Inject Turndown for tests
        await page.evaluate(TURNDOWN_LIB + "; window.TurndownService = TurndownService;")
        await page.wait_for_function("typeof TurndownService !== 'undefined'")
        
        # Scenario 1: AI Studio with complex nested lists and display math
        ai_studio_html = r'''
        <ms-chat-turn>
            <ms-markdown-block>
                <ms-text-chunk>
                    <h1>Header</h1>
                    <ul>
                        <li>Item 1
                            <ul>
                                <li>Nested A</li>
                                <li>Nested B</li>
                            </ul>
                        </li>
                        <li>Item 2</li>
                    </ul>
                    <ms-math-block class="math-display">
                        <math><semantics><annotation encoding="application/x-tex">\begin{matrix} a & b \\ c & d \end{matrix}</annotation></semantics></math>
                    </ms-math-block>
                </ms-text-chunk>
            </ms-markdown-block>
        </ms-chat-turn>
        '''
        await page.set_content(ai_studio_html)
        extracted = await page.evaluate(AI_STUDIO_JS)
        cleaned = clean_ai_studio_text(extracted)
        
        print(f"\nAI Studio Cleaned:\n{cleaned}")
        assert "Header" in cleaned
        assert "Nested A" in cleaned
        assert "Nested B" in cleaned
        assert "matrix" in cleaned
        assert "\n" in cleaned

        # Scenario 2: Claude with thinking blocks and code blocks
        claude_html = r'''
        <div class="font-claude-message">
            <div class="prose">
                <p>I will think about this.</p>
                <details class="thinking">Reasoning process...</details>
                <p>Here is your code:</p>
                <pre><code>def hello():
    print("world")
    # multiple spaces here    <--
</code></pre>
                <p>Done.</p>
                <div class="math math-display">
                    <semantics><annotation encoding="application/x-tex">x^2 + y^2 = r^2</annotation></semantics>
                </div>
            </div>
        </div>
        '''
        await page.set_content(claude_html)
        extracted = await page.evaluate(CLAUDE_JS)
        # We need to simulate the 'prompt' arg for claude clean if we want to test redundant prompt removal
        cleaned = clean_claude_text(extracted, prompt="dummy prompt")
        
        print(f"\nClaude Cleaned:\n{cleaned}")
        assert "Reasoning process" not in cleaned
        assert "def hello():" in cleaned
        assert "    print(\"world\")" in cleaned
        assert "    <--" in cleaned
        assert "x^2 + y^2 = r^2" in cleaned
        assert "Done." in cleaned

        # Scenario 3: ChatGPT with multiple math formulas and citations
        chatgpt_html = r'''
        <div data-message-author-role="assistant">
            <div class="markdown prose">
                <p>Formula 1: <span class="katex"><annotation encoding="application/x-tex">E=mc^2</annotation></span></p>
                <p>Formula 2 in display:</p>
                <div class="katex-display">
                    <span class="katex"><annotation encoding="application/x-tex">\sum_{i=1}^n i = \frac{n(n+1)}{2}</annotation></span>
                </div>
                <p>According to <button class="cit-button">[1]</button> and <span class="citation">[+2]</span>.</p>
                <button class="cit-button">[1]</button>
            </div>
        </div>
        '''
        await page.set_content(chatgpt_html)
        extracted = await page.evaluate(CHATGPT_JS)
        cleaned = clean_chatgpt_text(extracted)
        
        print(f"\nChatGPT Cleaned:\n{cleaned}")
        assert "E=mc^2" in cleaned
        assert "\\sum" in cleaned
        assert "[1]" not in cleaned
        assert "[+2]" not in cleaned
        assert "Formula 1" in cleaned

        await browser.close()

@pytest.mark.asyncio
async def test_extra_whitespace_and_empty_lines():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # Inject Turndown for tests
        # Inject Turndown for tests
        await page.evaluate(TURNDOWN_LIB + "; window.TurndownService = TurndownService;")
        await page.wait_for_function("typeof TurndownService !== 'undefined'")
        
        # Test that cleaning functions consolidate multiple empty lines (\n\n\n) into \n\n
        content = r'''
        <div data-message-author-role="assistant">
            <div class="prose">
                <p>Paragraph 1</p>
                <br><br><br><br>
                <p>Paragraph 2</p>
            </div>
        </div>
        '''
        await page.set_content(content)
        extracted = await page.evaluate(CHATGPT_JS)
        cleaned = clean_chatgpt_text(extracted)
        
        print(f"\nWhitespace Cleanup Result:\n{repr(cleaned)}")
        # Check that we don't have more than 2 consecutive newlines
        assert "\n\n\n" not in cleaned
        assert "Paragraph 1" in cleaned
        assert "Paragraph 2" in cleaned

        await browser.close()
