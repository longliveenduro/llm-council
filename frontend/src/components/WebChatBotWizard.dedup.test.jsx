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

describe('WebChatBotWizard Stage 1 Deduplication', () => {
    const defaultProps = {
        conversationId: 'dedup-test-123',
        currentTitle: 'New Conversation',
        llmNames: ['Claude Sonnet 4.5', 'Gemini 3 Pro'],
        automationModels: {
            ai_studio: [{ name: 'Gemini 3 Pro', id: 'gemini-3-pro' }],
            chatgpt: [],
            claude: [{ name: 'Claude Sonnet 4.5', id: 'claude-sonnet-4-5' }],
        },
        onComplete: vi.fn(),
        onCancel: vi.fn(),
    };

    beforeEach(() => {
        vi.clearAllMocks();
        localStorage.clear();
        // Reset window.confirm to auto-accept
        vi.spyOn(window, 'confirm').mockReturnValue(true);
    });

    it('should replace existing response when running same model twice with thinking', async () => {
        // First automation run
        api.runAutomation.mockResolvedValueOnce({
            response: 'First Claude response',
            thinking_used: true
        });
        // Second automation run
        api.runAutomation.mockResolvedValueOnce({
            response: 'Second Claude response',
            thinking_used: true
        });

        render(<WebChatBotWizard {...defaultProps} />);

        // Type a question
        const questionArea = screen.getByLabelText(/Your Question:/i);
        fireEvent.change(questionArea, { target: { value: 'Test query' } });

        // Select Claude model
        const modelSelect = screen.getByLabelText('Current Model');
        fireEvent.change(modelSelect, { target: { value: 'Claude Sonnet 4.5' } });

        // First automation run
        const claudeBtn = screen.getByText('Run via Claude');
        fireEvent.click(claudeBtn);

        await waitFor(() => {
            expect(api.runAutomation).toHaveBeenCalledTimes(1);
        });

        // Wait for response to appear in the textarea
        await waitFor(() => {
            const responseArea = screen.getByPlaceholderText('Model Response');
            expect(responseArea.value).toBe('First Claude response');
        });

        // Add the first response
        const addBtn = screen.getByText('Add Response');
        fireEvent.click(addBtn);

        // Verify first response was added
        await waitFor(() => {
            const responsesList = document.querySelector('.responses-list');
            expect(responsesList.textContent).toContain('Claude Sonnet 4.5 [Ext. Thinking]');
        });

        // Count responses - should be 1
        let responseItems = document.querySelectorAll('.response-item');
        expect(responseItems.length).toBe(1);

        // Re-select Claude model (it gets cleared after adding)
        fireEvent.change(modelSelect, { target: { value: 'Claude Sonnet 4.5' } });

        // Second automation run
        fireEvent.click(screen.getByText('Run via Claude'));

        await waitFor(() => {
            expect(api.runAutomation).toHaveBeenCalledTimes(2);
        });

        // Wait for second response
        await waitFor(() => {
            const responseArea = screen.getByPlaceholderText('Model Response');
            expect(responseArea.value).toBe('Second Claude response');
        });

        // Add the second response - should trigger confirm dialog and REPLACE
        fireEvent.click(screen.getByText('Add Response'));

        // Check that confirm was called with the correct model name (including suffix)
        await waitFor(() => {
            expect(window.confirm).toHaveBeenCalledWith(
                expect.stringContaining('Claude Sonnet 4.5 [Ext. Thinking]')
            );
        });

        // Should still be 1 response, not 2
        responseItems = document.querySelectorAll('.response-item');
        expect(responseItems.length).toBe(1);

        // And it should contain the second response content
        // (We can't check the response content directly since it's truncated in the UI,
        // but we verify the count is correct)
    });

    it('should allow different models to be added without deduplication conflict', async () => {
        // Claude response
        api.runAutomation.mockResolvedValueOnce({
            response: 'Claude response',
            thinking_used: true
        });
        // Gemini response
        api.runAutomation.mockResolvedValueOnce({
            response: 'Gemini response',
            thinking_used: false
        });

        render(<WebChatBotWizard {...defaultProps} />);

        const questionArea = screen.getByLabelText(/Your Question:/i);
        fireEvent.change(questionArea, { target: { value: 'Test query' } });

        // Add Claude response
        const modelSelect = screen.getByLabelText('Current Model');
        fireEvent.change(modelSelect, { target: { value: 'Claude Sonnet 4.5' } });

        fireEvent.click(screen.getByText('Run via Claude'));
        await waitFor(() => {
            expect(screen.getByPlaceholderText('Model Response').value).toBe('Claude response');
        });
        fireEvent.click(screen.getByText('Add Response'));

        // Add Gemini response
        fireEvent.change(modelSelect, { target: { value: 'Gemini 3 Pro' } });
        fireEvent.click(screen.getByText('Run via AI Studio'));
        await waitFor(() => {
            expect(screen.getByPlaceholderText('Model Response').value).toBe('Gemini response');
        });
        fireEvent.click(screen.getByText('Add Response'));

        // Should have 2 different responses
        const responseItems = document.querySelectorAll('.response-item');
        expect(responseItems.length).toBe(2);

        // Confirm should NOT have been called for deduplication
        expect(window.confirm).not.toHaveBeenCalled();
    });

    it('should create separate responses when same model runs with different thinking status', async () => {
        // First run - thinking NOT used
        api.runAutomation.mockResolvedValueOnce({
            response: 'Without thinking',
            thinking_used: false
        });
        // Second run - same model, thinking IS used
        api.runAutomation.mockResolvedValueOnce({
            response: 'With thinking',
            thinking_used: true
        });

        render(<WebChatBotWizard {...defaultProps} />);

        const questionArea = screen.getByLabelText(/Your Question:/i);
        fireEvent.change(questionArea, { target: { value: 'Test' } });

        const modelSelect = screen.getByLabelText('Current Model');
        fireEvent.change(modelSelect, { target: { value: 'Claude Sonnet 4.5' } });

        // First run (without thinking) and add
        fireEvent.click(screen.getByText('Run via Claude'));
        await waitFor(() => {
            expect(screen.getByPlaceholderText('Model Response').value).toBe('Without thinking');
        });
        fireEvent.click(screen.getByText('Add Response'));

        // Verify it was added WITHOUT suffix (thinking_used was false)
        await waitFor(() => {
            const responsesList = document.querySelector('.responses-list');
            expect(responsesList.textContent).toContain('Claude Sonnet 4.5');
        });

        // Should have 1 response
        let responseItems = document.querySelectorAll('.response-item');
        expect(responseItems.length).toBe(1);

        // Re-select and run again WITH thinking
        fireEvent.change(modelSelect, { target: { value: 'Claude Sonnet 4.5' } });
        fireEvent.click(screen.getByText('Run via Claude'));
        await waitFor(() => {
            expect(screen.getByPlaceholderText('Model Response').value).toBe('With thinking');
        });
        fireEvent.click(screen.getByText('Add Response'));

        // Confirm should NOT have been called (these are different responses)
        expect(window.confirm).not.toHaveBeenCalled();

        // Should now have 2 responses (thinking and non-thinking are different)
        responseItems = document.querySelectorAll('.response-item');
        expect(responseItems.length).toBe(2);

        // The responses list should contain both versions
        const responsesList = document.querySelector('.responses-list');
        expect(responsesList.textContent).toContain('Claude Sonnet 4.5');
        expect(responsesList.textContent).toContain('[Ext. Thinking]');
    });
});
