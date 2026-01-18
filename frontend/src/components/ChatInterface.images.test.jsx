import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import ChatInterface from './ChatInterface';
import { api } from '../api';

// Mock API
vi.mock('../api', () => ({
    api: {
        getImageUrl: vi.fn((path) => {
            if (!path) return '';
            if (path.startsWith('http') || path.startsWith('data:')) return path;
            return `http://localhost:8001${path.startsWith('/') ? path : '/' + path}`;
        }),
    },
}));

// Mock scrollIntoView as it's not implemented in JSDOM
window.HTMLElement.prototype.scrollIntoView = vi.fn();

describe('ChatInterface Image Rendering', () => {
    const defaultProps = {
        conversation: {
            id: 'conv-123',
            messages: [
                {
                    role: 'user',
                    content: 'Hello with image',
                    metadata: {
                        image_url: '/api/images/test.jpg'
                    }
                }
            ]
        },
        onSendMessage: vi.fn(),
        onNewConversation: vi.fn(),
        isLoading: false,
        llmNames: [],
        theme: 'dark'
    };

    it('renders a single image from legacy image_url with correct backend URL', () => {
        render(<ChatInterface {...defaultProps} />);

        const img = screen.getByAltText('Attached');
        expect(img).toBeInTheDocument();
        expect(img.src).toBe('http://localhost:8001/api/images/test.jpg');
        expect(api.getImageUrl).toHaveBeenCalledWith('/api/images/test.jpg');
    });

    it('renders multiple images from image_urls with correct backend URLs', () => {
        const propsWithMultipleImages = {
            ...defaultProps,
            conversation: {
                ...defaultProps.conversation,
                messages: [
                    {
                        role: 'user',
                        content: 'Hello with multiple images',
                        metadata: {
                            image_urls: ['/api/images/img1.jpg', '/api/images/img2.png']
                        }
                    }
                ]
            }
        };

        render(<ChatInterface {...propsWithMultipleImages} />);

        const images = screen.getAllByAltText(/Attached/);
        expect(images).toHaveLength(2);
        expect(images[0].src).toBe('http://localhost:8001/api/images/img1.jpg');
        expect(images[1].src).toBe('http://localhost:8001/api/images/img2.png');
        expect(api.getImageUrl).toHaveBeenCalledWith('/api/images/img1.jpg');
        expect(api.getImageUrl).toHaveBeenCalledWith('/api/images/img2.png');
    });

    it('renders legacy image_url even if image_urls is an empty array', () => {
        const propsWithEmptyArray = {
            ...defaultProps,
            conversation: {
                ...defaultProps.conversation,
                messages: [
                    {
                        role: 'user',
                        content: 'Hello with empty array',
                        metadata: {
                            image_url: '/api/images/legacy.jpg',
                            image_urls: []
                        }
                    }
                ]
            }
        };

        render(<ChatInterface {...propsWithEmptyArray} />);

        const img = screen.getByAltText('Attached');
        expect(img).toBeInTheDocument();
        expect(img.src).toBe('http://localhost:8001/api/images/legacy.jpg');
    });
});
