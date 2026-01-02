/**
 * API client for the LLM Council backend.
 */

const API_BASE = 'http://localhost:8001';

export const api = {
  /**
   * List all conversations.
   */
  async listConversations() {
    const response = await fetch(`${API_BASE}/api/conversations`);
    if (!response.ok) {
      throw new Error('Failed to list conversations');
    }
    return response.json();
  },

  /**
   * Create a new conversation.
   */
  async createConversation() {
    const response = await fetch(`${API_BASE}/api/conversations`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({}),
    });
    if (!response.ok) {
      throw new Error('Failed to create conversation');
    }
    return response.json();
  },

  /**
   * Get a specific conversation.
   */
  async getConversation(conversationId) {
    const response = await fetch(
      `${API_BASE}/api/conversations/${conversationId}`
    );
    if (!response.ok) {
      throw new Error('Failed to get conversation');
    }
    return response.json();
  },

  /**
   * Send a message in a conversation.
   */
  async sendMessage(conversationId, content, manualResponses = []) {
    const response = await fetch(
      `${API_BASE}/api/conversations/${conversationId}/message`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ content, manual_responses: manualResponses }),
      }
    );
    if (!response.ok) {
      throw new Error('Failed to send message');
    }
    return response.json();
  },

  /**
   * Send a message and receive streaming updates.
   * @param {string} conversationId - The conversation ID
   * @param {string} content - The message content
   * @param {function} onEvent - Callback function for each event: (eventType, data) => void
   * @returns {Promise<void>}
   */
  async sendMessageStream(conversationId, content, onEvent) {
    const response = await fetch(
      `${API_BASE}/api/conversations/${conversationId}/message/stream`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ content }),
      }
    );

    if (!response.ok) {
      throw new Error('Failed to send message');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const chunk = decoder.decode(value);
      const lines = chunk.split('\n');

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6);
          try {
            const event = JSON.parse(data);
            onEvent(event.type, event);
          } catch (e) {
            console.error('Failed to parse SSE event:', e);
          }
        }
      }
    }
  },

  /**
   * Run automation for a prompt.
   * provider: "ai_studio", "chatgpt", or "claude"
   */
  async runAutomation(prompt, model, provider = "ai_studio") {
    const response = await fetch(`${API_BASE}/api/manual/run-automation`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ prompt, model, provider }),
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Automation failed');
    }
    return response.json();
  },

  /**
   * Get Stage 2 prompt (Manual Mode).
   */
  async getStage2Prompt(query, stage1Responses, previousMessages = []) {
    const response = await fetch(`${API_BASE}/api/manual/stage2-prompt`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        user_query: query,
        stage1_results: stage1Responses,
        previous_messages: previousMessages
      }),
    });
    if (!response.ok) {
      throw new Error('Failed to get Stage 2 prompt');
    }
    return response.json();
  },

  /**
   * Process rankings (Manual Mode).
   */
  async processRankings(stage2Results, labelToModel) {
    const response = await fetch(`${API_BASE}/api/manual/process-rankings`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        stage2_results: stage2Results,
        label_to_model: labelToModel
      }),
    });
    if (!response.ok) {
      throw new Error('Failed to process rankings');
    }
    return response.json();
  },

  /**
   * Get Stage 3 prompt (Manual Mode).
   */
  async getStage3Prompt(query, stage1Results, stage2Results, previousMessages = []) {
    const response = await fetch(`${API_BASE}/api/manual/stage3-prompt`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        user_query: query,
        stage1_results: stage1Results,
        stage2_results: stage2Results,
        previous_messages: previousMessages
      }),
    });
    if (!response.ok) {
      throw new Error('Failed to get Stage 3 prompt');
    }
    return response.json();
  },

  /**
   * Save a fully constructed manual message.
   */
  async saveManualMessage(conversationId, messageData) {
    const response = await fetch(`${API_BASE}/api/conversations/${conversationId}/message/manual`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(messageData),
    });
    if (!response.ok) {
      throw new Error('Failed to save manual message');
    }
    return response.json();
  },

  async deleteConversation(conversationId) {
    const response = await fetch(`${API_BASE}/api/conversations/${conversationId}`, {
      method: 'DELETE',
    });
    if (!response.ok) {
      throw new Error('Failed to delete conversation');
    }
    return response.json();
  },

  async updateConversationTitle(conversationId, title) {
    const response = await fetch(`${API_BASE}/api/conversations/${conversationId}/title`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ title }),
    });
    if (!response.ok) {
      throw new Error('Failed to update conversation title');
    }
    return response.json();
  },

  // --- Automation Session Methods ---

  /**
   * Get automation login status for all providers.
   */
  async getAutomationStatus() {
    const response = await fetch(`${API_BASE}/api/automation/status`);
    if (!response.ok) {
      throw new Error('Failed to get automation status');
    }
    return response.json();
  },

  /**
   * Initiate interactive login for a provider.
   * @param {string} provider - "ai_studio", "chatgpt", or "claude"
   */
  async loginAutomation(provider) {
    const response = await fetch(`${API_BASE}/api/automation/login/${provider}`, {
      method: 'POST',
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Login failed');
    }
    return response.json();
  },

  /**
   * Logout (clear session) for a provider.
   * @param {string} provider - "ai_studio", "chatgpt", or "claude"
   */
  async logoutAutomation(provider) {
    const response = await fetch(`${API_BASE}/api/automation/logout/${provider}`, {
      method: 'POST',
    });
    if (!response.ok) {
      throw new Error('Logout failed');
    }
    return response.json();
  },

  /**
   * Get available models for a provider.
   * @param {string} provider - "ai_studio", "chatgpt", or "claude"
   */
  async getAutomationModels(provider) {
    const response = await fetch(`${API_BASE}/api/automation/models/${provider}`);
    if (!response.ok) {
      throw new Error('Failed to get automation models');
    }
    return response.json();
  },

  /**
   * Force a sync of automation models for a provider.
   * @param {string} provider - "ai_studio", "chatgpt", or "claude"
   */
  async syncAutomationModels(provider) {
    const response = await fetch(`${API_BASE}/api/automation/models/${provider}/sync`, {
      method: 'POST',
    });
    if (!response.ok) {
      throw new Error('Failed to sync automation models');
    }
    return response.json();
  },
};
