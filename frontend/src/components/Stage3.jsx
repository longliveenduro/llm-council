import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import remarkGfm from 'remark-gfm';
import 'katex/dist/katex.min.css';


import { getModelIcon } from '../utils/modelIcons';
import './Stage3.css';

function getModelLabel(modelName, labelToModel) {
  if (!labelToModel) return null;
  const entry = Object.entries(labelToModel).find(([_, model]) => model === modelName);
  if (entry) {
    return entry[0].replace('Response ', '');
  }
  return null;
}

export default function Stage3({ finalResponse, labelToModel, aggregateRankings }) {
  if (!finalResponse) {
    return null;
  }

  const label = getModelLabel(finalResponse.model, labelToModel);
  const modelDisplayName = (finalResponse.model.split('/')[1] || finalResponse.model)
    .replace('Chat GPT', 'ChatGPT')
    .replace(' [Ext. Thinking]', '');
  const chairmanLabel = label ? `Model ${label}: ${modelDisplayName}` : modelDisplayName;

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
            Chairman: {chairmanLabel}
          </div>
        </div>
        <div className="final-text markdown-content">
          <ReactMarkdown
            remarkPlugins={[remarkMath, remarkGfm]}
            rehypePlugins={[rehypeKatex]}
          >
            {finalResponse.response}
          </ReactMarkdown>
        </div>


      </div>

      {aggregateRankings && aggregateRankings.length > 0 && (
        <div className="aggregate-rankings">
          <h4>Aggregate Rankings (Street Cred)</h4>
          <p className="stage-description">
            Combined results across all peer evaluations (lower score is better):
          </p>
          <div className="aggregate-list">
            {aggregateRankings.map((agg, index) => (
              <div key={index} className="aggregate-item">
                <span className="rank-position">#{index + 1}</span>
                <span className="rank-model-container">
                  {getModelIcon(agg.model) && (
                    <img
                      src={getModelIcon(agg.model)}
                      alt=""
                      className="rank-model-icon"
                      style={{ filter: 'var(--icon-filter)' }}
                      onError={(e) => e.target.style.display = 'none'}
                    />
                  )}
                  <span className="rank-model">
                    {agg.model.split('/')[1] || agg.model}
                  </span>
                </span>
                <span className="rank-score">
                  Avg: {agg.average_rank.toFixed(2)}
                </span>
                <span className="rank-count">
                  ({agg.rankings_count} votes)
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
