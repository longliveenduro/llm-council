import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { api } from '../api';
import './ManualWizard.css';

export default function ManualWizard({ conversationId, previousMessages = [], onComplete, onCancel }) {
    const [step, setStep] = useState(1); // 1: Opinions, 2: Review, 3: Synthesis
    const [isLoading, setIsLoading] = useState(false);

    const isFollowUp = previousMessages.length > 0;

    // Data State
    const [userQuery, setUserQuery] = useState('');
    const [stage1Responses, setStage1Responses] = useState([]); // { model, response }
    const [stage2Prompt, setStage2Prompt] = useState('');
    const [labelToModel, setLabelToModel] = useState({});
    const [stage2Responses, setStage2Responses] = useState([]); // { model, ranking }
    const [stage3Prompt, setStage3Prompt] = useState('');
    const [stage3Response, setStage3Response] = useState(''); // { model, response }

    // Input State for current item
    const [currentModel, setCurrentModel] = useState('');
    const [currentText, setCurrentText] = useState('');

    // --- Helpers ---
    const copyToClipboard = (text) => {
        navigator.clipboard.writeText(text);
    };

    const getContextText = () => {
        let text = 'Context so far:\n\n';
        let turnCount = 1;

        // Group messages into turns (assuming User -> Assistant pattern)
        // We iterate through and formatting pairs
        for (let i = 0; i < previousMessages.length; i++) {
            const msg = previousMessages[i];
            if (msg.role === 'user') {
                text += `User Question ${turnCount}: ${msg.content}\n`;
            } else if (msg.role === 'assistant') {
                const response = msg.stage3?.response || "(No final response)";
                text += `LLM Answer ${turnCount}: ${response}\n\n`;
                turnCount++;
            }
        }

        text += `Current Question: ${userQuery}`;
        return text;
    };

    const addStage1Response = () => {
        if (currentModel && currentText) {
            setStage1Responses([...stage1Responses, { model: currentModel, response: currentText }]);
            setCurrentModel('');
            setCurrentText('');
        }
    };

    const addStage2Response = () => {
        if (currentModel && currentText) {
            setStage2Responses([...stage2Responses, { model: currentModel, ranking: currentText }]);
            setCurrentModel('');
            setCurrentText('');
        }
    };

    // --- Navigation Handlers ---

    const handleGoToStep2 = async () => {
        if (!userQuery.trim() || stage1Responses.length === 0) return;

        setIsLoading(true);
        try {
            const data = await api.getStage2Prompt(userQuery, stage1Responses, previousMessages);
            setStage2Prompt(data.prompt);
            setLabelToModel(data.label_to_model);
            setStep(2);
        } catch (error) {
            console.error(error);
            alert('Failed to generate Stage 2 prompt');
        } finally {
            setIsLoading(false);
        }
    };

    const handleGoToStep3 = async () => {
        if (stage2Responses.length === 0) return;

        setIsLoading(true);
        try {
            // First process rankings to get aggregation and parsed data
            const processedData = await api.processRankings(stage2Responses, labelToModel);

            // Then generate stage 3 prompt
            const promptData = await api.getStage3Prompt(
                userQuery,
                stage1Responses,
                processedData.stage2_results, // Use processed with parsed rankings
                previousMessages
            );

            setStage3Prompt(promptData.prompt);

            // Store processed stage 2 results for final save
            setStage2Responses(processedData.stage2_results);

            // Also need to store aggregate for metadata if we want (but backend re-calcs on save usually? 
            // Actually save_manual_message just takes what we give it. 
            // The aggregate is calculated but where do we put it? 
            // SaveManualMessageRequest expects metadata. We should include it there.
            // But processedData returns aggregate_rankings.

            // Pass aggregate_rankings to step 3 or state
            window.tempAggregateRankings = processedData.aggregate_rankings; // Hacky but effective for now

            setStep(3);
        } catch (error) {
            console.error(error);
            alert('Failed to process rankings or generate Stage 3 prompt');
        } finally {
            setIsLoading(false);
        }
    };

    const [manualTitle, setManualTitle] = useState('');

    const handleComplete = async () => {
        if (!stage3Response.model || !stage3Response.response) return;

        setIsLoading(true);
        try {
            const messageData = {
                user_query: userQuery,
                stage1: stage1Responses,
                stage2: stage2Responses,
                stage3: {
                    model: stage3Response.model,
                    response: stage3Response.response
                },
                metadata: {
                    label_to_model: labelToModel,
                    aggregate_rankings: window.tempAggregateRankings || []
                },
                title: manualTitle // Optional
            };

            await api.saveManualMessage(conversationId, messageData);

            // Feedback
            alert('Conversation saved successfully!');

            onComplete();
        } catch (error) {
            console.error(error);
            alert('Failed to save message');
        } finally {
            setIsLoading(false);
        }
    };

    // --- Render Steps ---

    const renderStep1 = () => (
        <div className="wizard-step">
            <h3>{isFollowUp ? 'Step 1: Follow Up Opinions' : 'Step 1: Initial Opinions'}</h3>
            <p className="step-desc">Enter your query and manually add model responses.</p>

            <div className="form-group">
                <label>{isFollowUp ? 'Your Follow Up Question:' : 'Your Question:'}</label>
                <textarea
                    value={userQuery}
                    onChange={(e) => setUserQuery(e.target.value)}
                    placeholder={isFollowUp ? 'What is your follow up question?' : 'What is your question?'}
                    rows={2}
                />
            </div>

            {isFollowUp && (
                <div className="form-group context-box">
                    <label>Context for Models (Previous History + New Query):</label>
                    <div className="context-preview">
                        {getContextText()}
                    </div>
                    <button onClick={() => copyToClipboard(getContextText())} className="copy-btn">
                        Copy Context
                    </button>
                    <p className="hint-text">Paste this context to your models so they know the conversation history.</p>
                </div>
            )}

            <div className="responses-list">
                {stage1Responses.map((r, i) => (
                    <div key={i} className="response-item">
                        <strong>{r.model}</strong>: {r.response.substring(0, 50)}...
                    </div>
                ))}
            </div>

            <div className="add-response-form">
                <input
                    placeholder="Model Name"
                    value={currentModel}
                    onChange={(e) => setCurrentModel(e.target.value)}
                />
                <textarea
                    placeholder="Model Response"
                    value={currentText}
                    onChange={(e) => setCurrentText(e.target.value)}
                    rows={3}
                />
                <button onClick={addStage1Response} disabled={!currentModel || !currentText}>Add Response</button>
            </div>

            <div className="wizard-actions">
                <button onClick={onCancel} className="secondary-btn">Cancel</button>
                <button
                    onClick={handleGoToStep2}
                    className="primary-btn"
                    disabled={!userQuery || stage1Responses.length === 0}
                >
                    Next: Peer Review
                </button>
            </div>
        </div>
    );

    const renderStep2 = () => (
        <div className="wizard-step">
            <h3>Step 2: Peer Review</h3>

            <div className="form-group">
                <label>Conversation Title (Optional):</label>
                <input
                    type="text"
                    placeholder="Enter a title for this conversation..."
                    value={manualTitle}
                    onChange={(e) => setManualTitle(e.target.value)}
                    className="title-input"
                />
                <p className="hint-text">You can set a title now based on the responses so far.</p>
            </div>

            <p className="step-desc">Copy the prompt below, send it to models, and paste their rankings.</p>

            <div className="prompt-box">
                <label>Stage 2 Prompt:</label>
                <div className="prompt-preview">
                    {stage2Prompt}
                </div>
                <button onClick={() => copyToClipboard(stage2Prompt)} className="copy-btn">Copy Prompt</button>
            </div>

            <div className="responses-list">
                {stage2Responses.map((r, i) => (
                    <div key={i} className="response-item">
                        <strong>{r.model}</strong>: {r.ranking.substring(0, 50)}...
                    </div>
                ))}
            </div>

            <div className="add-response-form">
                <select
                    value={currentModel}
                    onChange={(e) => setCurrentModel(e.target.value)}
                    className="model-select"
                >
                    <option value="">Select Reviewer Model</option>
                    {stage1Responses.map((r, i) => (
                        <option key={i} value={r.model}>{r.model}</option>
                    ))}
                </select>
                <textarea
                    placeholder="Paste Ranking Response (must include 'FINAL RANKING:...')"
                    value={currentText}
                    onChange={(e) => setCurrentText(e.target.value)}
                    rows={3}
                />
                <button onClick={addStage2Response} disabled={!currentModel || !currentText}>Add Ranking</button>
            </div>

            <div className="wizard-actions">
                <button onClick={() => setStep(1)} className="secondary-btn">Back</button>
                <button
                    onClick={handleGoToStep3}
                    className="primary-btn"
                    disabled={stage2Responses.length === 0}
                >
                    Next: Synthesis
                </button>
            </div>
        </div>
    );

    const renderStep3 = () => (
        <div className="wizard-step">
            <h3>Step 3: Synthesis</h3>
            <p className="step-desc">Copy the Chairman prompt and paste the final answer.</p>

            <div className="prompt-col-layout">
                <div className="prompt-box">
                    <label>Chairman Prompt (Anonymized):</label>
                    <div className="prompt-preview">
                        {stage3Prompt}
                    </div>
                    <button onClick={() => copyToClipboard(stage3Prompt)} className="copy-btn">Copy Prompt</button>
                </div>

                <div className="mapping-box">
                    <label>Reference Mapping:</label>
                    <div className="mapping-list">
                        {Object.entries(labelToModel).map(([label, model]) => (
                            <div key={label} className="mapping-item">
                                <strong>{label}</strong> = {model}
                            </div>
                        ))}
                    </div>
                </div>
            </div>

            <div className="form-group">
                <label>Final Synthesis:</label>
                <div className="chairman-input-row">
                    <select
                        value={stage3Response.model}
                        onChange={(e) => setStage3Response({ ...stage3Response, model: e.target.value })}
                        className="model-select chairman-select"
                    >
                        <option value="Manual Chairman">Manual Chairman</option>
                        {stage1Responses.map((r, i) => (
                            <option key={i} value={r.model}>{r.model}</option>
                        ))}
                    </select>
                </div>
                <textarea
                    className="final-response-input"
                    value={stage3Response.response || ''}
                    onChange={(e) => setStage3Response({ ...stage3Response, response: e.target.value })}
                    placeholder="Paste the final answer here..."
                    rows={6}
                />
            </div>

            <div className="wizard-actions">
                <button onClick={() => setStep(2)} className="secondary-btn">Back</button>
                <button
                    onClick={handleComplete}
                    className="primary-btn complete-btn"
                    disabled={!stage3Response.response}
                >
                    Finish & Save
                </button>
            </div>
        </div>
    );

    if (isLoading) {
        return <div className="manual-wizard-loading">Processing...</div>;
    }

    return (
        <div className="manual-wizard">
            {step === 1 && renderStep1()}
            {step === 2 && renderStep2()}
            {step === 3 && renderStep3()}
        </div>
    );
}
