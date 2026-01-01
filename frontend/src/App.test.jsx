import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import App from './App';

// Mock the API module
vi.mock('./api', () => ({
    api: {
        listConversations: vi.fn(() => Promise.resolve([])),
        getAutomationStatus: vi.fn(() => Promise.resolve({ ai_studio: false, chatgpt: false })),
        getAutomationModels: vi.fn(() => Promise.resolve([])),
    },
}));

describe('App', () => {
    it('renders without crashing and shows the sidebar', async () => {
        render(<App />);

        // Check if Sidebar elements are present
        // For example, the "New Conversation" button
        const newConvButtons = screen.getAllByText(/New Conversation/i);
        expect(newConvButtons.length).toBeGreaterThan(0);

        // Check if the empty state message is shown in the main pane
        expect(screen.getByText(/Create a new conversation to get started/i)).toBeInTheDocument();
    });
});
