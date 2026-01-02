import { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import { api } from '../api';
import { getModelIcon } from '../utils/modelIcons';
import './ManualWizard.css';

const ModelBadge = ({ model }) => {
    const iconUrl = getModelIcon(model);
    return (
        <span className="model-badge">
            {iconUrl && (
                <img
                    src={iconUrl}
                    alt=""
                    className="model-badge-icon"
                    style={{ filter: 'var(--icon-filter)' }}
                    onError={(e) => e.target.style.display = 'none'}
                />
            )}
            <span className="model-badge-name">{model}</span>
        </span>
    );
};

export default function ManualWizard({ conversationId, currentTitle, previousMessages = [], llmNames = [], onAddLlmName, onComplete, onCancel, automationModels = { ai_studio: [], chatgpt: [], claude: [] }, onTitleUpdate, initialQuestion = '' }) {
    const draftKey = `manual_draft_${conversationId}`;
    const savedDraft = JSON.parse(localStorage.getItem(draftKey) || '{}');

    const [step, setStep] = useState(savedDraft.step || 1); // 1: Opinions, 2: Review, 3: Synthesis
    const [isLoading, setIsLoading] = useState(false);
    const [isAutomating, setIsAutomating] = useState(false);

    const isFollowUp = previousMessages.length > 0;

    // Data State
    const [userQuery, setUserQuery] = useState(savedDraft.userQuery || initialQuestion || '');
    const [stage1Responses, setStage1Responses] = useState(savedDraft.stage1Responses || []); // { model, response }
    const [stage2Prompt, setStage2Prompt] = useState(savedDraft.stage2Prompt || '');
    const [labelToModel, setLabelToModel] = useState(savedDraft.labelToModel || {});
    const [stage2Responses, setStage2Responses] = useState(savedDraft.stage2Responses || []); // { model, ranking }
    const [stage3Prompt, setStage3Prompt] = useState(savedDraft.stage3Prompt || '');
    const [stage3Response, setStage3Response] = useState(savedDraft.stage3Response || { model: '', response: '' }); // { model, response }
    const [manualTitle, setManualTitle] = useState(savedDraft.manualTitle || (currentTitle !== 'New Conversation' ? currentTitle : ''));
    const [aggregateRankings, setAggregateRankings] = useState(savedDraft.aggregateRankings || []);
    const [aiStudioModel, setAiStudioModel] = useState(savedDraft.aiStudioModel || (automationModels.ai_studio[0]?.name) || 'Gemini 2.5 Flash');

    // Input State for current item
    const [currentModel, setCurrentModel] = useState(savedDraft.currentModel || llmNames[0] || '');
    const [currentText, setCurrentText] = useState(savedDraft.currentText || '');

    // Sync aiStudioModel with available models
    useEffect(() => {
        const fallbacks = ['Gemini 3 Flash', 'Gemini 2.5 Flash', 'Gemini 1.5 Flash'];
        const isFallback = !aiStudioModel || fallbacks.includes(aiStudioModel);

        if (automationModels.ai_studio.length > 0) {
            const inGeminiList = automationModels.ai_studio.find(m => m.name === aiStudioModel);
            const inGptList = automationModels.chatgpt && automationModels.chatgpt.find(m => m.name === aiStudioModel);
            const inClaudeList = automationModels.claude && automationModels.claude.find(m => m.name === aiStudioModel);

            if (isFallback || (!inGeminiList && !inGptList && !inClaudeList)) {
                const defaultModel = automationModels.ai_studio[0]?.name;
                if (defaultModel) {
                    setAiStudioModel(defaultModel);
                }
            }
        }
    }, [automationModels.ai_studio, automationModels.chatgpt, automationModels.claude]);

    // Helpers for button disabling
    const normalizeName = (name) => name ? name.toLowerCase().replace(/\s+/g, '') : '';

    let activeModel = aiStudioModel;
    if (step === 1 || step === 2) {
        if (currentModel) activeModel = currentModel;
    } else if (step === 3) {
        if (stage3Response.model && stage3Response.model !== 'Manual Chairman') {
            activeModel = stage3Response.model;
        }
    }

    const isChatGPTSelected = activeModel && normalizeName(activeModel).includes('chatgpt');
    const isGeminiSelected = activeModel && normalizeName(activeModel).includes('gemini');
    const isClaudeSelected = activeModel && normalizeName(activeModel).includes('claude');

    // --- Persistence ---
    useEffect(() => {
        const draft = {
            step, userQuery, stage1Responses, stage2Prompt, labelToModel,
            stage2Responses, stage3Prompt, stage3Response, manualTitle,
            aggregateRankings, aiStudioModel, currentModel, currentText
        };
        localStorage.setItem(draftKey, JSON.stringify(draft));
    }, [draftKey, step, userQuery, stage1Responses, stage2Prompt, labelToModel, stage2Responses, stage3Prompt, stage3Response, manualTitle, aggregateRankings, aiStudioModel, currentModel, currentText]);

    const [isGeneratingTitle, setIsGeneratingTitle] = useState(false);
    const generatingLock = useRef(false);

    // --- Auto Title Generation ---
    const generateTitle = async (query) => {
        if (!query || isGeneratingTitle || generatingLock.current) return;
        setIsGeneratingTitle(true);
        generatingLock.current = true;

        try {
            const titlePrompt = `Generate a very short title (3-5 words maximum) that summarizes the following question.
The title should be concise and descriptive. No quotes or punctuation.

Question: ${query}

Title:`;
            const titleData = await api.runAutomation(titlePrompt, 'Gemini 2.5 Flash', 'ai_studio');
            const generatedTitle = titleData.response.trim().replace(/["']/g, '');
            setManualTitle(generatedTitle);
            await api.updateConversationTitle(conversationId, generatedTitle);
            if (onTitleUpdate) onTitleUpdate(conversationId, generatedTitle);
        } catch (err) {
            console.error('Failed to generate title', err);
        } finally {
            setIsGeneratingTitle(false);
            generatingLock.current = false;
        }
    };

    useEffect(() => {
        if (initialQuestion && (!manualTitle || manualTitle === 'New Conversation')) {
            generateTitle(initialQuestion);
        }
    }, [initialQuestion]);

    const copyToClipboard = (text) => navigator.clipboard.writeText(text);

    const getContextText = () => {
        let text = 'Context so far:\n\n';
        let turnCount = 1;
        for (let i = 0; i < previousMessages.length; i++) {
            const msg = previousMessages[i];
            if (msg.role === 'user') {
                text += `User Question ${turnCount}: ${msg.content}\n`;
            } else if (msg.role === 'assistant') {
                text += `LLM Answer ${turnCount}: ${msg.stage3?.response || "(No response)"}\n\n`;
                turnCount++;
            }
        }
        text += `Current Question: ${userQuery}`;
        return text;
    };

    const addStage1Response = () => {
        if (currentModel && currentText) {
            setStage1Responses([...stage1Responses, { model: currentModel, response: currentText }]);
            const nextIdx = llmNames.indexOf(currentModel) + 1;
            setCurrentModel(nextIdx > 0 && nextIdx < llmNames.length ? llmNames[nextIdx] : '');
            setCurrentText('');
        }
    };

    const addStage2Response = () => {
        if (currentModel && currentText) {
            setStage2Responses([...stage2Responses, { model: currentModel, ranking: currentText }]);
            const stage1Models = stage1Responses.map(r => r.model);
            const otherModels = llmNames.filter(name => !stage1Models.includes(name));
            const allReviewerModels = [...stage1Models, ...otherModels];
            const nextIdx = allReviewerModels.indexOf(currentModel) + 1;
            setCurrentModel(nextIdx > 0 && nextIdx < allReviewerModels.length ? allReviewerModels[nextIdx] : '');
            setCurrentText('');
        }
    };

    const handleRunAutomation = async (prompt, provider = "ai_studio") => {
        if (!prompt) return;
        setIsAutomating(true);
        setCurrentText('');
        try {
            let modelToUse = aiStudioModel;
            const norm = (name) => name ? name.toLowerCase().replace(/\s+/g, '') : '';

            if (provider === 'chatgpt') {
                if (aiStudioModel && norm(aiStudioModel).includes('chatgpt')) {
                    modelToUse = aiStudioModel;
                } else if (currentModel && norm(currentModel).includes('chatgpt')) {
                    modelToUse = currentModel;
                } else {
                    const gpts = (llmNames || []).filter(n => norm(n).includes('chatgpt'));
                    modelToUse = gpts.find(n => n.toLowerCase().includes('thinking')) || gpts[0] || 'ChatGPT';
                }
                if (!modelToUse.toLowerCase().includes('thinking') && !modelToUse.toLowerCase().includes('o1')) {
                    modelToUse += ' Thinking';
                }
            } else if (provider === 'claude') {
                if (aiStudioModel && norm(aiStudioModel).includes('claude')) {
                    modelToUse = aiStudioModel;
                } else if (currentModel && norm(currentModel).includes('claude')) {
                    modelToUse = currentModel;
                } else {
                    const claudes = (llmNames || []).filter(n => norm(n).includes('claude'));
                    modelToUse = claudes[0] || 'Claude 3.5 Sonnet';
                }
            }

            const data = await api.runAutomation(prompt, modelToUse, provider);
            setCurrentText(data.response);
        } catch (error) {
            alert(`Automation failed: ${error.message}`);
        } finally {
            setIsAutomating(false);
        }
    };

    const handleRunStage3Automation = async (prompt, provider = "ai_studio") => {
        if (!prompt) return;
        setIsAutomating(true);
        setStage3Response(prev => ({ ...prev, response: '' }));
        try {
            let modelToUse = aiStudioModel;
            const norm = (name) => name ? name.toLowerCase().replace(/\s+/g, '') : '';

            if (provider === 'chatgpt') {
                const gpts = (llmNames || []).filter(n => norm(n).includes('chatgpt'));
                modelToUse = (stage3Response.model && norm(stage3Response.model).includes('chatgpt'))
                    ? stage3Response.model
                    : (gpts.find(n => n.toLowerCase().includes('thinking')) || gpts[0] || 'ChatGPT');
                if (!modelToUse.toLowerCase().includes('thinking') && !modelToUse.toLowerCase().includes('o1')) {
                    modelToUse += ' Thinking';
                }
            } else if (provider === 'claude') {
                const claudes = (llmNames || []).filter(n => norm(n).includes('claude'));
                modelToUse = (stage3Response.model && norm(stage3Response.model).includes('claude'))
                    ? stage3Response.model
                    : (claudes[0] || 'Claude 3.5 Sonnet');
            }

            const data = await api.runAutomation(prompt, modelToUse, provider);
            setStage3Response(prev => ({ ...prev, response: data.response }));
        } catch (error) {
            alert(`Automation failed: ${error.message}`);
        } finally {
            setIsAutomating(false);
        }
    };

    const handleGoToStep2 = async () => {
        if (!userQuery.trim() || stage1Responses.length === 0) return;
        setIsLoading(true);
        try {
            if (!manualTitle || manualTitle === 'New Conversation') await generateTitle(userQuery);
            const data = await api.getStage2Prompt(userQuery, stage1Responses, previousMessages);
            setStage2Prompt(data.prompt);
            setLabelToModel(data.label_to_model);
            setStep(2);
        } catch (error) {
            alert('Failed to generate Stage 2 prompt');
        } finally {
            setIsLoading(false);
        }
    };

    const handleGoToStep3 = async () => {
        if (stage2Responses.length === 0) return;
        setIsLoading(true);
        try {
            const processed = await api.processRankings(stage2Responses, labelToModel);
            const promptData = await api.getStage3Prompt(userQuery, stage1Responses, processed.stage2_results, previousMessages);
            setStage3Prompt(promptData.prompt);
            setStage2Responses(processed.stage2_results);
            setAggregateRankings(processed.aggregate_rankings);
            if (!stage3Response.model || stage3Response.model === 'Manual Chairman') {
                if (stage1Responses.length > 0) setStage3Response(prev => ({ ...prev, model: stage1Responses[0].model }));
            }
            setStep(3);
        } catch (error) {
            alert('Failed to process rankings');
        } finally {
            setIsLoading(false);
        }
    };

    const handleComplete = async () => {
        if (!stage3Response.model || !stage3Response.response) return;
        setIsLoading(true);
        try {
            const messageData = {
                user_query: userQuery,
                stage1: stage1Responses,
                stage2: stage2Responses,
                stage3: stage3Response,
                metadata: { label_to_model: labelToModel, aggregate_rankings: aggregateRankings },
                title: manualTitle
            };
            await api.saveManualMessage(conversationId, messageData);
            alert('Conversation saved!');
            localStorage.removeItem(draftKey);
            onComplete();
        } catch (error) {
            alert('Failed to save message');
        } finally {
            setIsLoading(false);
        }
    };

    const renderStep1 = () => (
        <div className="wizard-step">
            <h3>{isFollowUp ? 'Step 1: Follow Up Opinions' : 'Step 1: Initial Opinions'}</h3>
            <p className="step-desc">Enter query and add model responses.</p>
            <div className="automation-settings">
                <label>Automation Model:</label>
                <div className="automation-input-row">
                    <div className="model-select-wrapper">
                        <select value={aiStudioModel} onChange={(e) => setAiStudioModel(e.target.value)} className="automation-model-select">
                            <optgroup label="AI Studio">
                                {automationModels.ai_studio.map(m => <option key={m.id} value={m.name}>{m.name}</option>)}
                            </optgroup>
                            {automationModels.chatgpt?.length > 0 && (
                                <optgroup label="ChatGPT">
                                    {automationModels.chatgpt.map(m => <option key={m.id} value={m.name}>{m.name}</option>)}
                                </optgroup>
                            )}
                            {automationModels.claude?.length > 0 && (
                                <optgroup label="Claude">
                                    {automationModels.claude.map(m => <option key={m.id} value={m.name}>{m.name}</option>)}
                                </optgroup>
                            )}
                        </select>
                        <button className="sync-council-btn" onClick={() => { if (onAddLlmName) { onAddLlmName(aiStudioModel); setCurrentModel(aiStudioModel); } }} disabled={llmNames.includes(aiStudioModel)}>
                            {llmNames.includes(aiStudioModel) ? '✓ In Council' : '+ Add to Council'}
                        </button>
                    </div>
                </div>
            </div>
            <div className="form-group">
                <label>Your Question:</label>
                <textarea value={userQuery} onChange={(e) => setUserQuery(e.target.value)} rows={4} />
            </div>
            <div className="responses-list">
                {stage1Responses.map((r, i) => <div key={i} className="response-item"><ModelBadge model={r.model} />: {r.response.substring(0, 50)}...</div>)}
            </div>
            <div className="add-response-form">
                <div className="model-input-group">
                    <select value={llmNames.includes(currentModel) ? currentModel : 'custom'} onChange={(e) => setCurrentModel(e.target.value === 'custom' ? '' : e.target.value)} className="model-select">
                        {llmNames.map(name => <option key={name} value={name}>{name}</option>)}
                        <option value="custom">Custom...</option>
                    </select>
                    {!llmNames.includes(currentModel) && <input value={currentModel} onChange={(e) => setCurrentModel(e.target.value)} className="custom-model-input" placeholder="Model Name" />}
                </div>
                <textarea value={currentText} onChange={(e) => setCurrentText(e.target.value)} rows={8} placeholder="Model Response" />
                <div className="add-response-actions">
                    <button onClick={addStage1Response} disabled={!currentModel || !currentText}>Add Response</button>
                    <div className="automation-row">
                        <button onClick={() => handleRunAutomation(isFollowUp ? getContextText() : userQuery, 'ai_studio')} className="automation-btn ai-studio-btn" disabled={isAutomating || !userQuery || isChatGPTSelected || isClaudeSelected || !currentModel}>Run via AI Studio</button>
                        <button onClick={() => handleRunAutomation(isFollowUp ? getContextText() : userQuery, 'chatgpt')} className="automation-btn chatgpt-btn" disabled={isAutomating || !userQuery || isGeminiSelected || isClaudeSelected || !currentModel} style={{ backgroundColor: '#10a37f' }}>Run via ChatGPT</button>
                        <button onClick={() => handleRunAutomation(isFollowUp ? getContextText() : userQuery, 'claude')} className="automation-btn claude-btn" disabled={isAutomating || !userQuery || isGeminiSelected || isChatGPTSelected || !currentModel} style={{ backgroundColor: '#d97757' }}>Run via Claude</button>
                    </div>
                </div>
                <div className="wizard-actions">
                    <div className="left-actions">
                        <button onClick={onCancel} className="secondary-btn">Cancel</button>
                        {(userQuery || stage1Responses.length > 0) && <button onClick={() => { if (window.confirm('Reset?')) { localStorage.removeItem(draftKey); window.location.reload(); } }} className="secondary-btn discard-btn">Discard</button>}
                    </div>
                    <button onClick={handleGoToStep2} className="primary-btn" disabled={!userQuery || stage1Responses.length === 0}>Next: Peer Review</button>
                </div>
            </div>
        </div>
    );

    const renderStep2 = () => (
        <div className="wizard-step">
            <h3>Step 2: Peer Review</h3>
            <div className="wizard-title-display"><strong>Title:</strong> {manualTitle || 'Generating...'}</div>
            <div className="prompt-box">
                <label>Stage 2 Prompt:</label>
                <div className="prompt-preview">{stage2Prompt}</div>
                <button onClick={() => copyToClipboard(stage2Prompt)} className="copy-btn">Copy Prompt</button>
            </div>
            <div className="responses-list">
                {stage2Responses.map((r, i) => <div key={i} className="response-item"><ModelBadge model={r.model} />: {r.ranking.substring(0, 50)}...</div>)}
            </div>
            <div className="add-response-form">
                <select value={currentModel} onChange={(e) => setCurrentModel(e.target.value)} className="model-select">
                    <option value="">Select Reviewer</option>
                    <optgroup label="Stage 1 Participants">{stage1Responses.map((r, i) => <option key={i} value={r.model}>{r.model}</option>)}</optgroup>
                    <optgroup label="Other">{llmNames.filter(n => !stage1Responses.some(r => r.model === n)).map(n => <option key={n} value={n}>{n}</option>)}</optgroup>
                </select>
                <textarea value={currentText} onChange={(e) => setCurrentText(e.target.value)} rows={8} placeholder="Paste Ranking" />
                <div className="add-response-actions">
                    <button onClick={addStage2Response} disabled={!currentModel || !currentText}>Add Ranking</button>
                    <div className="automation-row">
                        <button onClick={() => handleRunAutomation(stage2Prompt, 'ai_studio')} className="automation-btn ai-studio-btn" disabled={isAutomating || !stage2Prompt || isChatGPTSelected || isClaudeSelected || !currentModel}>Run via AI Studio</button>
                        <button onClick={() => handleRunAutomation(stage2Prompt, 'chatgpt')} className="automation-btn chatgpt-btn" disabled={isAutomating || !stage2Prompt || isGeminiSelected || isClaudeSelected || !currentModel} style={{ backgroundColor: '#10a37f' }}>Run via ChatGPT</button>
                        <button onClick={() => handleRunAutomation(stage2Prompt, 'claude')} className="automation-btn claude-btn" disabled={isAutomating || !stage2Prompt || isGeminiSelected || isChatGPTSelected || !currentModel} style={{ backgroundColor: '#d97757' }}>Run via Claude</button>
                    </div>
                </div>
                <div className="wizard-actions">
                    <div className="left-actions">
                        <button onClick={() => setStep(1)} className="secondary-btn">Back</button>
                        <button onClick={() => { if (window.confirm('Reset?')) { localStorage.removeItem(draftKey); window.location.reload(); } }} className="secondary-btn discard-btn">Discard</button>
                    </div>
                    <button onClick={handleGoToStep3} className="primary-btn" disabled={stage2Responses.length === 0}>Next: Synthesis</button>
                </div>
            </div>
        </div>
    );

    const renderStep3 = () => (
        <div className="wizard-step">
            <h3>Step 3: Synthesis</h3>
            <div className="prompt-col-layout">
                <div className="prompt-box">
                    <label>Chairman Prompt:</label>
                    <div className="prompt-preview">{stage3Prompt}</div>
                    <button onClick={() => copyToClipboard(stage3Prompt)} className="copy-btn">Copy Prompt</button>
                </div>
                <div className="mapping-box">
                    <label>Mapping:</label>
                    <div className="mapping-list">{Object.entries(labelToModel).map(([l, m]) => <div key={l} className="mapping-item"><strong>{l}</strong> = <ModelBadge model={m} /></div>)}</div>
                </div>
            </div>
            <div className="form-group">
                <label>Final Synthesis:</label>
                <div className="chairman-input-row" style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                        <select value={stage3Response.model} onChange={(e) => setStage3Response({ ...stage3Response, model: e.target.value })} className="model-select">
                            <option value="Manual Chairman">Manual Chairman</option>
                            {stage1Responses.map((r, i) => <option key={i} value={r.model}>{r.model}</option>)}
                        </select>
                        <div className="automation-row">
                            <button onClick={() => handleRunStage3Automation(stage3Prompt, 'ai_studio')} className="automation-btn stage3-auto-btn ai-studio-btn" disabled={isAutomating || !stage3Prompt || isChatGPTSelected || isClaudeSelected || stage3Response.model === 'Manual Chairman'}>AI Studio</button>
                            <button onClick={() => handleRunStage3Automation(stage3Prompt, 'chatgpt')} className="automation-btn stage3-auto-btn chatgpt-btn" disabled={isAutomating || !stage3Prompt || isGeminiSelected || isClaudeSelected || stage3Response.model === 'Manual Chairman'} style={{ backgroundColor: '#10a37f' }}>ChatGPT</button>
                            <button onClick={() => handleRunStage3Automation(stage3Prompt, 'claude')} className="automation-btn stage3-auto-btn claude-btn" disabled={isAutomating || !stage3Prompt || isGeminiSelected || isChatGPTSelected || stage3Response.model === 'Manual Chairman'} style={{ backgroundColor: '#d97757' }}>Claude</button>
                        </div>
                    </div>
                    <textarea value={stage3Response.response || ''} onChange={(e) => setStage3Response({ ...stage3Response, response: e.target.value })} rows={12} placeholder="Final answer..." />
                </div>
                <div className="wizard-actions">
                    <div className="left-actions">
                        <button onClick={() => setStep(2)} className="secondary-btn">Back</button>
                        <button onClick={() => { if (window.confirm('Reset?')) { localStorage.removeItem(draftKey); window.location.reload(); } }} className="secondary-btn discard-btn">Discard</button>
                    </div>
                    <button onClick={handleComplete} className="primary-btn complete-btn" disabled={!stage3Response.response}>Finish & Save</button>
                </div>
            </div>
        </div>
    );

    if (isLoading) return <div className="manual-wizard-loading">Processing...</div>;

    return (
        <div className="manual-wizard">
            {(isGeneratingTitle || isAutomating) && (
                <div className="modal-overlay">
                    <div className="modal-content">
                        <div className="modal-spinner" />
                        <div className="modal-text">{isGeneratingTitle ? 'Generating title...' : 'Running automation...'}</div>
                    </div>
                </div>
            )}
            {step === 1 && renderStep1()}
            {step === 2 && renderStep2()}
            {step === 3 && renderStep3()}
        </div>
    );
}
