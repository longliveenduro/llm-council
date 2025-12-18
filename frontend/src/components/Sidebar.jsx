import { useState, useEffect, useRef } from 'react';
import { getModelIcon } from '../utils/modelIcons';
import './Sidebar.css';

export default function Sidebar({
  conversations,
  currentConversationId,
  onSelectConversation,
  onNewConversation,
  onDeleteConversation,
  onRenameConversation,
  llmNames,
  onAddLlmName,
  onRemoveLlmName,
}) {
  const [editingId, setEditingId] = useState(null);
  const [editTitle, setEditTitle] = useState('');
  const [isAddingLlm, setIsAddingLlm] = useState(false);
  const [newLlmName, setNewLlmName] = useState('');
  const editInputRef = useRef(null);
  const llmInputRef = useRef(null);

  useEffect(() => {
    if (editingId && editInputRef.current) {
      editInputRef.current.focus();
    }
  }, [editingId]);

  useEffect(() => {
    if (isAddingLlm && llmInputRef.current) {
      llmInputRef.current.focus();
    }
  }, [isAddingLlm]);

  const handleAddLlm = (e) => {
    e.preventDefault();
    if (newLlmName.trim()) {
      onAddLlmName(newLlmName.trim());
      setNewLlmName('');
      setIsAddingLlm(false);
    }
  };

  const handleLlmKeyDown = (e) => {
    if (e.key === 'Enter') {
      handleAddLlm(e);
    } else if (e.key === 'Escape') {
      setIsAddingLlm(false);
      setNewLlmName('');
    }
  };

  const handleStartEdit = (e, conv) => {
    e.stopPropagation();
    setEditingId(conv.id);
    setEditTitle(conv.title || 'New Conversation');
  };

  const handleSaveEdit = (e) => {
    e.stopPropagation();
    if (editingId && editTitle.trim()) {
      onRenameConversation(editingId, editTitle.trim());
      setEditingId(null);
    } else {
      setEditingId(null); // Cancel if empty
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      handleSaveEdit(e);
    } else if (e.key === 'Escape') {
      e.stopPropagation();
      setEditingId(null);
    }
  };

  return (
    <div className="sidebar">
      <div className="sidebar-header">
        <h1>LLM Council</h1>
        <button className="new-conversation-btn" onClick={onNewConversation}>
          + New Conversation
        </button>
      </div>

      <div className="sidebar-section">
        <div className="section-header">
          <h2>Council Members</h2>
          <button
            className="add-llm-btn"
            onClick={() => setIsAddingLlm(true)}
            title="Add Council Member"
          >
            +
          </button>
        </div>

        <div className="llm-list">
          {isAddingLlm && (
            <div className="add-llm-input-container">
              <input
                ref={llmInputRef}
                type="text"
                className="add-llm-input"
                placeholder="Model name..."
                value={newLlmName}
                onChange={(e) => setNewLlmName(e.target.value)}
                onKeyDown={handleLlmKeyDown}
                onBlur={() => {
                  if (!newLlmName.trim()) setIsAddingLlm(false);
                }}
              />
            </div>
          )}
          {llmNames.map((name) => {
            const iconUrl = getModelIcon(name);
            return (
              <div key={name} className="llm-item">
                <div className="llm-icon-container">
                  {iconUrl ? (
                    <img
                      src={iconUrl}
                      alt=""
                      className="llm-icon"
                      onError={(e) => e.target.style.display = 'none'}
                    />
                  ) : (
                    <div className="llm-icon-placeholder" />
                  )}
                </div>
                <span className="llm-name" title={name}>{name}</span>
                <button
                  className="remove-llm-btn"
                  onClick={() => onRemoveLlmName(name)}
                  title="Remove"
                >
                  ×
                </button>
              </div>
            );
          })}
        </div>
      </div>

      <div className="sidebar-section">
        <div className="section-header">
          <h2>Conversations</h2>
        </div>
      </div>

      <div className="conversation-list">
        {conversations.length === 0 ? (
          <div className="no-conversations">No conversations yet</div>
        ) : (
          conversations.map((conv) => (
            <div
              key={conv.id}
              className={`conversation-item ${conv.id === currentConversationId ? 'active' : ''
                }`}
              onClick={() => onSelectConversation(conv.id)}
            >
              <div className="conversation-info">
                {editingId === conv.id ? (
                  <input
                    ref={editInputRef}
                    type="text"
                    className="edit-title-input"
                    value={editTitle}
                    onChange={(e) => setEditTitle(e.target.value)}
                    onKeyDown={handleKeyDown}
                    onBlur={() => setEditingId(null)}
                    onClick={(e) => e.stopPropagation()}
                  />
                ) : (
                  <>
                    <div className="conversation-title">
                      {conv.title || 'New Conversation'}
                    </div>
                    <div className="conversation-meta">
                      {conv.message_count} messages
                    </div>
                  </>
                )}
              </div>

              <div className="item-actions">
                <button
                  className="icon-btn edit-btn"
                  onClick={(e) => handleStartEdit(e, conv)}
                  title="Rename"
                >
                  ✎
                </button>
                <button
                  className="icon-btn delete-btn"
                  onClick={(e) => {
                    e.stopPropagation();
                    onDeleteConversation(conv.id);
                  }}
                  title="Delete"
                >
                  ×
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
