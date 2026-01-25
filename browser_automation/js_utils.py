"""
Shared JavaScript Utilities for Browser Automation.

This module contains shared JavaScript code strings that are injected 
into browser pages (via Playwright's page.evaluate) to perform complex 
DOM operations that are hard to do from Python alone.
"""

HTML_TO_MARKDOWN_JS = r'''
(function(scope) {
    if (scope.domToMarkdown) return scope.domToMarkdown;

    function domToMarkdown(rootElement, options = {}) {
        if (!rootElement) return "";

        // --- Configuration ---
        // Helper to check for block elements
        const isBlock = (tagName) => {
            return ['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'div', 'ul', 'ol', 'li', 'pre', 'blockquote', 'table', 'tr', 'article', 'section'].includes(tagName);
        };

        // --- Recursive Processor ---
        function processNode(node) {
            if (!node) return "";

            // 1. Handle Shadow DOM (Pierce abstraction)
            // If an element has an open shadow root, its rendered content is there.
            if (node.shadowRoot) {
                let res = "";
                for (let child of node.shadowRoot.childNodes) {
                    res += processNode(child);
                }
                return res;
            }

            // 2. Text Nodes
            if (node.nodeType === 3) { // Node.TEXT_NODE
                // Check if we are inside a code block
                const parent = node.parentElement;
                const isCode = parent && (parent.closest('pre') || parent.closest('code') || parent.tagName === 'MS-CODE-BLOCK');
                
                if (isCode) {
                    return node.textContent;
                }
                
                // Normalize whitespace: replace newlines/tabs/multi-space with single space
                return node.textContent.replace(/\s+/g, ' ');
            }

            if (node.nodeType !== 1) return ""; // Skip comments etc.

            const tagName = node.tagName.toLowerCase();

            // 3. Ignore Noise / UI Elements
            if (['button', 'ms-copy-button', 'ms-feedback-button', 'mat-icon', 'script', 'style', 'noscript', 'img', 'svg'].includes(tagName)) return "";
            if (node.classList.contains('sr-only') || node.getAttribute('aria-hidden') === 'true') return "";
            if (node.classList.contains('citation') && !node.textContent.includes('[')) return ""; // Skip purely visual citations if better ones exist

            // 4. Handle Math (Latex Attributes) - Common in AI Studio
            let latex = node.getAttribute('latex') || node.getAttribute('data-latex');
            if (!latex && tagName === 'annotation' && node.getAttribute('encoding') === 'application/x-tex') {
                latex = node.textContent.trim();
            }
            if (latex) {
                const isDisplay = node.classList.contains('display') || 
                                  node.classList.contains('math-display') || 
                                  tagName === 'ms-math-block' ||
                                  node.closest && node.closest('ms-math-block');
                return isDisplay ? `\n$$\n${latex}\n$$\n` : `$${latex}$`;
            }

            // 5. Handle Slots (Shadow DOM projection)
            if (tagName === 'slot') {
                let res = "";
                // assignedNodes({flatten: true}) gets the distributed nodes
                const assigned = node.assignedNodes ? node.assignedNodes({flatten: true}) : [];
                if (assigned.length > 0) {
                    for (let n of assigned) res += processNode(n);
                } else {
                    // Fallback content if nothing assigned
                    for (let child of node.childNodes) res += processNode(child);
                }
                return res;
            }

            // 6. Handle Code Blocks specifically
            if (tagName === 'pre' || tagName === 'ms-code-block') {
                const codeEl = node.querySelector('code') || node;
                let lang = "";
                const classes = codeEl.className || "";
                const match = classes.match(/language-(\w+)/);
                if (match) lang = match[1];
                
                // Use textContent directly to preserve whitespace
                return `\n\`\`\`${lang}\n${node.textContent.trim()}\n\`\`\`\n`;
            }

            if (tagName === 'br') return '\n';

            // 7. Generic Child Traversal
            let content = "";
            for (let child of node.childNodes) {
                content += processNode(child);
            }

            // 8. Element Formatting based on Semantic Tags AND Computed Styles
            let prefix = "";
            let suffix = "";
            
            // Check computed styles for bold/italic on ANY element that isn't already a semantic formatting tag
            // we skip explicit formatting tags because they are handled in the switch below
            const semanticTags = ['b', 'strong', 'i', 'em', 'code', 'pre', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'];
            
            if (!semanticTags.includes(tagName)) {
                // Using getComputedStyle is expensive, catch errors if node detached
                try {
                    const style = window.getComputedStyle(node);
                    const fontWeight = style.fontWeight; // '700', 'bold', etc.
                    const fontStyle = style.fontStyle;   // 'italic'
                    
                    // Simple bold check (>= 500 or "bold" or "bolder")
                    // Note: 500 is "Medium", often used for emphasis in Material Design (AI Studio)
                    // We treat it as bold to preserve visual distinction.
                    const isBold = fontWeight === 'bold' || fontWeight === 'bolder' || parseInt(fontWeight) >= 500;
                    const isItalic = fontStyle === 'italic';
                    
                    if (isBold) { prefix += "**"; suffix = "**" + suffix; }
                    if (isItalic) { prefix += "_"; suffix = "_" + suffix; }
                } catch(e) {}
            }

            switch (tagName) {
                case 'h1': return `\n# ${content.trim()}\n\n`;
                case 'h2': return `\n## ${content.trim()}\n\n`;
                case 'h3': return `\n### ${content.trim()}\n\n`;
                case 'h4': return `\n#### ${content.trim()}\n\n`;
                case 'h5': return `\n##### ${content.trim()}\n\n`;
                case 'h6': return `\n###### ${content.trim()}\n\n`;

                case 'p': return `\n${prefix}${content.trim()}${suffix}\n\n`;

                case 'b':
                case 'strong': return `**${content}**`;

                case 'i':
                case 'em': return `_${content}_`;

                case 'code': return `\`${content}\``;

                case 'ul': return `\n${content}\n`;
                case 'ol': return `\n${content}\n`;

                case 'li':
                    let outputPrefix = "- ";
                    const parent = node.parentElement;
                    if (parent && parent.tagName.toLowerCase() === 'ol') {
                        // Calculate index: count preceding LI siblings
                        let index = 1;
                        let sibling = node.previousElementSibling;
                        while (sibling) {
                            if (sibling.tagName.toLowerCase() === 'li') index++;
                            sibling = sibling.previousElementSibling;
                        }
                        outputPrefix = `${index}. `;
                    }
                    return `${outputPrefix}${prefix}${content.trim()}${suffix}\n`;

                case 'a':
                    if (!content.trim()) return ""; 
                    const href = node.getAttribute('href');
                    if (href && !href.startsWith('javascript:')) {
                        return `[${content.trim()}](${href})`;
                    }
                    return content;

                case 'blockquote':
                    return `\n> ${content.trim()}\n\n`;

                case 'table':
                    // Simple table conversion (could be improved)
                    return `\n${content.trim()}\n`;

                case 'tr': return `| ${content.trim()} |\n`;
                case 'td': 
                case 'th': return `${content.trim()} | `;
                
                case 'div':
                    // Divs are tricky. They might be blocks or inline wrappers.
                    // If content has newlines, treat as block?
                    return `${prefix}${content}${suffix}`;

                default: return `${prefix}${content}${suffix}`;
            }
        }

        // Start processing
        let result = processNode(rootElement);
        
        // --- Post-Processing / Cleanup ---
        // 1. Collapse multiple newlines (max 2)
        result = result.replace(/\n{3,}/g, '\n\n');
        // 2. Trim
        return result.trim();
    }

    scope.domToMarkdown = domToMarkdown;
    return domToMarkdown;
})(window);
'''
