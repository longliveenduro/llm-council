
import { render } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import WebChatBotWizard from './WebChatBotWizard';

describe('WebChatBotWizard Syntax Check', () => {
    it('should be able to import and render without syntax errors', () => {
        // The act of importing (above) and rendering (below) will catch syntax errors
        expect(WebChatBotWizard).toBeDefined();
        // We catch render crashes here
        expect(() => render(<WebChatBotWizard />)).not.toThrow();
    });
});
