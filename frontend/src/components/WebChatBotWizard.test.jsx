import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import WebChatBotWizard from './WebChatBotWizard';
import { api } from '../api';

// Re-expose calculateCurrentScores for testing if needed, or just let the wizard do its thing

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
        llmNames: ['Claude 4.6 Sonnet', 'Gemini 3 Pro'],
        automationModels: {
            ai_studio: [{ name: 'Gemini 3 Pro', id: 'gemini-3-pro' }],
            chatgpt: [],
            claude: [{ name: 'Claude 4.6 Sonnet', id: 'claude-3-5-sonnet' }],
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

        // Select Claude 4.6 Sonnet
        const modelSelect = screen.getByLabelText('Current Model');
        fireEvent.change(modelSelect, { target: { value: 'Claude 4.6 Sonnet' } });

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
        fireEvent.change(modelSelect, { target: { value: 'Claude 4.6 Sonnet' } });

        // Click Run via Claude
        const claudeBtn = screen.getByText('Run via Claude');
        fireEvent.click(claudeBtn);

        await waitFor(() => {
            expect(api.runAutomation).toHaveBeenCalledWith(
                expect.stringContaining('How are you?'),
                'Claude 4.6 Sonnet [Ext. Thinking]',
                'claude',
                null,
                []
            );
        });

        // Click Write tab to see the textarea
        fireEvent.click(screen.getByText('Write'));

        // Check if response is displayed
        const responseArea = screen.getByPlaceholderText('Response by LLM will go here...');
        expect(responseArea).toHaveValue('Claude says hello');
    });


    it('calls api.runAutomation with thinking model name when Claude is selected', async () => {
        api.runAutomation.mockResolvedValue({ response: 'Thinking results' });
        render(<WebChatBotWizard {...defaultProps} />);

        // Type a question
        const questionArea = screen.getByLabelText(/Your Question:/i);
        fireEvent.change(questionArea, { target: { value: 'Deep thought query' } });

        // Select Claude 4.6 Sonnet from current model dropdown
        const modelSelect = screen.getByLabelText('Current Model');
        fireEvent.change(modelSelect, { target: { value: 'Claude 4.6 Sonnet' } });

        // Click Run via Claude
        const claudeBtn = screen.getByText('Run via Claude');
        fireEvent.click(claudeBtn);

        await waitFor(() => {
            expect(api.runAutomation).toHaveBeenCalledWith(
                expect.any(String),
                'Claude 4.6 Sonnet [Ext. Thinking]',
                'claude',
                null,
                []
            );
        });
    });

    it('does not double-append thinking when model name already contains it', async () => {
        api.runAutomation.mockResolvedValue({ response: 'Already thinking' });

        // Add a thinking model to lllmNames for this test
        const propsWithThinking = {
            ...defaultProps,
            llmNames: ['Claude 4.6 Sonnet [Ext. Thinking]', ...defaultProps.llmNames]
        };
        render(<WebChatBotWizard {...propsWithThinking} />);

        // Select a model that already has "Thinking" in the name
        const modelSelect = screen.getByLabelText('Current Model');
        fireEvent.change(modelSelect, { target: { value: 'Claude 4.6 Sonnet [Ext. Thinking]' } });

        // Type a question
        const questionArea = screen.getByLabelText(/Your Question:/i);
        fireEvent.change(questionArea, { target: { value: 'Test query' } });

        // Click Run via Claude
        const claudeBtn = screen.getByText('Run via Claude');
        fireEvent.click(claudeBtn);

        await waitFor(() => {
            expect(api.runAutomation).toHaveBeenCalledWith(
                expect.any(String),
                'Claude 4.6 Sonnet [Ext. Thinking]',
                'claude',
                null,
                []
            );
        });
    });
});

describe('WebChatBotWizard Stage 3 Preselection', () => {
    const defaultProps = {
        conversationId: 'conv-456',
        currentTitle: 'New Conversation',
        llmNames: ['Model A', 'Model B', 'Model C'],
        automationModels: {
            ai_studio: [],
            chatgpt: [],
            claude: [],
        },
    };

    it('preselects the winner from Stage 2 and shows explanation', async () => {
        const savedDraft = {
            step: 2,
            stage1Responses: [
                { model: 'Model A', response: 'A' },
                { model: 'Model B', response: 'B' },
            ],
            labelToModel: {
                'Response A': 'Model A',
                'Response B': 'Model B',
            },
            stage2Responses: [
                { model: 'Model A', ranking: 'FINAL RANKING:\n1. Response B\n2. Response A' },
            ],
            userQuery: 'Which is better?',
        };

        // Mock API responses for handleGoToStep3
        api.processRankings = vi.fn().mockResolvedValue({
            stage2_results: savedDraft.stage2Responses,
            aggregate_rankings: []
        });
        api.getStage3Prompt = vi.fn().mockResolvedValue({ prompt: 'Stage 3 Prompt' });

        const draftKey = `web_chatbot_draft_${defaultProps.conversationId}`;
        localStorage.setItem(draftKey, JSON.stringify(savedDraft));

        render(<WebChatBotWizard {...defaultProps} />);

        // Click "Next: Synthesis"
        const nextBtn = screen.getByText(/Next: Synthesis/);
        fireEvent.click(nextBtn);

        await waitFor(() => {
            expect(screen.getByText('Step 3: Synthesis')).toBeInTheDocument();
        });

        // Verify Model B is preselected (it won the ranking from Model A)
        const modelSelect = screen.getByDisplayValue('Model B');
        expect(modelSelect).toBeInTheDocument();

        // Verify explanation text
        const explanation = screen.getByText(/Model "Model B" was preselected because it had the highest scores in Stage 2/i);
        expect(explanation).toBeInTheDocument();

        localStorage.removeItem(draftKey);
    });
});


