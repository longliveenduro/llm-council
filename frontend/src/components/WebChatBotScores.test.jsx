import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import WebChatBotWizard from './WebChatBotWizard';

// Mock getModelIcon
import * as modelIcons from '../utils/modelIcons';
import React from 'react';
import { api } from '../api';

vi.mock('../api', () => ({
    api: {
        runAutomation: vi.fn(),
        getStage2Prompt: vi.fn(),
        updateConversationTitle: vi.fn(),
    },
}));

vi.mock('../utils/modelIcons', () => ({
    getModelIcon: vi.fn(() => 'test-icon.png'),
}));

describe('WebChatBotWizard Scoring Logic', () => {
    const defaultProps = {
        conversationId: 'conv-123',
        currentTitle: 'New Conversation',
        llmNames: ['Model A', 'Model B', 'Model C'],
        automationModels: {
            ai_studio: [],
            chatgpt: [],
            claude: [],
        },
    };

    it('calculates and displays scores in Stage 2 mapping area', async () => {
        const savedDraft = {
            step: 2,
            stage1Responses: [
                { model: 'Model A', response: 'A response' },
                { model: 'Model B', response: 'B response' },
                { model: 'Model C', response: 'C response' },
            ],
            labelToModel: {
                'Response A': 'Model A',
                'Response B': 'Model B',
                'Response C': 'Model C',
            },
            stage2Responses: [
                { model: 'Model A', ranking: 'FINAL RANKING:\n1. Response A\n2. Response B\n3. Response C' },
                { model: 'Model B', ranking: 'FINAL RANKING:\n1. Response B\n2. Response A\n3. Response C' },
            ],
            userQuery: 'Test question',
        };

        // Mock localStorage to load the draft
        const draftKey = `web_chatbot_draft_${defaultProps.conversationId}`;
        localStorage.setItem(draftKey, JSON.stringify(savedDraft));

        render(<WebChatBotWizard {...defaultProps} />);

        // Verify Average Ranks:
        // Model A: (1 + 2) / 2 = 1.5
        // Model B: (2 + 1) / 2 = 1.5
        // Model C: (3 + 3) / 2 = 3

        // Both Model A and B should have Gold medals because they tie for rank 1 (1.5)
        // Model C should have Bronze medal because it's rank 3. Wait, let's check tie logic.
        // aggregate.sort((a, b) => a.avgRank - b.avgRank);
        // currentRankIndex = i; if item.avgRank > aggregate[i-1].avgRank
        // i=0: index=0, medal=🥇 (Model A)
        // i=1: index=0, medal=🥇 (Model B)
        // i=2: index=2, medal=🥉 (Model C)

        // Let's check if 1.5 is displayed
        const scoreElements = screen.getAllByText('1.5');
        expect(scoreElements).toHaveLength(2);

        const scoreC = screen.getByText('3');
        expect(scoreC).toBeInTheDocument();

        // Check for medals
        const goldMedals = screen.getAllByText('🥇');
        expect(goldMedals).toHaveLength(2);

        const bronzeMedal = screen.getByText('🥉');
        expect(bronzeMedal).toBeInTheDocument();

        localStorage.removeItem(draftKey);
    });
});
