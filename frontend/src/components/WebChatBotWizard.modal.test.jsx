import { render, screen, fireEvent, within } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import WebChatBotWizard from './WebChatBotWizard';

// Mock API
vi.mock('../api', () => ({
    api: {
        runAutomation: vi.fn(),
        getStage2Prompt: vi.fn(),
        updateConversationTitle: vi.fn(),
    },
}));

describe('WebChatBotWizard Response Modal', () => {
    const defaultProps = {
        conversationId: 'modal-test-123',
        currentTitle: 'Modal Test',
        llmNames: ['Model A', 'Model B'],
        automationModels: { ai_studio: [], chatgpt: [], claude: [] },
    };

    it('opens a modal with Preview/Source tabs when a Stage 1 response is clicked', () => {
        // Setup initial state with one response
        const savedDraft = {
            step: 1,
            stage1Responses: [
                { model: 'Model A', response: 'Test Response with Math: $E=mc^2$' }
            ],
            userQuery: 'Test Query',
        };
        const draftKey = `web_chatbot_draft_${defaultProps.conversationId}`;
        localStorage.setItem(draftKey, JSON.stringify(savedDraft));

        render(<WebChatBotWizard {...defaultProps} />);

        // Verify response item exists
        const responseItem = screen.getByText(/Test Response/);
        expect(responseItem).toBeInTheDocument();

        // Click the response item
        fireEvent.click(responseItem);

        // Verify Modal opens using testId
        const modal = screen.getByTestId('response-modal');
        expect(modal).toBeInTheDocument();

        // Scope queries to the modal
        const { getByRole, getByText, getByDisplayValue } = within(modal);

        // Check header
        expect(getByRole('heading', { name: /Model A\s+Response/i })).toBeInTheDocument();

        // Check tabs
        expect(getByRole('button', { name: 'Preview' })).toBeInTheDocument();
        expect(getByRole('button', { name: 'Source' })).toBeInTheDocument();

        // Check content (Preview mode is default)
        expect(getByText(/Test Response with Math/)).toBeInTheDocument();

        // Switch to Source tab
        fireEvent.click(getByRole('button', { name: 'Source' }));

        // Verify textarea with raw content is present
        const sourceArea = getByDisplayValue('Test Response with Math: $E=mc^2$');
        expect(sourceArea).toBeInTheDocument();
        expect(sourceArea.tagName).toBe('TEXTAREA');

        // Close modal
        fireEvent.click(getByRole('button', { name: '×' }));
        expect(screen.queryByTestId('response-modal')).not.toBeInTheDocument();

        // Cleanup
        localStorage.removeItem(draftKey);
    });
});
