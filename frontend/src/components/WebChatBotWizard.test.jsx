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

describe('WebChatBotWizard Claude Integration', () => {
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

    it('shows and enables the correct button when a model is selected', () => {
        render(<WebChatBotWizard {...defaultProps} />);

        // Type a question
        const questionArea = screen.getByLabelText(/Your Question:/i);
        fireEvent.change(questionArea, { target: { value: 'Test query' } });

        // Select Claude 3.5 Sonnet
        const modelSelect = screen.getByLabelText('Current Model');
        fireEvent.change(modelSelect, { target: { value: 'Claude 3.5 Sonnet' } });

        const claudeBtn = screen.getByText('Run via Claude');
        expect(claudeBtn).not.toBeDisabled();
        expect(screen.queryByText('Run via AI Studio')).not.toBeInTheDocument();
        expect(screen.queryByText('Run via ChatGPT')).not.toBeInTheDocument();

        // Select Gemini 2.5 Flash (default automation model if currentModel is cleared, but here we test explicit selection)
        fireEvent.change(modelSelect, { target: { value: 'Gemini 3 Pro' } });
        const aiStudioBtn = screen.getByText('Run via AI Studio');
        expect(aiStudioBtn).not.toBeDisabled();
        expect(screen.queryByText('Run via Claude')).not.toBeInTheDocument();
    });

    it('calls api.runAutomation with "claude" provider when clicking Run via Claude', async () => {
        api.runAutomation.mockResolvedValue({ response: 'Claude says hello' });
        render(<WebChatBotWizard {...defaultProps} />);

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
                'Claude 3.5 Sonnet [Ext. Thinking]',
                'claude'
            );
        });

        // Check if response is displayed
        const responseArea = screen.getByPlaceholderText('Model Response');
        expect(responseArea).toHaveValue('Claude says hello');
    });


    it('calls api.runAutomation with thinking model name when Claude is selected', async () => {
        api.runAutomation.mockResolvedValue({ response: 'Thinking results' });
        render(<WebChatBotWizard {...defaultProps} />);

        // Type a question
        const questionArea = screen.getByLabelText(/Your Question:/i);
        fireEvent.change(questionArea, { target: { value: 'Deep thought query' } });

        // Select Claude 3.5 Sonnet from current model dropdown
        const modelSelect = screen.getByLabelText('Current Model');
        fireEvent.change(modelSelect, { target: { value: 'Claude 3.5 Sonnet' } });

        // Click Run via Claude
        const claudeBtn = screen.getByText('Run via Claude');
        fireEvent.click(claudeBtn);

        await waitFor(() => {
            expect(api.runAutomation).toHaveBeenCalledWith(
                expect.any(String),
                'Claude 3.5 Sonnet [Ext. Thinking]',
                'claude'
            );
        });
    });

    it('does not double-append thinking when model name already contains it', async () => {
        api.runAutomation.mockResolvedValue({ response: 'Already thinking' });

        // Add a thinking model to lllmNames for this test
        const propsWithThinking = {
            ...defaultProps,
            llmNames: ['Claude 3.5 Sonnet [Ext. Thinking]', ...defaultProps.llmNames]
        };
        render(<WebChatBotWizard {...propsWithThinking} />);

        // Select a model that already has "Thinking" in the name
        const modelSelect = screen.getByLabelText('Current Model');
        fireEvent.change(modelSelect, { target: { value: 'Claude 3.5 Sonnet [Ext. Thinking]' } });

        // Type a question
        const questionArea = screen.getByLabelText(/Your Question:/i);
        fireEvent.change(questionArea, { target: { value: 'Test query' } });

        // Click Run via Claude
        const claudeBtn = screen.getByText('Run via Claude');
        fireEvent.click(claudeBtn);

        await waitFor(() => {
            expect(api.runAutomation).toHaveBeenCalledWith(
                expect.any(String),
                'Claude 3.5 Sonnet [Ext. Thinking]',
                'claude'
            );
        });
    });
});
