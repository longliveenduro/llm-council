import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import WebChatBotWizard from './WebChatBotWizard';
import { api } from '../api';

// Mock API
vi.mock('../api', () => ({
    api: {
        runAutomation: vi.fn(),
        getStage2Prompt: vi.fn(),
        updateConversationTitle: vi.fn(),
    },
}));

describe('WebChatBotWizard Title Generation', () => {
    const defaultProps = {
        conversationId: 'title-test-123',
        currentTitle: 'New Conversation',
        llmNames: ['Claude 4.5 Sonnet'],
        automationModels: {
            ai_studio: [{ name: 'Gemini Flash Latest', id: 'gfl' }],
            chatgpt: [],
            claude: [],
        },
    };

    beforeEach(() => {
        vi.clearAllMocks();
    });

    it('generates title using Gemini Flash Latest when moving to Stage 2', async () => {
        api.runAutomation.mockResolvedValueOnce({
            response: 'A Great Title',
            thinking_used: false
        });
        api.getStage2Prompt.mockResolvedValueOnce({
            prompt: 'Stage 2 Prompt',
            label_to_model: { 'Response A': 'Claude 4.5 Sonnet' }
        });

        render(<WebChatBotWizard {...defaultProps} />);

        // Type a question
        const questionArea = screen.getByLabelText(/Your Question:/i);
        fireEvent.change(questionArea, { target: { value: 'What is conciousness?' } });

        // Add a response so we can move to Stage 2
        const modelSelect = screen.getByLabelText('Current Model');
        fireEvent.change(modelSelect, { target: { value: 'Claude 4.5 Sonnet' } });

        // Manual entry or automation (mocked)
        fireEvent.click(screen.getByText('Write'));
        const responseArea = screen.getByPlaceholderText('Model Response');
        fireEvent.change(responseArea, { target: { value: 'Test response' } });
        fireEvent.click(screen.getByText('Add Response'));

        // Click Peer Review
        const nextBtn = screen.getByText('Next: Peer Review');
        fireEvent.click(nextBtn);

        await waitFor(() => {
            // Check if title generation was called
            expect(api.runAutomation).toHaveBeenCalledWith(
                expect.stringContaining('Generate a very short title'),
                'Gemini Flash Latest',
                'ai_studio'
            );
        });

        await waitFor(() => {
            expect(api.updateConversationTitle).toHaveBeenCalledWith(
                'title-test-123',
                'A Great Title'
            );
        });
    });
});
