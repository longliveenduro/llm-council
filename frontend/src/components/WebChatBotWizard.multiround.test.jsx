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

describe('WebChatBotWizard Multi-Round Automation', () => {
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
        window.confirm = vi.fn(() => true);
    });

    it('runs multiple rounds automatically and labels them correctly', async () => {
        api.runAutomation.mockResolvedValueOnce({ response: 'Round 1 results', thinking_used: true })
            .mockResolvedValueOnce({ response: 'Round 2 results', thinking_used: true });

        render(<WebChatBotWizard {...defaultProps} />);

        // Type a question
        const questionArea = screen.getByLabelText(/Your Question:/i);
        fireEvent.change(questionArea, { target: { value: 'Compare these rounds' } });

        // Set Rounds per Model to 2
        const roundsInput = screen.getByLabelText(/Rounds per Model/i);
        fireEvent.change(roundsInput, { target: { value: '2' } });
        expect(roundsInput.value).toBe('2');

        // Select Claude 3.5 Sonnet
        const modelSelect = screen.getByLabelText('Current Model');
        fireEvent.change(modelSelect, { target: { value: 'Claude 3.5 Sonnet' } });

        // Click Run via Claude
        const claudeBtn = screen.getByText('Run via Claude');
        fireEvent.click(claudeBtn);

        // Verify it was called twice
        await waitFor(() => {
            expect(api.runAutomation).toHaveBeenCalledTimes(2);
        });

        // Verify labels in the list
        expect(screen.getByText('Model A1:')).toBeInTheDocument();
        expect(screen.getByText('Model A2:')).toBeInTheDocument();

        // Verify Mapping Box (ignoring icons/formatting)
        // Since text is split across <strong> and <span>, we use a custom matcher
        const matchesA1 = (content, element) => {
            const hasText = (node) => node.textContent === "Model A1 = Claude 3.5 Sonnet [Ext. Thinking]";
            const nodeHasText = hasText(element);
            const childrenDontHaveText = Array.from(element.children).every(
                (child) => !hasText(child)
            );
            return nodeHasText && childrenDontHaveText;
        };
        expect(screen.getByText(matchesA1)).toBeInTheDocument();
    });

    it('prompts for overwrite when rerunning multi-round for the same model', async () => {
        api.runAutomation.mockResolvedValue({ response: 'Results', thinking_used: true });
        window.confirm = vi.fn(() => true);

        const simpleProps = {
            ...defaultProps,
            llmNames: ['UniqueClaude'],
            automationModels: {
                ai_studio: [],
                chatgpt: [],
                claude: [{ name: 'UniqueClaude', id: 'unique-claude' }],
            },
        };

        render(<WebChatBotWizard {...simpleProps} />);

        // Setup: Run 2 rounds
        fireEvent.change(screen.getByLabelText(/Rounds per Model/i), { target: { value: '2' } });
        fireEvent.change(screen.getByLabelText(/Your Question:/i), { target: { value: 'Test' } });
        fireEvent.change(screen.getByLabelText('Current Model'), { target: { value: 'UniqueClaude' } });

        fireEvent.click(screen.getByText('Run via Claude'));

        await waitFor(() => {
            expect(api.runAutomation).toHaveBeenCalledTimes(2);
        });

        // Small wait to ensure state settles
        await new Promise(r => setTimeout(r, 100));

        // Rerun
        fireEvent.change(screen.getByLabelText('Current Model'), { target: { value: 'UniqueClaude' } });
        fireEvent.click(screen.getByText('Run via Claude'));

        await waitFor(() => {
            expect(window.confirm).toHaveBeenCalled();
        });

        await waitFor(() => {
            expect(api.runAutomation).toHaveBeenCalledTimes(4);
        });
    });

    it('stops automation if user cancels the overwrite confirmation', async () => {
        api.runAutomation.mockResolvedValue({ response: 'Results', thinking_used: true });
        window.confirm = vi.fn(() => false);

        const stopProps = {
            ...defaultProps,
            llmNames: ['StopClaude'],
            automationModels: {
                ai_studio: [],
                chatgpt: [],
                claude: [{ name: 'StopClaude', id: 'stop-claude' }],
            },
        };

        render(<WebChatBotWizard {...stopProps} />);

        // Setup: Run 2 rounds
        fireEvent.change(screen.getByLabelText(/Rounds per Model/i), { target: { value: '2' } });
        fireEvent.change(screen.getByLabelText(/Your Question:/i), { target: { value: 'Test' } });
        fireEvent.change(screen.getByLabelText('Current Model'), { target: { value: 'StopClaude' } });

        fireEvent.click(screen.getByText('Run via Claude'));

        await waitFor(() => {
            expect(api.runAutomation).toHaveBeenCalledTimes(2);
        });

        // Trigger rerun but cancel
        fireEvent.change(screen.getByLabelText('Current Model'), { target: { value: 'StopClaude' } });
        window.confirm = vi.fn(() => false);
        fireEvent.click(screen.getByText('Run via Claude'));

        await waitFor(() => {
            expect(window.confirm).toHaveBeenCalled();
        });

        // Automation should NOT have run further (still 2 calls total)
        expect(api.runAutomation).toHaveBeenCalledTimes(2);
    });
});
