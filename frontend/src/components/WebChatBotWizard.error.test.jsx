import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import WebChatBotWizard from './WebChatBotWizard';
import { api } from '../api';

// Mock the API
vi.mock('../api', () => ({
    api: {
        runAutomation: vi.fn(),
        updateConversationTitle: vi.fn(),
        getImageUrl: vi.fn((img) => img),
        uploadImage: vi.fn()
    }
}));

describe('WebChatBotWizard Error Handling', () => {
    const defaultProps = {
        conversationId: 'test-conv',
        currentTitle: 'New Conversation',
        previousMessages: [],
        llmNames: ['GPT-4o', 'Claude 3.5 Sonnet'],
        onComplete: vi.fn(),
        onCancel: vi.fn(),
        automationModels: {
            ai_studio: [{ name: 'Gemini 2.5 Flash', id: 'gemini-1' }],
            chatgpt: [{ name: 'GPT-4o', id: 'gpt-1' }],
            claude: [{ name: 'Claude 3.5 Sonnet', id: 'claude-1' }]
        },
        onTitleUpdate: vi.fn(),
        initialQuestion: 'Hello world'
    };

    beforeEach(() => {
        vi.clearAllMocks();
        // Default success for title generation and other background calls
        api.runAutomation.mockResolvedValue({
            response: 'Test Title',
            error: false,
            error_msgs: null,
            error_type: null
        });
    });

    it('displays error message and disables Add Response button on automation failure', async () => {
        api.runAutomation.mockResolvedValueOnce({
            response: null,
            error_msgs: 'Quota exceeded for file uploads',
            error: true,
            error_type: 'quota_exceeded'
        });

        render(<WebChatBotWizard {...defaultProps} initialQuestion={null} />);

        // Select a model
        const modelSelect = screen.getByLabelText(/Current Model/i);
        fireEvent.change(modelSelect, { target: { value: 'GPT-4o' } });

        // Type a question
        const queryTextarea = screen.getByLabelText(/Your Question:/i);
        fireEvent.change(queryTextarea, { target: { value: 'How are you?' } });

        const runBtn = screen.getByText(/Run via AI Studio/i);
        fireEvent.click(runBtn);

        // Wait for automation to "complete" with error
        await waitFor(() => {
            expect(screen.getAllByText(/Quota exceeded for file uploads/i).length).toBeGreaterThan(0);
        });

        // Check if error indicator is visible
        expect(screen.getByText(/Error in automation/i)).toBeInTheDocument();

        // Add Response button should be disabled
        const addBtn = screen.getByText(/Add Response/i);
        expect(addBtn).toBeDisabled();
    });

    it('resets error state when user edits the text', async () => {
        api.runAutomation.mockResolvedValueOnce({
            response: null,
            error_msgs: 'Some error',
            error: true,
            error_type: 'generic_error'
        });

        render(<WebChatBotWizard {...defaultProps} initialQuestion={null} />);

        // Select a model
        const modelSelect = screen.getByLabelText(/Current Model/i);
        fireEvent.change(modelSelect, { target: { value: 'GPT-4o' } });

        // Type a question
        const queryTextarea = screen.getByLabelText(/Your Question:/i);
        fireEvent.change(queryTextarea, { target: { value: 'How are you?' } });

        const runBtn = screen.getByText(/Run via AI Studio/i);
        fireEvent.click(runBtn);

        await waitFor(() => {
            expect(screen.getAllByText(/Some error/i).length).toBeGreaterThan(0);
        });

        const textarea = screen.getByPlaceholderText(/Paste Model Response here.../i);
        const addBtn = screen.getByText(/Add Response/i);

        expect(addBtn).toBeDisabled();

        // Simulate manual edit
        fireEvent.change(textarea, { target: { value: 'Manual correction' } });

        // Add Response button should now be enabled
        expect(addBtn).not.toBeDisabled();
        expect(screen.queryByText(/Error in automation/i)).not.toBeInTheDocument();
    });
});
