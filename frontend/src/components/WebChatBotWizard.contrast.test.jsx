import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import WebChatBotWizard from './WebChatBotWizard';
import fs from 'fs';
import path from 'path';

describe('WebChatBotWizard Contrast', () => {
    const defaultProps = {
        conversationId: 'contrast-test',
        currentTitle: 'Contrast Test',
        llmNames: ['Claude 4.6 Sonnet'],
        automationModels: {
            ai_studio: [{ name: 'Gemini 3 Pro Preview', id: 'g3p' }],
            chatgpt: [{ name: 'ChatGPT 5.2', id: 'c52' }],
            claude: [{ name: 'Claude 4.6 Sonnet', id: 'c45s' }],
        },
    };

    it('Stage 1 form groups have correct layout and labels', () => {
        // Inject CSS
        const cssPath = path.resolve(__dirname, 'WebChatBotWizard.css');
        const cssContent = fs.readFileSync(cssPath, 'utf8');
        const style = document.createElement('style');
        style.type = 'text/css';
        style.innerHTML = cssContent;
        document.head.appendChild(style);

        const { container } = render(<WebChatBotWizard {...defaultProps} />);

        const formGroups = container.querySelectorAll('.form-group');
        expect(formGroups.length).toBeGreaterThan(0);

        // Verify "Your Question" section
        expect(screen.getByText(/Your Question:/i)).toBeInTheDocument();
        const questionLabel = screen.getByText(/Your Question:/i);
        const questionGroupStyle = window.getComputedStyle(questionLabel.closest('.form-group'));
        expect(questionGroupStyle.marginBottom).toBe('20px');

        // Verify "Rounds per Council Member" section
        expect(screen.getByText(/Rounds per Council Member:/i)).toBeInTheDocument();
        const roundsLabel = screen.getByText(/Rounds per Council Member:/i);
        const roundsGroupStyle = window.getComputedStyle(roundsLabel.closest('.form-group'));
        expect(roundsGroupStyle.marginBottom).toBe('12px'); // .rounds-per-model-section has 12px

        // Cleanup
        document.head.removeChild(style);
    });
});
