const ICON_BASE_URL = 'https://unpkg.com/@lobehub/icons-static-svg@latest/icons';

const MODEL_ICON_MAPPING = {
    'openai': 'openai',
    'claude': 'claude',
    'anthropic': 'anthropic',
    'gemini': 'gemini',
    'google': 'googlegemini',
    'mistral': 'mistral',
    'llama': 'meta',
    'meta': 'meta',
    'grok': 'xai',
    'xai': 'xai',
    'perplexity': 'perplexity',
    'deepseek': 'deepseek',
    'minimax': 'minimax',
    'moonshot': 'moonshot',
    'qwen': 'aliyun',
    'yi': '01ai',
    // Lower priority models or keywords
    'gpt-4': 'openai',
    'gpt-3.5': 'openai',
    'chatgpt': 'openai',
    'chat gpt': 'openai',
    'thinking': 'openai',
};

export const getModelIcon = (modelName) => {
    if (!modelName) return null;

    const normalizedName = modelName.toLowerCase();

    for (const [key, icon] of Object.entries(MODEL_ICON_MAPPING)) {
        if (normalizedName.includes(key)) {
            return `${ICON_BASE_URL}/${icon}.svg`;
        }
    }

    // Fallback icon if no match found (maybe a generic bot icon or just null)
    return null;
};
