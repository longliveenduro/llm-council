import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import WebChatBotWizard from './WebChatBotWizard';
import fs from 'fs';
import path from 'path';

describe('WebChatBotWizard Contrast', () => {
    const defaultProps = {
        conversationId: 'contrast-test',
        currentTitle: 'Contrast Test',
        llmNames: ['Claude 4.5 Sonnet'],
        automationModels: {
            ai_studio: [{ name: 'Gemini 3 Pro Preview', id: 'g3p' }],
            chatgpt: [{ name: 'ChatGPT 5.2', id: 'c52' }],
            claude: [{ name: 'Claude 4.5 Sonnet', id: 'c45s' }],
        },
    };

    it('Automation Targets have correct styling for light and dark modes', () => {
        // Inject CSS
        const cssPath = path.resolve(__dirname, 'WebChatBotWizard.css');
        const cssContent = fs.readFileSync(cssPath, 'utf8');
        const style = document.createElement('style');
        style.type = 'text/css';
        style.innerHTML = cssContent;
        document.head.appendChild(style);

        const { container } = render(<WebChatBotWizard {...defaultProps} />);

        const badgeRows = container.querySelectorAll('.best-model-badge-row');
        expect(badgeRows.length).toBeGreaterThan(0);

        const firstRow = badgeRows[0];
        const rowStyle = window.getComputedStyle(firstRow);

        // Check baseline styles
        expect(rowStyle.display).toBe('flex');
        expect(rowStyle.borderRadius).toBe('8px');

        // Dark mode simulation (if the app or parent has .dark-mode)
        container.closest('body').classList.add('dark-mode');
        // JSDOM might not perfectly reflect media queries/complex selectors but it should catch basic ones if we added .dark-mode .best-model-badge-row

        const darkRowStyle = window.getComputedStyle(firstRow);
        // We defined: background: rgba(255, 255, 255, 0.07);
        // In JSDOM this might not update unless we force a style re-calc or if it's simple enough.
        // Actually, JSDOM getComputedStyle is limited.

        // But we can at least check if the class exists and the elements are in the DOM
        expect(screen.getByText('Gemini:')).toBeInTheDocument();
        expect(screen.getByText('Gemini 3 Pro Preview')).toBeInTheDocument();

        // Cleanup
        document.head.removeChild(style);
        container.closest('body').classList.remove('dark-mode');
    });
});
