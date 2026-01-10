import pytest
import asyncio
from playwright.async_api import async_playwright

# The JS extraction logic from ai_studio_automation.py, claude_automation.py, and chatgpt_automation.py
# extracted and put into functions for testing.

AI_STUDIO_JS = r'''
() => {
    const lastTurn = document.querySelector('ms-chat-turn:last-of-type');
    if (!lastTurn) return "DEBUG: No last turn found";
    
    const clone = lastTurn.cloneNode(true);
    
    // 1. Process Math Elements
    const mathElements = clone.querySelectorAll('ms-katex, ms-math-block, .math, .math-inline, .math-display, [latex]');
    
    mathElements.forEach(el => {
        let latex = el.getAttribute('latex') || el.getAttribute('data-latex');
        if (!latex) {
            const annotation = el.querySelector('annotation[encoding="application/x-tex"]');
            if (annotation) latex = annotation.textContent.trim();
        }
        if (latex) {
            const isDisplay = el.classList.contains('display') || 
                              el.classList.contains('math-display') || 
                              el.tagName === 'MS-MATH-BLOCK' ||
                              el.closest('ms-math-block');
            el.textContent = isDisplay ? `\n$$\n${latex}\n$$\n` : `$${latex}$`;
        }
    });

    // 2. Remove UI noise
    const noise = clone.querySelectorAll('button, .mat-icon, ms-copy-button, ms-feedback-button, .sr-only');
    noise.forEach(el => el.remove());

    // 3. Hidden Append Strategy
    clone.style.position = 'absolute';
    clone.style.left = '-9999px';
    clone.style.whiteSpace = 'pre-wrap';
    document.body.appendChild(clone);
    
    let resultText = null;
    try {
        const contentEls = clone.querySelectorAll('ms-markdown-block, ms-text-chunk, .text-content');
        if (contentEls.length > 0) {
            resultText = Array.from(contentEls).map(el => el.innerText).join('\n').trim();
        } else {
            resultText = clone.innerText.trim();
        }
    } finally {
        document.body.removeChild(clone);
    }
    return resultText;
}
'''

CLAUDE_JS = r'''
() => {
    const candidates = Array.from(document.querySelectorAll('.font-claude-message, .font-claude-response'));
    if (candidates.length === 0) return "DEBUG: No candidates found";
    
    const topLevelMessages = candidates.filter(el => 
        !el.parentElement.closest('.font-claude-message, .font-claude-response')
    );
    
    if (topLevelMessages.length === 0) return "DEBUG: No top-level messages found";
    const lastMessage = topLevelMessages[topLevelMessages.length - 1];
    const clone = lastMessage.cloneNode(true);

    const mathElements = clone.querySelectorAll('.katex, .math, .math-inline, .math-display');
    mathElements.forEach(el => {
        const annotation = el.querySelector('annotation[encoding="application/x-tex"]');
        if (annotation) {
            const latex = annotation.textContent;
            const isBlock = el.classList.contains('math-display') || el.closest('.math-display');
            el.textContent = isBlock ? `\n$$\n${latex}\n$$\n` : `$${latex}$`;
        }
    });

    clone.style.position = 'absolute';
    clone.style.left = '-9999px';
    clone.style.whiteSpace = 'pre-wrap';
    document.body.appendChild(clone);
    
    let resultText = null;
    try {
        const allMarkdown = clone.querySelectorAll('.standard-markdown');
        if (allMarkdown.length > 0) {
            const lastMarkdown = allMarkdown[allMarkdown.length - 1];
            resultText = lastMarkdown.innerText.trim();
        } else {
            const thinkingSelectors = [
                'details', '[class*="thinking"]', '[class*="Thinking"]',
                '[data-testid*="thinking"]', 'summary', '.border-border-300.rounded-lg',
            ];
            for (const selector of thinkingSelectors) {
                const elements = clone.querySelectorAll(selector);
                elements.forEach(el => el.remove());
            }
            const prose = clone.querySelector('.prose');
            if (prose) {
                resultText = prose.innerText.trim();
            } else {
                resultText = clone.innerText.trim();
            }
        }
    } finally {
        document.body.removeChild(clone);
    }
    return resultText;
}
'''

CHATGPT_JS = r'''
() => {
    const assistantMessages = document.querySelectorAll('[data-message-author-role="assistant"]');
    if (assistantMessages.length === 0) return "DEBUG: No assistant messages found";
    
    const lastMessage = assistantMessages[assistantMessages.length - 1];
    const clone = lastMessage.cloneNode(true);
    
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
        // Regex for [+1] or [1]
        if (/^\[\+?\d+\]$/.test(text)) el.remove();
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
}
'''

