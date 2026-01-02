import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import ManualWizard from './ManualWizard';
import { api } from '../api';

// Mock API
vi.mock('../api', () => ({
    api: {
        runAutomation: vi.fn(),
        getStage2Prompt: vi.fn(),
        updateConversationTitle: vi.fn(),
    },
}));

describe('ManualWizard Claude Integration', () => {
    const defaultProps = {
        conversationId: 'conv-123',
        currentTitle: 'New Conversation',
        llmNames: ['Claude 3.5 Sonnet', 'Gemini 3 Pro'],
        automationModels: {
            ai_studio: [{ name: 'Gemini 3 Pro', id: 'gemini-3-pro' }],
            chatgpt: [],
            claude: [{ name: 'Claude 3.5 Sonnet', id: 'claude-3-5-sonnet' }],
        },
    };

    beforeEach(() => {
        vi.clearAllMocks();
        // Mock default behavior for automation status
    });

    it('enables the Claude button and disables others when Claude model is selected', () => {
        render(<ManualWizard {...defaultProps} />);

        // Type a question
        const questionArea = screen.getByLabelText(/Your Question:/i);
        fireEvent.change(questionArea, { target: { value: 'Test query' } });

        // Select Claude 3.5 Sonnet from current model dropdown
        const modelSelect = screen.getByLabelText('Current Model');
        fireEvent.change(modelSelect, { target: { value: 'Claude 3.5 Sonnet' } });

        const claudeBtn = screen.getByText('Run via Claude');
        const aiStudioBtn = screen.getByText('Run via AI Studio');
        const chatgptBtn = screen.getByText('Run via ChatGPT');

        expect(claudeBtn).not.toBeDisabled();
        expect(aiStudioBtn).toBeDisabled();
        expect(chatgptBtn).toBeDisabled();
    });

    it('calls api.runAutomation with "claude" provider when clicking Run via Claude', async () => {
        api.runAutomation.mockResolvedValue({ response: 'Claude says hello' });
        render(<ManualWizard {...defaultProps} />);

        // Type a question
        const questionArea = screen.getByLabelText(/Your Question:/i);
        fireEvent.change(questionArea, { target: { value: 'How are you?' } });

        // Select Claude model in the dropdown
        const modelSelect = screen.getByLabelText('Current Model');
        fireEvent.change(modelSelect, { target: { value: 'Claude 3.5 Sonnet' } });

        // Click Run via Claude
        const claudeBtn = screen.getByText('Run via Claude');
        fireEvent.click(claudeBtn);

        await waitFor(() => {
            expect(api.runAutomation).toHaveBeenCalledWith(
                expect.stringContaining('How are you?'),
                'Claude 3.5 Sonnet',
                'claude'
            );
        });

        // Check if response is displayed
        const responseArea = screen.getByPlaceholderText('Model Response');
        expect(responseArea).toHaveValue('Claude says hello');
    });
});
