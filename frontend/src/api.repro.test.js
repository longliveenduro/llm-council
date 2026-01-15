
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { api } from './api';

describe('api.runAutomation', () => {
    let fetchSpy;

    beforeEach(() => {
        // Mock global fetch
        fetchSpy = vi.spyOn(global, 'fetch').mockResolvedValue({
            ok: true,
            json: async () => ({ response: 'ok' })
        });
    });

    afterEach(() => {
        vi.restoreAllMocks();
    });

    it('should include image in the request body when provided', async () => {
        const prompt = 'test prompt';
        const model = 'test-model';
        const provider = 'chatgpt';
        const image = 'data:image/png;base64,fakeimage';

        await api.runAutomation(prompt, model, provider, image);

        expect(fetchSpy).toHaveBeenCalledTimes(1);
        const [url, options] = fetchSpy.mock.calls[0];

        expect(url).toContain('/api/web-chatbot/run-automation');
        expect(options.method).toBe('POST');

        const body = JSON.parse(options.body);
        expect(body).toEqual({
            prompt,
            model,
            provider,
            image,
            images: []
        });
    });
});