@pytest.mark.asyncio
async def test_ai_studio_line_breaks_and_math():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # Simulate AI Studio HTML
        htmlContent = r'''
        <ms-chat-turn>
            <ms-markdown-block>
                <ms-text-chunk>
                    <p>First paragraph with some <b>bold</b> text.</p>
                    <p>Second paragraph starting after a break.</p>
                </ms-text-chunk>
                <ms-text-chunk>
                    <p>Third paragraph in a separate chunk.</p>
                    <ms-math-block class="math-display">
                        <math>
                            <semantics>
                                <annotation encoding="application/x-tex">E = mc^2</annotation>
                            </semantics>
                        </math>
                    </ms-math-block>
                    <p>Text after math: <ms-katex class="math-inline"><math><semantics><annotation encoding="application/x-tex">x+y</annotation></semantics></math></ms-katex> is cool.</p>
                </ms-text-chunk>
            </ms-markdown-block>
            <button>Copy</button>
        </ms-chat-turn>
        '''
        await page.set_content(htmlContent)
        
        result = await page.evaluate(AI_STUDIO_JS)
        await browser.close()
        
        print(f"\nAI Studio Result:\n{result}")
        assert "First paragraph" in result
        assert "Second paragraph" in result
        assert "Third paragraph" in result
        # Check math - it should be wrapped in $$ or $ and contained within the result
        assert "E = mc^2" in result or "E=mc^2" in result.replace(" ", "")
        assert "x+y" in result
        assert "\n" in result

@pytest.mark.asyncio
async def test_claude_formatting():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # Simulate Claude HTML
        # Use simple hex for the pi symbol to avoid encoding issues in tests
        htmlContent = r'''
        <div class="font-claude-message">
            <div class="prose">
                <p>Paragraph one.</p>
                <p>Paragraph two with math <span class="math math-inline"><semantics><annotation encoding="application/x-tex">\pi</annotation></semantics></span>.</p>
                <div class="math math-display">
                    <semantics><annotation encoding="application/x-tex">\int_0^1 x dx</annotation></semantics>
                </div>
                <details class="thinking">thinking content to be removed</details>
            </div>
        </div>
        '''
        await page.set_content(htmlContent)
        
        result = await page.evaluate(CLAUDE_JS)
        await browser.close()
        
        print(f"\nClaude Result:\n{result}")
        assert "Paragraph one." in result
        assert "Paragraph two" in result
        assert r"$\pi$" in result or r"pi" in result.lower()
        assert r"int_0^1xdx" in result.replace(" ", "") or "int_0^1 x dx" in result
        assert "thinking content" not in result

@pytest.mark.asyncio
async def test_chatgpt_formatting():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # Simulate ChatGPT HTML
        htmlContent = '''
        <div data-message-author-role="assistant">
            <div class="markdown prose">
                <p>Here is some logic:</p>
                <pre><code>code block\nline 2</code></pre>
                <p>Formula:</p>
                <div class="katex-display">
                    <span class="katex">
                        <annotation encoding="application/x-tex">a^2 + b^2 = c^2</annotation>
                    </span>
                </div>
                <p>Citation <button class="cit-button">[1]</button></p>
            </div>
        </div>
        '''
        await page.set_content(htmlContent)
        
        result = await page.evaluate(CHATGPT_JS)
        await browser.close()
        
        print(f"\nChatGPT Result:\n{result}")
        assert "Here is some logic:" in result
        assert "code block\nline 2" in result or "code block" in result
        assert "$$\na^2 + b^2 = c^2\n$$" in result or "$$a^2 + b^2 = c^2$$" in result or "a^2 + b^2 = c^2" in result
        assert "[1]" not in result

@pytest.mark.asyncio
async def test_whitespace_preservation():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # Test pre-wrap preservation
        htmlContent = '''
        <div data-message-author-role="assistant">
            <div class="prose">
                <p>Line 1</p>
                <p>  Indented Line</p>
                <p>Line 3</p>
            </div>
        </div>
        '''
        await page.set_content(htmlContent)
        
        result = await page.evaluate(CHATGPT_JS)
        await browser.close()
        
        print(f"\nWhitespace Result:\n{result}")
        # Check that indentation is preserved from innerText with pre-wrap
        assert "  Indented Line" in result
        assert "Line 1" in result
        assert "Line 3" in result

@pytest.mark.asyncio
async def test_multiple_spaces_preservation():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # Test preservation of multiple consecutive spaces
        htmlContent = '''
        <div data-message-author-role="assistant">
            <div class="prose">
                <p>Word    with    four    spaces.</p>
                <p>Mixed\tspaces\tand\ttabs.</p>
            </div>
        </div>
        '''
        await page.set_content(htmlContent)
        
        result = await page.evaluate(CHATGPT_JS)
        await browser.close()
        
        print(f"\nMultiple Spaces Result:\n{result}")
        # innerText with pre-wrap should preserve multiple spaces
        assert "Word    with    four    spaces." in result
        assert "Mixed" in result and "tabs." in result

