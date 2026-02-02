import { render, screen, fireEvent, within } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import WebChatBotWizard from './WebChatBotWizard';

// Mock API
vi.mock('../api', () => ({
    api: {
        runAutomation: vi.fn(),
        getStage2Prompt: vi.fn(),
        updateConversationTitle: vi.fn(),
    },
}));

describe('WebChatBotWizard Markdown Rendering', () => {
    const defaultProps = {
        conversationId: 'markdown-test-123',
        currentTitle: 'Markdown Test',
        llmNames: ['Model A', 'Model B'],
        automationModels: { ai_studio: [], chatgpt: [], claude: [] },
    };

    const draftKey = `web_chatbot_draft_${defaultProps.conversationId}`;

    afterEach(() => {
        localStorage.removeItem(draftKey);
    });

    describe('Modal Preview Markdown Rendering', () => {
        it('renders headings as h1 and h2 elements in modal Preview', () => {
            const savedDraft = {
                step: 1,
                stage1Responses: [
                    { model: 'Model A', response: '# Main Heading\n\nSome text.\n\n## Sub Heading\n\nMore text.' }
                ],
                userQuery: 'Test Query',
            };
            localStorage.setItem(draftKey, JSON.stringify(savedDraft));

            render(<WebChatBotWizard {...defaultProps} />);

            // Click the response item to open modal
            const responseItem = screen.getByText(/Main Heading/);
            fireEvent.click(responseItem);

            // Get modal
            const modal = screen.getByTestId('response-modal');
            expect(modal).toBeInTheDocument();

            // Verify h1 and h2 elements are rendered (not plain text)
            const heading1 = within(modal).getByRole('heading', { level: 1 });
            expect(heading1).toHaveTextContent('Main Heading');

            const heading2 = within(modal).getByRole('heading', { level: 2 });
            expect(heading2).toHaveTextContent('Sub Heading');
        });

        it('renders bold and italic text with proper elements in modal Preview', () => {
            const savedDraft = {
                step: 1,
                stage1Responses: [
                    { model: 'Model A', response: 'This has **bold text** and *italic text* in it.' }
                ],
                userQuery: 'Test Query',
            };
            localStorage.setItem(draftKey, JSON.stringify(savedDraft));

            render(<WebChatBotWizard {...defaultProps} />);

            // Click the response to open modal
            fireEvent.click(screen.getByText(/bold text/));

            const modal = screen.getByTestId('response-modal');

            // Check for strong element (bold)
            const boldElement = within(modal).getByText('bold text');
            expect(boldElement.tagName).toBe('STRONG');

            // Check for em element (italic)
            const italicElement = within(modal).getByText('italic text');
            expect(italicElement.tagName).toBe('EM');
        });

        it('renders unordered lists with ul and li elements in modal Preview', () => {
            const savedDraft = {
                step: 1,
                stage1Responses: [
                    { model: 'Model A', response: 'Here is a list:\n\n- Item One\n- Item Two\n- Item Three' }
                ],
                userQuery: 'Test Query',
            };
            localStorage.setItem(draftKey, JSON.stringify(savedDraft));

            render(<WebChatBotWizard {...defaultProps} />);

            fireEvent.click(screen.getByText(/Item One/));

            const modal = screen.getByTestId('response-modal');

            // Check for list elements
            const list = within(modal).getByRole('list');
            expect(list.tagName).toBe('UL');

            const listItems = within(modal).getAllByRole('listitem');
            expect(listItems).toHaveLength(3);
            expect(listItems[0]).toHaveTextContent('Item One');
            expect(listItems[1]).toHaveTextContent('Item Two');
            expect(listItems[2]).toHaveTextContent('Item Three');
        });

        it('renders numbered lists with ol and li elements in modal Preview', () => {
            const savedDraft = {
                step: 1,
                stage1Responses: [
                    { model: 'Model A', response: 'Ordered list:\n\n1. First\n2. Second\n3. Third' }
                ],
                userQuery: 'Test Query',
            };
            localStorage.setItem(draftKey, JSON.stringify(savedDraft));

            render(<WebChatBotWizard {...defaultProps} />);

            fireEvent.click(screen.getByText(/First/));

            const modal = screen.getByTestId('response-modal');

            // Check for ordered list
            const list = within(modal).getByRole('list');
            expect(list.tagName).toBe('OL');

            const listItems = within(modal).getAllByRole('listitem');
            expect(listItems).toHaveLength(3);
        });
    });

    describe('Write/Preview Toggle Markdown Rendering', () => {
        it('renders markdown as HTML in Step 1 Preview tab', () => {
            const savedDraft = {
                step: 1,
                stage1Responses: [],
                userQuery: 'Test Query',
                currentText: '# Preview Heading\n\n**Bold preview**',
                currentModel: 'Model A',
            };
            localStorage.setItem(draftKey, JSON.stringify(savedDraft));

            render(<WebChatBotWizard {...defaultProps} />);

            // Click Preview tab
            const previewTab = screen.getByRole('button', { name: 'Preview' });
            fireEvent.click(previewTab);

            // Verify heading is rendered as h1
            const heading = screen.getByRole('heading', { level: 1 });
            expect(heading).toHaveTextContent('Preview Heading');

            // Verify bold is rendered as strong
            const bold = screen.getByText('Bold preview');
            expect(bold.tagName).toBe('STRONG');
        });
    });
});
