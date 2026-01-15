import { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import remarkGfm from 'remark-gfm';
import 'katex/dist/katex.min.css';


import Stage1 from './Stage1';
import Stage2 from './Stage2';
import Stage3 from './Stage3';
import WebChatBotWizard from './WebChatBotWizard';
import Highscores from './Highscores';
import './ChatInterface.css';

export default function ChatInterface({
  conversation,
  onSendMessage,
  onNewConversation,
  isLoading,
  onReload, // Added prop to trigger reload after manual save
  llmNames,
  onAddLlmName,
  theme,
  automationModels,
  onTitleUpdate,
}) {
  const [input, setInput] = useState('');


  // Web ChatBot Mode State
  const [isWebChatBotMode, setIsWebChatBotMode] = useState(false);
  const [isContinuing, setIsContinuing] = useState(false);

  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [conversation]);

  // Track previous conversation ID to detect switches during render
  const prevConversationIdRef = useRef(conversation?.id);

  // Reset continuing state when switching conversations
  useEffect(() => {
    setIsContinuing(false);
    setInput(''); // Clear input when switching conversations
    const hasDraft = localStorage.getItem(`web_chatbot_draft_${conversation?.id}`);
    setIsWebChatBotMode(!!hasDraft);

    // Update ref after side effects
    prevConversationIdRef.current = conversation?.id;
  }, [conversation?.id]);

  // If conversation changed (render ID != ref ID), force input to empty to prevent leakage
  // into the WebChatBotWizard before the useEffect can clear the state.
  const effectiveInput = conversation?.id === prevConversationIdRef.current ? input : '';

  const handleSubmit = (e) => {
    e.preventDefault();
    if (input.trim() && !isLoading) {
      onSendMessage(input);
      setInput('');
      // Keep isContinuing true so we don't hide input immediately while loading?
      // Actually, once response comes back, we might want to hide it to accept "historic" state again?
      // But for smooth chat, let's keep it open?
      // User requirement: "historic" councils should be clean.
      // If I just asked a question, it's now "historic"?
      // Let's reset isContinuing to false when a response completes?
      // But we don't easily know here when it completes (streaming happens in App).
      // Let's just leave isContinuing as true until the user switches conversation.
    }
  };

  const handleKeyDown = (e) => {
    // Submit on Enter (without Shift)
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const handleWebChatBotWizardComplete = () => {
    setIsWebChatBotMode(false);
    if (onReload) onReload();
    // Also scroll bottom
    setTimeout(scrollToBottom, 100);
    // Note: isContinuing stays true here so user sees the result and input remains?
    // actually if we want it to be "clean" again, we should set isContinuing(false).
    setIsContinuing(false);
  };

  if (!conversation) {
    return (
      <div className="chat-interface">
        <div className="empty-state">
          <div className="council-image-container">
            <img
              src={theme === 'dark' ? '/header-dark.png' : '/header-light.png'}
              alt="LLM Council"
              className="council-header-img"
            />
          </div>
          <button className="new-conv-empty-btn" onClick={onNewConversation}>
            Create a new conversation to get started
          </button>
          <Highscores />
        </div>
      </div>
    );
  }

  const hasAssistantResponse = conversation.messages.some(m => m.role === 'assistant');
  const showInput = !hasAssistantResponse || isContinuing;

  return (
    <div className="chat-interface">
      {showInput && isWebChatBotMode ? (
        <div className="web-chatbot-wizard-fullscreen">
          <div className="mode-toggle">
            <label className="switch">
              <input
                type="checkbox"
                checked={isWebChatBotMode}
                onChange={() => setIsWebChatBotMode(!isWebChatBotMode)}
                disabled={isLoading}
              />
              <span className="slider round"></span>
            </label>
            <span className="mode-label">Web ChatBot</span>
          </div>
          <WebChatBotWizard
            key={conversation.id}
            conversationId={conversation.id}
            currentTitle={conversation.title}
            previousMessages={conversation.messages}
            llmNames={llmNames}
            onAddLlmName={onAddLlmName}
            onComplete={handleWebChatBotWizardComplete}
            onCancel={() => setIsWebChatBotMode(false)}
            automationModels={automationModels}
            onTitleUpdate={onTitleUpdate}
            initialQuestion={effectiveInput}
          />
        </div>
      ) : (
        <>
          <div className="messages-container">
            {conversation.messages.length === 0 && !isWebChatBotMode ? (
              <div className="empty-state">
                <div className="council-image-container">
                  <img
                    src={theme === 'dark' ? '/header-dark.png' : '/header-light.png'}
                    alt="LLM Council"
                    className="council-header-img"
                  />
                </div>
                <p>Ask a question to consult the LLM Council</p>
              </div>
            ) : (
              conversation.messages.map((msg, index) => (
                <div key={index} className="message-group">
                  {msg.role === 'user' ? (
                    <div className="user-message">
                      <div className="message-label">You</div>
                      <div className="message-content">
                        {msg.metadata?.image_url && (
                          <div className="user-uploaded-image">
                            <img
                              src={msg.metadata.image_url}
                              alt="Attached"
                              style={{
                                maxWidth: '100%',
                                maxHeight: '300px',
                                borderRadius: '8px',
                                marginBottom: '12px',
                                border: '1px solid var(--border-color)'
                              }}
                              onClick={() => window.open(msg.metadata.image_url, '_blank')}
                              title="Click to view full size"
                            />
                          </div>
                        )}
                        <div className="markdown-content">
                          <ReactMarkdown
                            remarkPlugins={[remarkMath, remarkGfm]}
                            rehypePlugins={[rehypeKatex]}
                          >
                            {msg.content}
                          </ReactMarkdown>
                        </div>

                      </div>
                    </div>
                  ) : (
                    <div className="assistant-message">
                      <div className="message-label">LLM Council</div>

                      {/* Stage 1 */}
                      {msg.loading?.stage1 && (
                        <div className="stage-loading">
                          <div className="spinner"></div>
                          <span>Running Stage 1: Collecting individual responses...</span>
                        </div>
                      )}
                      {msg.stage1 && <Stage1 responses={msg.stage1} />}

                      {/* Stage 2 */}
                      {msg.loading?.stage2 && (
                        <div className="stage-loading">
                          <div className="spinner"></div>
                          <span>Running Stage 2: Peer rankings...</span>
                        </div>
                      )}
                      {msg.stage2 && (
                        <Stage2
                          rankings={msg.stage2}
                          labelToModel={msg.metadata?.label_to_model}
                          aggregateRankings={msg.metadata?.aggregate_rankings}
                        />
                      )}

                      {/* Stage 3 */}
                      {msg.loading?.stage3 && (
                        <div className="stage-loading">
                          <div className="spinner"></div>
                          <span>Running Stage 3: Final synthesis...</span>
                        </div>
                      )}
                      {msg.stage3 && (
                        <Stage3
                          finalResponse={msg.stage3}
                          labelToModel={msg.metadata?.label_to_model}
                        />
                      )}
                    </div>
                  )}
                </div>
              ))
            )}

            {isLoading && (
              <div className="loading-indicator">
                <div className="spinner"></div>
                <span>Consulting the council...</span>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {!showInput && (
            <div className="continue-container">
              <button
                className="continue-btn"
                onClick={() => setIsContinuing(true)}
              >
                Continue Conversation
              </button>
            </div>
          )}

          {showInput && (
            <div className="input-area">
              <div className="mode-toggle">
                <label className="switch">
                  <input
                    type="checkbox"
                    checked={isWebChatBotMode}
                    onChange={() => setIsWebChatBotMode(!isWebChatBotMode)}
                    disabled={isLoading}
                  />
                  <span className="slider round"></span>
                </label>
                <span className="mode-label">Web ChatBot</span>
              </div>

              <form className="input-form" onSubmit={handleSubmit}>
                <textarea
                  className="message-input"
                  placeholder="Ask your question... (Shift+Enter for new line, Enter to send)"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  disabled={isLoading}
                  rows={3}
                />
                <button
                  type="submit"
                  className="send-button"
                  disabled={!input.trim() || isLoading}
                >
                  Send
                </button>
              </form>
            </div>
          )}
        </>
      )}
    </div>
  );
}


