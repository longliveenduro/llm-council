import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import WebChatBotWizard from './WebChatBotWizard';
import { api } from '../api';

// Mock API
vi.mock('../api', () => ({
    api: {
        runAutomation: vi.fn(),
        getStage2Prompt: vi.fn(),
        processRankings: vi.fn(),
        getStage3Prompt: vi.fn(),
        updateConversationTitle: vi.fn(),
        getImageUrl: vi.fn(img => img),
    },
}));

describe('WebChatBotWizard Scores and Parsing', () => {
    const defaultProps = {
        conversationId: 'conv-scores-123',
        currentTitle: 'New Conversation',
        llmNames: ['Model A', 'Model B'],
        automationModels: {
            ai_studio: [{ name: 'Model A', id: 'a' }],
            chatgpt: [],
            claude: [],
        },
    };

    beforeEach(() => {
        vi.clearAllMocks();
        localStorage.clear();
    });

    it('correctly parses rankings with multi-round labels (A1, B1)', async () => {
        // We need to simulate being in Step 2 with some multi-round responses
        const savedDraft = {
            step: 2,
            userQuery: 'Test query',
            stage1Responses: [
                { model: 'Model A', response: 'Response A1' },
                { model: 'Model A', response: 'Response A2' },
                { model: 'Model B', response: 'Response B1' },
            ],
            labelToModel: {
                'Response A1': 'Model A',
                'Response A2': 'Model A',
                'Response B1': 'Model B',
            },
            stage2Responses: [],
            stage2Prompt: 'Review these...',
        };

        const draftKey = `web_chatbot_draft_${defaultProps.conversationId}`;
        localStorage.setItem(draftKey, JSON.stringify(savedDraft));

        render(<WebChatBotWizard {...defaultProps} />);

        // Add a ranking manually
        const modelSelect = screen.getByLabelText('Current Model');
        fireEvent.change(modelSelect, { target: { value: 'Model A' } });

        const rankingText = "FINAL RANKING:\n1. Response B1\n2. Response A1\n3. Response A2";
        const pasteArea = screen.getByPlaceholderText('Paste Ranking');
        fireEvent.change(pasteArea, { target: { value: rankingText } });

        fireEvent.click(screen.getByText('Add Ranking'));

        // The "Mapping" box should now show the scores
        await waitFor(() => {
            // Model B was 1st, Model A was 2nd and 3rd
            // Model B avg: 1.0, Model A avg: (2+3)/2 = 2.5

            // Labels in MappingBox strip 'Response ' so 'Response B1' becomes 'Model B1'
            const modelBItem = screen.getByText('Model B1').closest('.mapping-item');
            expect(modelBItem.textContent).toContain('1');

            const modelA1Item = screen.getByText('Model A1').closest('.mapping-item');
            expect(modelA1Item.textContent).toContain('2.5');

            const modelA2Item = screen.getByText('Model A2').closest('.mapping-item');
            expect(modelA2Item.textContent).toContain('2.5');
        });
    });

    it('shows the Aggregate Rankings (Street Cred) box in Stage 2', async () => {
        const savedDraft = {
            step: 2,
            userQuery: 'Test query',
            stage1Responses: [{ model: 'Model A', response: 'A' }],
            labelToModel: { 'Response A': 'Model A' },
            stage2Responses: [{ model: 'Model A', ranking: 'FINAL RANKING:\n1. Response A' }],
            aggregateRankings: [{ model: 'Model A', average_rank: 1.0, rankings_count: 1 }],
            stage2Prompt: 'Review...',
        };

        const draftKey = `web_chatbot_draft_${defaultProps.conversationId}`;
        localStorage.setItem(draftKey, JSON.stringify(savedDraft));

        render(<WebChatBotWizard {...defaultProps} />);

        expect(screen.getByText('Aggregate Rankings (Street Cred)')).toBeInTheDocument();
        expect(screen.getByText('Avg: 1.00')).toBeInTheDocument();
        expect(screen.getByText('(1 votes)')).toBeInTheDocument();
    });

    it('shows the Mapping and Aggregate Rankings boxes in Stage 3', async () => {
        const savedDraft = {
            step: 3,
            userQuery: 'Test query',
            stage1Responses: [{ model: 'Model A', response: 'A' }],
            labelToModel: { 'Response A': 'Model A' },
            stage2Responses: [{ model: 'Model A', ranking: 'FINAL RANKING:\n1. Response A' }],
            aggregateRankings: [{ model: 'Model A', average_rank: 1.0, rankings_count: 1 }],
            stage3Prompt: 'Synthesize...',
            stage3Response: { model: 'Model A', response: '' }
        };

        const draftKey = `web_chatbot_draft_${defaultProps.conversationId}`;
        localStorage.setItem(draftKey, JSON.stringify(savedDraft));

        render(<WebChatBotWizard {...defaultProps} />);

        // In Stage 3
        expect(screen.getByText('Mapping:')).toBeInTheDocument();
        expect(screen.getByText('Aggregate Rankings (Street Cred)')).toBeInTheDocument();
        expect(screen.getByText('Avg: 1.00')).toBeInTheDocument();
    });
});
