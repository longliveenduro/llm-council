import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import WebChatBotWizard from './WebChatBotWizard';
import { api } from '../api';
import fs from 'fs';
import path from 'path';

// Mock API
vi.mock('../api', () => ({
    api: {
        runAutomation: vi.fn(),
        getStage2Prompt: vi.fn(),
        processRankings: vi.fn(),
        getStage3Prompt: vi.fn(),
        updateConversationTitle: vi.fn(),
    },
}));

describe('WebChatBotWizard Layout', () => {
    const defaultProps = {
        conversationId: 'conv-layout-test',
        currentTitle: 'Layout Test',
        llmNames: ['Model A', 'Model B'],
        automationModels: { ai_studio: [], chatgpt: [], claude: [] },
    };

    it('Stage 3 synthesis section has correct flex properties for scrolling', async () => {
        // Setup state for Stage 3
        const savedDraft = {
            step: 3,
            stage1Responses: [{ model: 'Model A', response: 'A' }],
            labelToModel: { 'Response A': 'Model A' },
            stage2Responses: [{ model: 'Model A', ranking: '1. Response A' }],
            stage3Prompt: 'Final Prompt',
            stage3Response: { model: 'Model A', response: 'Response' },
            userQuery: 'Query',
        };

        const draftKey = `web_chatbot_draft_${defaultProps.conversationId}`;
        localStorage.setItem(draftKey, JSON.stringify(savedDraft));

        // Inject CSS manually for JSDOM
        const cssPath = path.resolve(__dirname, 'WebChatBotWizard.css');
        const cssContent = fs.readFileSync(cssPath, 'utf8');
        const style = document.createElement('style');
        style.innerHTML = cssContent;
        document.head.appendChild(style);

        const { container } = render(<WebChatBotWizard {...defaultProps} />);

        const section = container.querySelector('.stage3-synthesis-section');
        expect(section).toBeInTheDocument();

        const styles = window.getComputedStyle(section);
        // This is the specific fix we are looking for:
        expect(styles.minHeight).toMatch(/^0(px)?$/);

        // Cleanup
        localStorage.removeItem(draftKey);
        document.head.removeChild(style);
    });
});