describe('WebChatBotWizard UI Changes - Thinking Status', () => {
    const defaultProps = {
        conversationId: 'test-conv-123',
        currentTitle: 'New Conversation',
        llmNames: ['GPT-4o', 'Claude 4.6 Sonnet', 'Gemini 2.5 Flash'],
        automationModels: {
            ai_studio: [{ name: 'Gemini 2.5 Flash', id: 'gemini-flash' }],
            chatgpt: [{ name: 'GPT-4o', id: 'gpt-4o' }],
            claude: [{ name: 'Claude 4.6 Sonnet', id: 'claude-sonnet' }],
        },
    };

    beforeEach(() => {
        vi.clearAllMocks();
        localStorage.clear();
    });

    it('does not include a Custom option in the model dropdown', () => {
        render(<WebChatBotWizard {...defaultProps} />);

        const modelSelect = screen.getByRole('combobox', { name: /current model/i });

        // Get all options
        const options = Array.from(modelSelect.querySelectorAll('option'));
        const optionValues = options.map(opt => opt.value);
        const optionTexts = options.map(opt => opt.textContent);

        // Verify no Custom option
        expect(optionValues).not.toContain('custom');
        expect(optionTexts).not.toContain('Custom...');
    });

    it('shows "Select Model..." as default option when no model selected', () => {
        render(<WebChatBotWizard {...defaultProps} />);

        // The first option should be "Select Model..."
        const modelSelect = screen.getByRole('combobox', { name: /current model/i });
        const firstOption = modelSelect.querySelector('option:first-child');

        expect(firstOption.textContent).toBe('Select Model...');
    });

    it('shows thinking indicator when automation returns thinking_used=true', async () => {
        api.runAutomation = vi.fn().mockResolvedValue({
            response: 'Test response',
            thinking_used: true
        });

        render(<WebChatBotWizard {...defaultProps} />);

        // Type a prompt in the user query textarea
        const promptInput = screen.getByLabelText(/Your Question:/i);
        fireEvent.change(promptInput, { target: { value: 'Test question' } });

        // Select Claude model to show Claude button
        const modelSelect = screen.getByLabelText('Current Model');
        fireEvent.change(modelSelect, { target: { value: 'Claude 4.6 Sonnet' } });

        // Click the Claude automation button
        const claudeBtn = screen.getByText('Run via Claude');
        fireEvent.click(claudeBtn);

        await waitFor(() => {
            // Check for thinking indicator by looking for the span element
            const thinkingIndicator = document.querySelector('.thinking-indicator.thinking-on');
            expect(thinkingIndicator).toBeInTheDocument();
        });
    });

    it('shows "No Thinking" indicator when automation returns thinking_used=false', async () => {
        api.runAutomation = vi.fn().mockResolvedValue({
            response: 'Test response',
            thinking_used: false
        });

        render(<WebChatBotWizard {...defaultProps} />);

        // Type a prompt in the user query textarea
        const promptInput = screen.getByLabelText(/Your Question:/i);
        fireEvent.change(promptInput, { target: { value: 'Test question' } });

        // Select Gemini model to show AI Studio button
        const modelSelect = screen.getByLabelText('Current Model');
        fireEvent.change(modelSelect, { target: { value: 'Gemini 2.5 Flash' } });

        // Click the AI Studio automation button
        const aiStudioBtn = screen.getByText('Run via AI Studio');
        fireEvent.click(aiStudioBtn);

        await waitFor(() => {
            // Check for no thinking indicator
            const indicator = document.querySelector('.thinking-indicator.thinking-off');
            expect(indicator).toBeInTheDocument();
        });
    });

    it('adds Thinking suffix to Claude model name when thinking_used is true', async () => {
        api.runAutomation = vi.fn().mockResolvedValue({
            response: 'Claude response',
            thinking_used: true
        });

        const draftKey = `web_chatbot_draft_${defaultProps.conversationId}`;
        localStorage.setItem(draftKey, JSON.stringify({ userQuery: 'Test query' }));

        render(<WebChatBotWizard {...defaultProps} />);

        // Type a prompt in the user query textarea
        const promptInput = screen.getByLabelText(/Your Question:/i);
        fireEvent.change(promptInput, { target: { value: 'Test question' } });

        // Select Claude model to show Claude button
        const modelSelect = screen.getByLabelText('Current Model');
        fireEvent.change(modelSelect, { target: { value: 'Claude 4.6 Sonnet' } });

        // Click the Claude automation button
        const claudeBtn = screen.getByText('Run via Claude');
        fireEvent.click(claudeBtn);

        await waitFor(() => {
            // Response should be in the response textarea
            expect(screen.getByDisplayValue('Claude response')).toBeInTheDocument();
        });

        // Click "Add Response"
        const addBtn = screen.getByText('Add Response');
        fireEvent.click(addBtn);

        // Check the responses list for the model name with Thinking suffix
        await waitFor(() => {
            const elements = screen.getAllByText(/Claude 4.6 Sonnet \[Ext. Thinking\]/i);
            expect(elements.length).toBeGreaterThan(0);
        });

        localStorage.removeItem(draftKey);
    });

    it('does not add Thinking suffix when thinking_used is false', async () => {
        api.runAutomation = vi.fn().mockResolvedValue({
            response: 'Gemini response',
            thinking_used: false
        });

        const draftKey = `web_chatbot_draft_${defaultProps.conversationId}`;
        localStorage.setItem(draftKey, JSON.stringify({ userQuery: 'Test query' }));

        render(<WebChatBotWizard {...defaultProps} />);

        // Type a prompt in the user query textarea
        const promptInput = screen.getByLabelText(/Your Question:/i);
        fireEvent.change(promptInput, { target: { value: 'Test question' } });

        // Select Gemini model
        const modelSelect = screen.getByLabelText('Current Model');
        fireEvent.change(modelSelect, { target: { value: 'Gemini 2.5 Flash' } });

        // Click the AI Studio automation button
        const aiStudioBtn = screen.getByText('Run via AI Studio');
        fireEvent.click(aiStudioBtn);

        await waitFor(() => {
            // Response should be in the response textarea
            expect(screen.getByDisplayValue('Gemini response')).toBeInTheDocument();
        });

        // Click "Add Response"
        const addBtn = screen.getByText('Add Response');
        fireEvent.click(addBtn);

        // Check the responses list - model name should NOT have Thinking suffix
        await waitFor(() => {
            const responsesList = document.querySelector('.responses-list');
            expect(responsesList).toBeInTheDocument();
            expect(responsesList.textContent).toContain('Gemini 2.5 Flash');
            expect(responsesList.textContent).not.toContain('Thinking');
        });

        localStorage.removeItem(draftKey);
    });
});



