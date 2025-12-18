import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { getModelIcon } from '../utils/modelIcons';
import './Stage1.css';

export default function Stage1({ responses }) {
  const [activeTab, setActiveTab] = useState(0);

  if (!responses || responses.length === 0) {
    return null;
  }

  return (
    <div className="stage stage1">
      <h3 className="stage-title">Stage 1: Individual Responses</h3>

      <div className="tabs">
        {responses.map((resp, index) => {
          const modelDisplayName = resp.model.split('/')[1] || resp.model;
          const iconUrl = getModelIcon(resp.model);
          return (
            <button
              key={index}
              className={`tab ${activeTab === index ? 'active' : ''}`}
              onClick={() => setActiveTab(index)}
            >
              {iconUrl && (
                <img
                  src={iconUrl}
                  alt=""
                  className="tab-icon"
                  onError={(e) => e.target.style.display = 'none'}
                />
              )}
              {`Model ${String.fromCharCode(65 + index)}: ${modelDisplayName}`}
            </button>
          );
        })}
      </div>

      <div className="tab-content">
        <div className="model-info-header">
          {getModelIcon(responses[activeTab].model) && (
            <img
              src={getModelIcon(responses[activeTab].model)}
              alt=""
              className="model-header-icon"
              onError={(e) => e.target.style.display = 'none'}
            />
          )}
          <div className="model-name">{responses[activeTab].model}</div>
        </div>
        <div className="response-text markdown-content">
          <ReactMarkdown>{responses[activeTab].response}</ReactMarkdown>
        </div>
      </div>
    </div >
  );
}
