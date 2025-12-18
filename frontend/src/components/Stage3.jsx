import ReactMarkdown from 'react-markdown';
import { getModelIcon } from '../utils/modelIcons';
import './Stage3.css';

export default function Stage3({ finalResponse }) {
  if (!finalResponse) {
    return null;
  }

  return (
    <div className="stage stage3">
      <h3 className="stage-title">Stage 3: Final Council Answer</h3>
      <div className="final-response">
        <div className="chairman-header">
          {getModelIcon(finalResponse.model) && (
            <img
              src={getModelIcon(finalResponse.model)}
              alt=""
              className="chairman-icon"
              style={{ filter: 'var(--icon-filter)' }}
              onError={(e) => e.target.style.display = 'none'}
            />
          )}
          <div className="chairman-label">
            Chairman: {finalResponse.model.split('/')[1] || finalResponse.model}
          </div>
        </div>
        <div className="final-text markdown-content">
          <ReactMarkdown>{finalResponse.response}</ReactMarkdown>
        </div>
      </div>
    </div>
  );
}
