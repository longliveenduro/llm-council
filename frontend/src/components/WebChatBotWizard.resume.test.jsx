import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import WebChatBotWizard from './WebChatBotWizard';
import { api } from '../api';

vi.mock('../api', () => ({
    api: {
        runAutomation: vi.fn(),
        getStage2Prompt: vi.fn(),
        updateConversationTitle: vi.fn(),
    },
}));

describe('WebChatBotWizard Resume Logic', () => {
    const defaultProps = {
        conversationId: 'conv-resume',
        currentTitle: 'Resume Conv',
        llmNames: ['Gemini'],
        automationModels: { ai_studio: [{ name: 'Gemini', id: 'g' }], chatgpt: [], claude: [] },
    };

    beforeEach(() => {
        vi.clearAllMocks();
        // Clear local storage draft
        localStorage.removeItem(`web_chatbot_draft_${defaultProps.conversationId}`);
    });

    it('uses dangling user message as current question and excludes it from context', async () => {
        api.runAutomation.mockResolvedValue({ response: 'Test Response' });

        const previousMessages = [
            { role: 'user', content: 'Q1' },
            { role: 'assistant', content: 'A1', stage3: { response: 'A1' } },
            { role: 'user', content: 'Dangling Q' } // This is what we are resuming
        ];

        render(<WebChatBotWizard {...defaultProps} previousMessages={previousMessages} />);

        // 1. Verify userQuery is populated
        const questionArea = screen.getByLabelText(/Your Question:/i);
        expect(questionArea).toHaveValue('Dangling Q');

        // 2. Trigger automation to check context
        const runBtn = screen.getByText('Run via AI Studio');
        fireEvent.click(runBtn);

        await waitFor(() => {
            expect(api.runAutomation).toHaveBeenCalled();
            const lastCallArgs = api.runAutomation.mock.calls[0];
            const prompt = lastCallArgs[0];

            // Should contain Q1 and A1 in history
            expect(prompt).toContain('User Question 1: Q1');
            expect(prompt).toContain('LLM Answer 1: A1');

            // Should contain Dangling Q as Current Question
            expect(prompt).toContain('Current Question: Dangling Q');

            // Should NOT contain "User Question 2: Dangling Q" in the history context
            // "Context so far" loop logic should have skipped it
            expect(prompt).not.toContain('User Question 2: Dangling Q');
        });
    });

    it('handles normal continuation correctly (no dangling message)', async () => {
        api.runAutomation.mockResolvedValue({ response: 'Test Response' });

        const previousMessages = [
            { role: 'user', content: 'Q1' },
            { role: 'assistant', content: 'A1', stage3: { response: 'A1' } }
        ];

        render(<WebChatBotWizard {...defaultProps} previousMessages={previousMessages} />);

        // 1. Verify userQuery is empty (prompts for new question)
        const questionArea = screen.getByLabelText(/Your Question:/i);
        expect(questionArea).toHaveValue('');

        // 2. Enter new question
        fireEvent.change(questionArea, { target: { value: 'New Q' } });

        // 3. Trigger automation
        const runBtn = screen.getByText('Run via AI Studio');
        fireEvent.click(runBtn);

        await waitFor(() => {
            const lastCallArgs = api.runAutomation.mock.calls[0];
            const prompt = lastCallArgs[0];

            expect(prompt).toContain('User Question 1: Q1');
            expect(prompt).toContain('LLM Answer 1: A1');
            expect(prompt).toContain('Current Question: New Q');
        });
    });

    it('omits "Current Question:" prefix for the very first message', async () => {
        api.runAutomation.mockResolvedValue({ response: 'Test Response' });
        const previousMessages = []; // No history

        render(<WebChatBotWizard {...defaultProps} previousMessages={previousMessages} />);

        const questionArea = screen.getByLabelText(/Your Question:/i);
        fireEvent.change(questionArea, { target: { value: 'First Question' } });

        const runBtn = screen.getByText('Run via AI Studio');
        fireEvent.click(runBtn);

        await waitFor(() => {
            expect(api.runAutomation).toHaveBeenCalled();
            const lastCallArgs = api.runAutomation.mock.calls[0];
            const prompt = lastCallArgs[0];

            // Should just be the question, no prefix, no context header
            expect(prompt).toBe('First Question');
        });
    });

    it('filters out dangling user message when calling getStage2Prompt', async () => {
        // Mock getStage2Prompt response
        api.getStage2Prompt.mockResolvedValue({
            prompt: 'Stage 2 Prompt',
            label_to_model: { 'Response A': 'TestModel' }
        });

        const previousMessages = [
            { role: 'user', content: 'Q1' },
            { role: 'assistant', content: 'A1', stage3: { response: 'A1' } },
            { role: 'user', content: 'Dangling Q' }
        ];

        render(<WebChatBotWizard {...defaultProps} previousMessages={previousMessages} />);

        // Verify dangling message is in input
        const questionArea = screen.getByLabelText(/Your Question:/i);
        expect(questionArea).toHaveValue('Dangling Q');

        // Add a dummy response to enable "Next"
        // 1. Select Write tab (id or text?)
        fireEvent.click(screen.getByText('Write'));

        // 2. Enter response
        const responseArea = screen.getByPlaceholderText('Response by LLM will go here...');
        fireEvent.change(responseArea, { target: { value: 'Test Response Content' } });

        // 3. Add response
        fireEvent.click(screen.getByText('Add Response'));

        // 4. Click Next
        const nextBtn = screen.getByText('Next: Peer Review →');
        fireEvent.click(nextBtn);

        await waitFor(() => {
            expect(api.getStage2Prompt).toHaveBeenCalled();
            const lastCallArgs = api.getStage2Prompt.mock.calls[0];
            // Args: userQuery, stage1Responses, previousMessages
            const passedHistory = lastCallArgs[2];

            // Should NOT contain dangling message
            expect(passedHistory).toHaveLength(2); // Q1 and A1 only
            expect(passedHistory[0].content).toBe('Q1');
            expect(passedHistory[1].content).toBe('A1');
        });
    });
});