describe('WebChatBotWizard Gemini Reference Display', () => {
    const defaultProps = {
        conversationId: 'test-conv-refs',
        currentTitle: 'New Conversation',
        llmNames: ['Gemini 3 Pro'],
        automationModels: {
            ai_studio: [{ name: 'Gemini 3 Pro', id: 'gemini-3-pro' }],
            chatgpt: [],
            claude: [],
        },
    };

    it('correctly renders Gemini references in the preview tab', async () => {
        const geminiResponse = "Main response with a footnote [1].\n\n---\n#### Sources\n[1] https://source.com";
        api.runAutomation.mockResolvedValue({
            response: geminiResponse,
            thinking_used: false
        });

        render(<WebChatBotWizard {...defaultProps} />);

        // Type a prompt
        const promptInput = screen.getByLabelText(/Your Question:/i);
        fireEvent.change(promptInput, { target: { value: 'Test references' } });

        // Select Gemini model
        const modelSelect = screen.getByLabelText('Current Model');
        fireEvent.change(modelSelect, { target: { value: 'Gemini 3 Pro' } });

        // Click run
        const aiStudioBtn = screen.getByText('Run via AI Studio');
        fireEvent.click(aiStudioBtn);

        await waitFor(() => {
            // Check in the Write tab first (textarea)
            const textArea = screen.getByPlaceholderText('Response by LLM will go here...');
            expect(textArea.value).toContain('---');
            expect(textArea.value).toContain('#### Sources');
        });

        // Click Preview tab
        const previewTab = screen.getByText('Preview');
        fireEvent.click(previewTab);

        // In preview tab, it should be rendered. 
        // We check for the text content. 
        await waitFor(() => {
            expect(screen.getByText(/Main response with a footnote/)).toBeInTheDocument();
            // Match the header - level 4 heading for #### Sources
            expect(screen.getByRole('heading', { level: 4 })).toHaveTextContent(/Sources/i);
            // Match the source URL part
            expect(screen.getByText(/https:\/\/source\.com/)).toBeInTheDocument();
        }, { timeout: 3000 });
    });
});
