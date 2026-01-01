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

export default function ManualWizard({ conversationId, currentTitle, previousMessages = [], llmNames = [], onAddLlmName, onComplete, onCancel, automationModels = { ai_studio: [], chatgpt: [] }, onTitleUpdate, initialQuestion = '' }) {
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
    // Default to first model if available, or empty string. Avoid "Manual Chairman" as default.
    const [stage3Response, setStage3Response] = useState(savedDraft.stage3Response || { model: '', response: '' }); // { model, response }
    const [manualTitle, setManualTitle] = useState(savedDraft.manualTitle || (currentTitle !== 'New Conversation' ? currentTitle : ''));
    const [aggregateRankings, setAggregateRankings] = useState(savedDraft.aggregateRankings || []);
    const [aiStudioModel, setAiStudioModel] = useState(savedDraft.aiStudioModel || (automationModels.ai_studio[0]?.name) || 'Gemini 2.5 Flash');
    const [isLoadingModels, setIsLoadingModels] = useState(false);

    // Input State for current item
    const [currentModel, setCurrentModel] = useState(savedDraft.currentModel || llmNames[0] || '');
    const [currentText, setCurrentText] = useState(savedDraft.currentText || '');

    // Load available models for automation - OBSOLETE: Now handled globally
    // But we still want to set a default model if aiStudioModel is just the default placeholder
    // But we still want to set a default model if aiStudioModel is just the default placeholder
    useEffect(() => {
        const fallbacks = ['Gemini 3 Flash', 'Gemini 2.5 Flash', 'Gemini 1.5 Flash'];
        const isFallback = !aiStudioModel || fallbacks.includes(aiStudioModel);

        if (automationModels.ai_studio.length > 0) {
            const inGeminiList = automationModels.ai_studio.find(m => m.name === aiStudioModel);
            const inGptList = automationModels.chatgpt && automationModels.chatgpt.find(m => m.name === aiStudioModel);

            // If current model is a fallback or (not in Gemini list AND not in GPT list), pick the best Gemini one
            // We basically only auto-switch if the current selection effectively became invalid or is a generic default.
            // If it's a valid GPT model, we leave it alone.
            if (isFallback || (!inGeminiList && !inGptList)) {
                // Only reset if we are sure it's not a custom user entry that we should preserve?
                // But previously it enforced list membership. Let's stick to that but expanded.
                // If it's "custom" (user typed), we should probably respect it too?
                // But the previous logic was strict about `currentInList`. 
                // Let's at least allow GPT models.

                // However, we must be careful: if the user JUST typed a custom name, we don't want to wipe it.
                // But this effect depends on [automationModels.ai_studio]. It runs when LIST updates.
                // So if list updates and my custom text isn't in it, I get wiped? That's bad UX if polling happens.
                // But assuming normal usage...

                const defaultModel = automationModels.ai_studio[0]?.name;
                if (defaultModel) {
                    setAiStudioModel(defaultModel);
                }
            }
        }
    }, [automationModels.ai_studio, automationModels.chatgpt]);

    // Helpers for button disabling
    // Normalize string for checking: remove spaces and lowercase
    const normalizeModelName = (name) => name ? name.toLowerCase().replace(/\s+/g, '') : '';

    // Check using normalized names so "Chat GPT" and "ChatGPT" both match "chatgpt"
    // We need to determine the "active" model being considered for the current step
    // to correctly disable buttons based on what the user is actually looking at/selecting.
    let activeModel = aiStudioModel;
    if (step === 1 || step === 2) {
        if (currentModel) activeModel = currentModel;
    } else if (step === 3) {
        if (stage3Response.model && stage3Response.model !== 'Manual Chairman') {
            activeModel = stage3Response.model;
        }
    }

    const isChatGPTSelected = activeModel && normalizeModelName(activeModel).includes('chatgpt');
    const isGeminiSelected = activeModel && normalizeModelName(activeModel).includes('gemini');

    // --- Persistence ---
    useEffect(() => {
        const draft = {
            step,
            userQuery,
            stage1Responses,
            stage2Prompt,
            labelToModel,
            stage2Responses,
            stage3Prompt,
            stage3Response,
            manualTitle,
            aggregateRankings,
            aiStudioModel,
            currentModel,
            currentText
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
The title should be concise and descriptive. Do not use quotes or punctuation in the title.

Question: ${query}

Title:`;
            // Force using Flash model for title generation
            const titleData = await api.runAutomation(titlePrompt, 'Gemini 2.5 Flash', 'ai_studio');
            const generatedTitle = titleData.response.trim().replace(/["']/g, '');
            setManualTitle(generatedTitle);

            // Update in backend
            await api.updateConversationTitle(conversationId, generatedTitle);

            // Update in parent (App) so sidebar reflects it immediately
            if (onTitleUpdate) {
                onTitleUpdate(conversationId, generatedTitle);
            }
        } catch (err) {
            console.error('Failed to generate title, continuing without one', err);
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

            // Advance to next model in council
            const currentIndex = llmNames.indexOf(currentModel);
            if (currentIndex !== -1 && currentIndex < llmNames.length - 1) {
                setCurrentModel(llmNames[currentIndex + 1]);
            } else {
                setCurrentModel('');
            }
            setCurrentText('');
        }
    };

    const addStage2Response = () => {
        if (currentModel && currentText) {
            setStage2Responses([...stage2Responses, { model: currentModel, ranking: currentText }]);

            // Determine possible reviewer models (same list as in the dropdown)
            const stage1Models = stage1Responses.map(r => r.model);
            const otherModels = llmNames.filter(name => !stage1Models.includes(name));
            const allReviewerModels = [...stage1Models, ...otherModels];

            const currentIndex = allReviewerModels.indexOf(currentModel);
            if (currentIndex !== -1 && currentIndex < allReviewerModels.length - 1) {
                setCurrentModel(allReviewerModels[currentIndex + 1]);
            } else {
                setCurrentModel('');
            }
            setCurrentText('');
        }
    };

    const handleRunAutomation = async (prompt, provider = "ai_studio") => {
        if (!prompt) return;
        setIsAutomating(true);
        setCurrentText(''); // Clear existing text
        try {
            let modelToUse = aiStudioModel;
            console.log(`[DEBUG] Step 1 Automation provider: ${provider}`);

            if (provider === 'chatgpt') {
                const normName = (name) => name ? name.toLowerCase().replace(/\s+/g, '') : '';

                // If the selected automation model IS a ChatGPT model, use it directly
                if (aiStudioModel && normName(aiStudioModel).includes('chatgpt')) {
                    modelToUse = aiStudioModel;
                } else {
                    // Fallback logic
                    const chatGptModels = (llmNames || []).filter(n => normName(n).includes('chatgpt'));
                    const thinkingModel = chatGptModels.find(n => n.toLowerCase().includes('thinking'));

                    if (currentModel && normName(currentModel).includes('chatgpt')) {
                        modelToUse = currentModel;
                    } else {
                        modelToUse = thinkingModel || chatGptModels[0] || 'ChatGPT';
                    }
                }

                if (!modelToUse.toLowerCase().includes('thinking') && !modelToUse.toLowerCase().includes('o1')) {
                    if (!modelToUse.toLowerCase().includes('thinking')) {
                        modelToUse += ' Thinking';
                    }
                }
            }

            console.log(`[DEBUG] Final model: ${modelToUse}`);
            const data = await api.runAutomation(prompt, modelToUse, provider);
            setCurrentText(data.response);
        } catch (error) {
            console.error(error);
            alert(`Automation failed: ${error.message}`);
        } finally {
            setIsAutomating(false);
        }
    };

    const handleRunStage3Automation = async (prompt, provider = "ai_studio") => {
        if (!prompt) return;
        setIsAutomating(true);
        setStage3Response(prev => ({ ...prev, response: '' })); // Clear existing text
        try {
            let modelToUse = aiStudioModel;
            console.log(`[DEBUG] Stage 3 Automation provider: ${provider}`);

            if (provider === 'chatgpt') {
                const normName = (name) => name ? name.toLowerCase().replace(/\s+/g, '') : '';
                const chatGptModels = (llmNames || []).filter(n => normName(n).includes('chatgpt'));
                const thinkingModel = chatGptModels.find(n => n.toLowerCase().includes('thinking'));

                if (stage3Response.model && normName(stage3Response.model).includes('chatgpt')) {
                    modelToUse = stage3Response.model;
                } else {
                    modelToUse = thinkingModel || chatGptModels[0] || 'ChatGPT';
                }

                if (!modelToUse.toLowerCase().includes('thinking') && !modelToUse.toLowerCase().includes('o1')) {
                    if (!modelToUse.toLowerCase().includes('thinking')) {
                        modelToUse += ' Thinking';
                    }
                }
            }

            console.log(`[DEBUG] Final Stage 3 model: ${modelToUse}`);
            const data = await api.runAutomation(prompt, modelToUse, provider);
            setStage3Response(prev => ({ ...prev, response: data.response }));
        } catch (error) {
            console.error(error);
            alert(`Automation failed: ${error.message}`);
        } finally {
            setIsAutomating(false);
        }
    };

    // --- Navigation Handlers ---

    const handleGoToStep2 = async () => {
        if (!userQuery.trim() || stage1Responses.length === 0) return;

        setIsLoading(true);
        try {
            // Generate title if it hasn't been set yet
            if (!manualTitle || manualTitle === 'New Conversation') {
                await generateTitle(userQuery);
            }

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
            // Pass aggregate_rankings to step 3 or state
            setAggregateRankings(processedData.aggregate_rankings);

            // If entering Stage 3 and no model selected yet (or it's Manual Chairman which we want to avoid as default for automation context),
            // auto-select the first real model from Stage 1 if available.
            if (!stage3Response.model || stage3Response.model === 'Manual Chairman') {
                if (stage1Responses.length > 0) {
                    setStage3Response(prev => ({ ...prev, model: stage1Responses[0].model }));
                }
            }

            setStep(3);
        } catch (error) {
            console.error(error);
            alert('Failed to process rankings or generate Stage 3 prompt');
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
                stage3: {
                    model: stage3Response.model,
                    response: stage3Response.response
                },
                metadata: {
                    label_to_model: labelToModel,
                    aggregate_rankings: aggregateRankings
                },
                title: manualTitle // Optional
            };

            await api.saveManualMessage(conversationId, messageData);

            // Feedback
            alert('Conversation saved successfully!');

            localStorage.removeItem(draftKey);
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

            <div className="automation-settings">
                <label>Automation Model:</label>
                <div className="automation-input-row">
                    <div className="model-select-wrapper">
                        <select
                            value={aiStudioModel}
                            onChange={(e) => {
                                const newModel = e.target.value;
                                setAiStudioModel(newModel);
                            }}
                            className="automation-model-select"
                        >
                            <optgroup label="AI Studio Models">
                                {automationModels.ai_studio.map(m => (
                                    <option key={m.id} value={m.name}>{m.name}</option>
                                ))}
                            </optgroup>
                            {automationModels.chatgpt && automationModels.chatgpt.length > 0 && (
                                <optgroup label="ChatGPT Models">
                                    {automationModels.chatgpt.map(m => (
                                        <option key={m.id} value={m.name}>{m.name}</option>
                                    ))}
                                </optgroup>
                            )}
                            {!automationModels.ai_studio.some(m => m.name === aiStudioModel) &&
                                (!automationModels.chatgpt || !automationModels.chatgpt.some(m => m.name === aiStudioModel)) && (
                                    <option value={aiStudioModel}>{aiStudioModel}</option>
                                )}
                            <option value="custom">Custom...</option>
                        </select>
                        {aiStudioModel === 'custom' && (
                            <input
                                type="text"
                                value=""
                                onChange={(e) => setAiStudioModel(e.target.value)}
                                placeholder="Enter custom model name"
                                className="custom-automation-input"
                                autoFocus
                            />
                        )}
                        <button
                            className="sync-council-btn"
                            onClick={() => {
                                if (onAddLlmName && aiStudioModel && !llmNames.includes(aiStudioModel)) {
                                    onAddLlmName(aiStudioModel);
                                    setCurrentModel(aiStudioModel); // Also set as active manual model
                                }
                            }}
                            disabled={llmNames.includes(aiStudioModel)}
                            title="Add to Council & Active Selection"
                        >
                            {llmNames.includes(aiStudioModel) ? '✓ In Council' : '+ Add to Council'}
                        </button>
                    </div>
                </div>
            </div>

            <div className="form-group">
                <label>{isFollowUp ? 'Your Follow Up Question:' : 'Your Question:'}</label>
                <textarea
                    value={userQuery}
                    onChange={(e) => setUserQuery(e.target.value)}
                    placeholder={isFollowUp ? 'What is your follow up question?' : 'What is your question?'}
                    rows={4}
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
                        <ModelBadge model={r.model} />: {r.response.substring(0, 50)}...
                    </div>
                ))}
            </div>

            <div className="add-response-form">
                <div className="model-input-group">
                    <select
                        value={llmNames.includes(currentModel) ? currentModel : 'custom'}
                        onChange={(e) => {
                            if (e.target.value === 'custom') {
                                setCurrentModel('');
                            } else {
                                setCurrentModel(e.target.value);
                            }
                        }}
                        className="model-select"
                    >
                        {llmNames.map(name => (
                            <option key={name} value={name}>{name}</option>
                        ))}
                        <option value="custom">Custom...</option>
                    </select>
                    {!llmNames.includes(currentModel) && (
                        <input
                            placeholder="Enter Model Name"
                            value={currentModel}
                            onChange={(e) => setCurrentModel(e.target.value)}
                            className="custom-model-input"
                        />
                    )}
                </div>
                <textarea
                    placeholder="Model Response"
                    value={currentText}
                    onChange={(e) => setCurrentText(e.target.value)}
                    rows={8}
                />
                <div className="add-response-actions">
                    <button onClick={addStage1Response} disabled={!currentModel || !currentText}>Add Response</button>
                    <button
                        onClick={() => handleRunAutomation(isFollowUp ? getContextText() : userQuery, 'ai_studio')}
                        className="automation-btn"
                        disabled={isAutomating || !userQuery || isChatGPTSelected || !currentModel}
                        title={!currentModel ? "Select a model below to enable" : (isChatGPTSelected ? "Select a Gemini model to enable" : "")}
                    >
                        {isAutomating ? 'Running...' : 'Run via AI Studio'}
                    </button>
                    <button
                        onClick={() => handleRunAutomation(isFollowUp ? getContextText() : userQuery, 'chatgpt')}
                        className="automation-btn chatgpt-btn"
                        disabled={isAutomating || !userQuery || isGeminiSelected || !currentModel}
                        style={{ backgroundColor: '#10a37f' }} // ChatGPT green
                        title={!currentModel ? "Select a model below to enable" : (isGeminiSelected ? "Select a ChatGPT model to enable" : "")}
                    >
                        {isAutomating ? 'Running...' : 'Run via ChatGPT'}
                    </button>
                </div>
            </div>

            <div className="wizard-actions">
                <div className="left-actions">
                    <button onClick={onCancel} className="secondary-btn">Cancel</button>
                    {(userQuery || stage1Responses.length > 0) && (
                        <button
                            onClick={() => {
                                if (window.confirm('Clear all entries and start over?')) {
                                    localStorage.removeItem(draftKey);
                                    window.location.reload(); // Simplest way to reset all state
                                }
                            }}
                            className="secondary-btn discard-btn"
                        >
                            Discard Draft
                        </button>
                    )}
                </div>
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
                <div className="wizard-title-display">
                    <strong>Conversation Title:</strong> {manualTitle || 'Generating...'}
                </div>
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
                        <ModelBadge model={r.model} />: {r.ranking.substring(0, 50)}...
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
                    <optgroup label="Stage 1 Participants">
                        {stage1Responses.map((r, i) => (
                            <option key={i} value={r.model}>{r.model}</option>
                        ))}
                    </optgroup>
                    <optgroup label="Other Council Members">
                        {llmNames.filter(name => !stage1Responses.some(r => r.model === name)).map(name => (
                            <option key={name} value={name}>{name}</option>
                        ))}
                    </optgroup>
                </select>
                <textarea
                    placeholder="Paste Ranking Response (must include 'FINAL RANKING:...')"
                    value={currentText}
                    onChange={(e) => setCurrentText(e.target.value)}
                    rows={8}
                />
                <div className="add-response-actions">
                    <button onClick={addStage2Response} disabled={!currentModel || !currentText}>Add Ranking</button>
                    <button
                        onClick={() => handleRunAutomation(stage2Prompt, 'ai_studio')}
                        className="automation-btn"
                        disabled={isAutomating || !stage2Prompt || isChatGPTSelected || !currentModel}
                        title={!currentModel ? "Select a model below to enable" : (isChatGPTSelected ? "Select a Gemini model to enable" : "")}
                    >
                        {isAutomating ? 'Running...' : 'Run via AI Studio'}
                    </button>
                    <button
                        onClick={() => handleRunAutomation(stage2Prompt, 'chatgpt')}
                        className="automation-btn chatgpt-btn"
                        disabled={isAutomating || !stage2Prompt || isGeminiSelected || !currentModel}
                        style={{ backgroundColor: '#10a37f' }}
                        title={!currentModel ? "Select a model below to enable" : (isGeminiSelected ? "Select a ChatGPT model to enable" : "")}
                    >
                        {isAutomating ? 'Running...' : 'Run via ChatGPT'}
                    </button>
                </div>
            </div>

            <div className="wizard-actions">
                <div className="left-actions">
                    <button onClick={() => setStep(1)} className="secondary-btn">Back</button>
                    <button
                        onClick={() => {
                            if (window.confirm('Clear all entries and start over?')) {
                                localStorage.removeItem(draftKey);
                                window.location.reload();
                            }
                        }}
                        className="secondary-btn discard-btn"
                    >
                        Discard Draft
                    </button>
                </div>
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
                                <strong>{label}</strong> = <ModelBadge model={model} />
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
                    <button
                        onClick={() => handleRunStage3Automation(stage3Prompt, 'ai_studio')}
                        className="automation-btn stage3-auto-btn"
                        disabled={isAutomating || !stage3Prompt || isChatGPTSelected || stage3Response.model === 'Manual Chairman'}
                        title={stage3Response.model === 'Manual Chairman' ? "Select a valid model to automate" : (isChatGPTSelected ? "Select a Gemini model to enable" : "")}
                    >
                        {isAutomating ? 'Automating...' : 'Run via AI Studio'}
                    </button>
                    <button
                        onClick={() => handleRunStage3Automation(stage3Prompt, 'chatgpt')}
                        className="automation-btn stage3-auto-btn chatgpt-btn"
                        disabled={isAutomating || !stage3Prompt || isGeminiSelected || stage3Response.model === 'Manual Chairman'}
                        style={{ backgroundColor: '#10a37f', marginLeft: '5px' }}
                        title={stage3Response.model === 'Manual Chairman' ? "Select a valid model to automate" : (isGeminiSelected ? "Select a ChatGPT model to enable" : "")}
                    >
                        {isAutomating ? 'Automating...' : 'Run via ChatGPT'}
                    </button>
                </div>
                <textarea
                    className="final-response-input"
                    value={stage3Response.response || ''}
                    onChange={(e) => setStage3Response({ ...stage3Response, response: e.target.value })}
                    placeholder="Paste the final answer here..."
                    rows={12}
                />
            </div>

            <div className="wizard-actions">
                <div className="left-actions">
                    <button onClick={() => setStep(2)} className="secondary-btn">Back</button>
                    <button
                        onClick={() => {
                            if (window.confirm('Clear all entries and start over?')) {
                                localStorage.removeItem(draftKey);
                                window.location.reload();
                            }
                        }}
                        className="secondary-btn discard-btn"
                    >
                        Discard Draft
                    </button>
                </div>
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
            {(isGeneratingTitle || isAutomating) && (
                <div className="modal-overlay">
                    <div className="modal-content">
                        <div className="modal-spinner"></div>
                        <div className="modal-text">
                            {isGeneratingTitle ? 'Generating conversation title...' : 'Running automation...'}
                        </div>
                    </div>
                </div>
            )}
            {step === 1 && renderStep1()}
            {step === 2 && renderStep2()}
            {step === 3 && renderStep3()}
        </div>
    );
}
