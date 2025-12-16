import { useState, useEffect, useRef } from 'react';
import './Sidebar.css';

export default function Sidebar({
  conversations,
  currentConversationId,
  onSelectConversation,
  onNewConversation,
  onDeleteConversation,
  onRenameConversation,
}) {
  const [editingId, setEditingId] = useState(null);
  const [editTitle, setEditTitle] = useState('');
  const editInputRef = useRef(null);

  useEffect(() => {
    if (editingId && editInputRef.current) {
      editInputRef.current.focus();
    }
  }, [editingId]);

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
