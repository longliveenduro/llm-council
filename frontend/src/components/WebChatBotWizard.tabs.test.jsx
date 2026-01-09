import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import WebChatBotWizard from './WebChatBotWizard';

// Mock API
vi.mock('../api', () => ({
    api: {
        runAutomation: vi.fn(),
    }
}));

describe('WebChatBotWizard Tab Switching', () => {
    const defaultProps = {
        conversationId: 'conv-tabs',
        currentTitle: 'Tab Test',
        llmNames: ['Model A'],
        automationModels: { ai_studio: [], chatgpt: [], claude: [] },
    };

    beforeEach(() => {
        localStorage.clear();
    });

    it('toggles between Write and Preview in Step 1', () => {
        render(<WebChatBotWizard {...defaultProps} />);

        // Step 1: Default is Preview = False (Write mode).
        // Textarea should be visible by default
        const textarea = screen.getByPlaceholderText('Model Response');
        expect(textarea).toBeInTheDocument();

        // Write tab should exist
        const writeBtn = screen.getByText('Write');
        const previewBtn = screen.getByText('Preview');

        // Clicking Preview should show "Nothing to preview"
        fireEvent.click(previewBtn);
        expect(screen.getByText('Nothing to preview')).toBeInTheDocument();
        expect(screen.queryByPlaceholderText('Model Response')).not.toBeInTheDocument();

        // Clicking Write should show Textarea again
        fireEvent.click(writeBtn);
        expect(screen.getByPlaceholderText('Model Response')).toBeInTheDocument();
        expect(screen.queryByText('Nothing to preview')).not.toBeInTheDocument();
    });

    it('toggles between Write and Preview in Step 3', () => {
        const savedDraft = {
            step: 3,
            userQuery: 'Q',
            stage1Responses: [{ model: 'A', response: 'A' }],
            stage2Responses: [{ model: 'A', ranking: 'A' }],
            labelToModel: {},
            stage3Prompt: 'P',
            stage3Response: { model: 'A', response: 'Response' },
        };
        localStorage.setItem(`web_chatbot_draft_${defaultProps.conversationId}`, JSON.stringify(savedDraft));

        render(<WebChatBotWizard {...defaultProps} />);

        // Step 3: Default is Preview = False (Write mode).
        // Should show textarea with value "Response"
        const textarea = screen.getByPlaceholderText('Final answer...');
        expect(textarea).toBeInTheDocument();
        expect(textarea).toHaveValue('Response');

        // Click Preview
        const previewBtn = screen.getByText('Preview');
        fireEvent.click(previewBtn);

        // Should show rendered response "Response" via ReactMarkdown
        expect(screen.getByText('Response')).toBeInTheDocument();
        expect(screen.queryByPlaceholderText('Final answer...')).not.toBeInTheDocument();
    });
});
