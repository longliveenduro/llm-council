import { useState, useEffect, useRef, useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import remarkGfm from 'remark-gfm';
import 'katex/dist/katex.min.css';
import { api } from '../api';
import { getModelIcon } from '../utils/modelIcons';
import './WebChatBotWizard.css';

const ModelBadge = ({ model }) => {
    const iconUrl = getModelIcon(model);
    return (
        <span className="model-badge" title={model}>
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

const parseRankingFromText = (rankingText) => {
    if (!rankingText) return [];

    // Look for "FINAL RANKING:" section
    if (rankingText.includes("FINAL RANKING:")) {
        const parts = rankingText.split("FINAL RANKING:");
        if (parts.length >= 2) {
            const rankingSection = parts[1];
            // Try to extract numbered list format (e.g., "1. Response A")
            const numberedMatches = rankingSection.match(/\d+\.\s*Response [A-Z]/g);
            if (numberedMatches) {
                return numberedMatches.map(m => m.match(/Response [A-Z]/)[0]);
            }

            // Fallback: Extract all "Response X" patterns in order
            const matches = rankingSection.match(/Response [A-Z]/g);
            return matches || [];
        }
    }

    // Fallback: try to find any "Response X" patterns in order in the whole text
    const matches = rankingText.match(/Response [A-Z]/g);
    return matches || [];
};

const calculateCurrentScores = (stage2Responses, labelToModel) => {
    if (!stage2Responses || stage2Responses.length === 0) return {};

    const modelPositions = {}; // modelName -> list of positions
    const labelToModelMap = labelToModel || {};

    stage2Responses.forEach(r => {
        const rankingText = r.ranking || "";
        const parsedRanking = parseRankingFromText(rankingText);

        parsedRanking.forEach((label, index) => {
            const modelName = labelToModelMap[label];
            if (modelName) {
                if (!modelPositions[modelName]) modelPositions[modelName] = [];
                modelPositions[modelName].push(index + 1);
            }
        });
    });

    const aggregate = [];
    Object.entries(modelPositions).forEach(([model, positions]) => {
        if (positions.length > 0) {
            const avgRank = positions.reduce((a, b) => a + b, 0) / positions.length;
            aggregate.push({
                model,
                avgRank: Math.round(avgRank * 10) / 10,
                count: positions.length
            });
        }
    });

    // Sort by avgRank (lower is better)
    aggregate.sort((a, b) => a.avgRank - b.avgRank);

    // Assign medals based on rank
    const scores = {};
    let currentRankIndex = 0;
    aggregate.forEach((item, i) => {
        if (i > 0 && item.avgRank > aggregate[i - 1].avgRank) {
            currentRankIndex = i;
        }

        let medal = null;
        if (currentRankIndex === 0) medal = '🥇';
        else if (currentRankIndex === 1) medal = '🥈';
        else if (currentRankIndex === 2) medal = '🥉';

        scores[item.model] = {
            avgRank: item.avgRank,
            medal: medal,
            rankIndex: currentRankIndex
        };
    });

    return scores;
};

const MappingBox = ({ labelToModel, scores = {}, showScoreExplanation = false }) => {
    if (!labelToModel || Object.keys(labelToModel).length === 0) return null;
    return (
        <div className="mapping-box">
            <div className="mapping-header">
                <label>Mapping:</label>
                {showScoreExplanation && <span className="score-explanation">(Lower is better)</span>}
            </div>
            <div className="mapping-list">
                {Object.entries(labelToModel).map(([l, m]) => {
                    const score = scores[m];
                    return (
                        <div key={l} className="mapping-item">
                            <div className="mapping-item-main">
                                <strong>{l.replace('Response ', 'Model ')}</strong> = <ModelBadge model={m} />
                            </div>
                            {score && score.count !== 0 && (
                                <div className="mapping-item-score" title={`Average Rank: ${score.avgRank}`}>
                                    {score.medal && <span className="score-medal">{score.medal}</span>}
                                    <span className="score-rank">{score.avgRank}</span>
                                </div>
                            )}
                        </div>
                    );
                })}
            </div>
        </div>
    );
};

export default function WebChatBotWizard({ conversationId, currentTitle, previousMessages = [], llmNames = [], onAddLlmName, onComplete, onCancel, automationModels = { ai_studio: [], chatgpt: [], claude: [] }, onTitleUpdate, initialQuestion = '' }) {
    const draftKey = `web_chatbot_draft_${conversationId}`;
    const savedDraft = JSON.parse(localStorage.getItem(draftKey) || '{}');

    const [step, setStep] = useState(savedDraft.step || 1); // 1: Opinions, 2: Review, 3: Synthesis
    const [isLoading, setIsLoading] = useState(false);
    const [isAutomating, setIsAutomating] = useState(false);

    const isFollowUp = previousMessages.length > 0;

    const isDanglingUser = previousMessages.length > 0 && previousMessages[previousMessages.length - 1].role === 'user';
    const danglingContent = isDanglingUser ? previousMessages[previousMessages.length - 1].content : '';

    // Data State
    const [userQuery, setUserQuery] = useState(savedDraft.userQuery || initialQuestion || danglingContent || '');
    const [stage1Responses, setStage1Responses] = useState(savedDraft.stage1Responses || []); // { model, response }
    const [stage2Prompt, setStage2Prompt] = useState(savedDraft.stage2Prompt || '');
    const [labelToModel, setLabelToModel] = useState(savedDraft.labelToModel || {});
    const [stage2Responses, setStage2Responses] = useState(savedDraft.stage2Responses || []); // { model, ranking }
    const [stage3Prompt, setStage3Prompt] = useState(savedDraft.stage3Prompt || '');
    const [stage3Response, setStage3Response] = useState(savedDraft.stage3Response || { model: '', response: '' }); // { model, response }
    const [manualTitle, setManualTitle] = useState(savedDraft.manualTitle || (currentTitle !== 'New Conversation' ? currentTitle : ''));
    const [aggregateRankings, setAggregateRankings] = useState(savedDraft.aggregateRankings || []);
    const [aiStudioModel, setAiStudioModel] = useState(savedDraft.aiStudioModel || (automationModels.ai_studio[0]?.name) || 'Gemini 2.5 Flash');
    const [preselectionReason, setPreselectionReason] = useState(savedDraft.preselectionReason || '');

    // Input State for current item
    const [currentModel, setCurrentModel] = useState(savedDraft.currentModel || llmNames[0] || '');
    const [currentText, setCurrentText] = useState(savedDraft.currentText || '');
    const [showPreview, setShowPreview] = useState(false); // Step 1 Preview Toggle - default to Write mode
    const [showStep3Preview, setShowStep3Preview] = useState(false); // Step 3 Preview Toggle - default to Write mode
    const [lastThinkingUsed, setLastThinkingUsed] = useState(null); // null, true, or false - tracks if last automation used thinking
    const [lastAutomationProvider, setLastAutomationProvider] = useState(null); // tracks which provider was used for last automation

    const currentScores = useMemo(() => {
        return calculateCurrentScores(stage2Responses, labelToModel);
    }, [stage2Responses, labelToModel]);

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
        if (stage3Response.model && stage3Response.model !== 'Web ChatBot Chairman') {
            activeModel = stage3Response.model;
        }
    }

    const getProviderInfo = (model) => {
        const n = normalizeName(model);
        if (n.includes('chatgpt')) return { label: 'ChatGPT', key: 'chatgpt', color: '#10a37f' };
        if (n.includes('claude')) return { label: 'Claude', key: 'claude', color: '#d97757' };
        return { label: 'AI Studio', key: 'ai_studio', color: '' };
    };

    const providerInfo = getProviderInfo(activeModel);

    // --- Persistence ---
    useEffect(() => {
        const draft = {
            step, userQuery, stage1Responses, stage2Prompt, labelToModel,
            stage2Responses, stage3Prompt, stage3Response, manualTitle,
            aggregateRankings, aiStudioModel, currentModel, currentText, preselectionReason
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
        let contextBuffer = '';
        let turnCount = 1;
        // Robustly pair User and Assistant messages.
        // Only include a User message if it is followed by an Assistant message.
        // This automatically excludes any trailing/dangling user messages.

        let i = 0;
        while (i < previousMessages.length) {
            const msg = previousMessages[i];

            if (msg.role === 'user') {
                // Check if next message exists and is assistant
                if (i + 1 < previousMessages.length && previousMessages[i + 1].role === 'assistant') {
                    // Start of a valid turn
                    contextBuffer += `User Question ${turnCount}: ${msg.content}\n`;
                    // Move to assistant
                    i++;
                    const assistantMsg = previousMessages[i];
                    contextBuffer += `LLM Answer ${turnCount}: ${assistantMsg.stage3?.response || "(No response)"}\n\n`;
                    turnCount++;
                } else {
                    // Dangling user message (or followed by another user message?), skip it from context
                    // matches the logic that this should be the "Current Question"
                }
            } else if (msg.role === 'assistant') {
                // Orphaned assistant message? Should not happen in normal flow, but if so, ignore or handle?
                // For now, ignore as we expect User -> Assistant structure
            }
            i++;
        }

        let text = '';
        if (contextBuffer) {
            text += `Context so far:\n\n${contextBuffer}`;
            text += `Current Question: ${userQuery}`;
        } else {
            text = userQuery;
        }
        return text;
    };

    const addStage1Response = () => {
        if (currentModel && currentText) {
            const existingIdx = stage1Responses.findIndex(r => r.model === currentModel);
            let newResponses;

            // Determine the model name to use (potentially with Thinking suffix)
            let modelNameToUse = currentModel;

            // Only add thinking suffix if:
            // 1. lastThinkingUsed is true
            // 2. The model doesn't already have a thinking-related suffix
            // 3. The provider was Claude or ChatGPT (Gemini always has thinking, doesn't need suffix)
            if (lastThinkingUsed === true && lastAutomationProvider !== 'ai_studio') {
                const hasThinkingSuffix = modelNameToUse.toLowerCase().includes('thinking') ||
                    modelNameToUse.toLowerCase().includes('[ext.');
                if (!hasThinkingSuffix) {
                    if (lastAutomationProvider === 'claude') {
                        modelNameToUse += ' [Ext. Thinking]';
                    } else if (lastAutomationProvider === 'chatgpt') {
                        modelNameToUse += ' Thinking';
                    }
                }
            }

            if (existingIdx !== -1) {
                if (!window.confirm(`A response from "${currentModel}" has already been added. Do you want to overwrite the old response with the new one?`)) {
                    return;
                }
                newResponses = [...stage1Responses];
                newResponses[existingIdx] = { model: modelNameToUse, response: currentText };
            } else {
                newResponses = [...stage1Responses, { model: modelNameToUse, response: currentText }];
            }

            setStage1Responses(newResponses);

            // Immediately update mapping so it's visible in Stage 1
            const newMapping = {};
            newResponses.forEach((r, i) => {
                const label = String.fromCharCode(65 + i);
                newMapping[`Response ${label}`] = r.model;
            });
            setLabelToModel(newMapping);

            if (existingIdx === -1) {
                const nextIdx = llmNames.indexOf(currentModel) + 1;
                setCurrentModel(nextIdx > 0 && nextIdx < llmNames.length ? llmNames[nextIdx] : '');
            }
            setCurrentText('');
            // Reset thinking status after adding response
            setLastThinkingUsed(null);
            setLastAutomationProvider(null);
        }
    };

    const addStage2Response = () => {
        if (currentModel && currentText) {
            const existingIdx = stage2Responses.findIndex(r => r.model === currentModel);
            let newResponses;

            // Determine the model name to use (potentially with Thinking suffix)
            let modelNameToUse = currentModel;
            if (lastThinkingUsed === true && lastAutomationProvider !== 'ai_studio') {
                const norm = (name) => name ? name.toLowerCase().replace(/\s+/g, '') : '';
                const hasThinkingSuffix = modelNameToUse.toLowerCase().includes('thinking') ||
                    modelNameToUse.toLowerCase().includes('[ext.');
                if (!hasThinkingSuffix) {
                    if (lastAutomationProvider === 'claude') {
                        modelNameToUse += ' [Ext. Thinking]';
                    } else if (lastAutomationProvider === 'chatgpt') {
                        modelNameToUse += ' Thinking';
                    }
                }
            }

            if (existingIdx !== -1) {
                if (!window.confirm(`A response from "${currentModel}" has already been added. Do you want to overwrite the old response with the new one?`)) {
                    return;
                }
                newResponses = [...stage2Responses];
                newResponses[existingIdx] = { model: modelNameToUse, ranking: currentText };
            } else {
                newResponses = [...stage2Responses, { model: modelNameToUse, ranking: currentText }];
            }

            setStage2Responses(newResponses);

            if (existingIdx === -1) {
                const nextIdx = llmNames.indexOf(currentModel) + 1;
                setCurrentModel(nextIdx > 0 && nextIdx < llmNames.length ? llmNames[nextIdx] : '');
            }
            setCurrentText('');
            setLastThinkingUsed(null);
            setLastAutomationProvider(null);
        }
    };

    const handleRunAutomation = async (prompt, provider = "ai_studio") => {
        if (!prompt) return;
        setIsAutomating(true);
        setCurrentText('');
        setLastThinkingUsed(null);
        setLastAutomationProvider(null);
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
                const claudes = (llmNames || []).filter(n => norm(n).includes('claude'));
                modelToUse = (currentModel && norm(currentModel).includes('claude'))
                    ? currentModel
                    : (claudes.length > 0 ? claudes[0] : 'Claude 3.5 Sonnet');

                if (!modelToUse.toLowerCase().includes('thinking')) {
                    modelToUse += ' [Ext. Thinking]';
                }
            }

            const data = await api.runAutomation(prompt, modelToUse, provider);
            setCurrentText(data.response);
            setLastThinkingUsed(data.thinking_used ?? null);
            setLastAutomationProvider(provider);
            // Update currentModel to the base model (without thinking suffix for display)
            if (provider === 'claude' || provider === 'chatgpt') {
                // Set to base model name (the one from llmNames, not with suffix)
                const baseModel = (llmNames || []).find(n => norm(n).includes(provider === 'claude' ? 'claude' : 'chatgpt'));
                if (baseModel) {
                    setCurrentModel(baseModel);
                }
            }
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
        setLastThinkingUsed(null);
        setLastAutomationProvider(null);
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
                if (!modelToUse.toLowerCase().includes('thinking')) {
                    modelToUse += ' [Ext. Thinking]';
                }
            }

            const data = await api.runAutomation(prompt, modelToUse, provider);
            console.log(`Automation successful for ${provider}, setting response`);

            setLastThinkingUsed(data.thinking_used ?? null);
            setLastAutomationProvider(provider);

            // Clean display model and set response in one update
            let finalDisplayModel = stage3Response.model;
            if (provider === 'claude' || provider === 'chatgpt') {
                const baseModel = (llmNames || []).find(n => norm(n).includes(provider === 'claude' ? 'claude' : 'chatgpt'));
                if (baseModel) {
                    finalDisplayModel = baseModel;
                }
            }

            setStage3Response(prev => ({
                ...prev,
                response: data.response,
                model: finalDisplayModel
            }));
        } catch (error) {
            alert(`Automation failed: ${error.message}`);
        } finally {
            setIsAutomating(false);
        }
    };

    const getValidHistory = () => {
        const validMsgs = [];
        let i = 0;
        while (i < previousMessages.length) {
            const msg = previousMessages[i];
            if (msg.role === 'user') {
                if (i + 1 < previousMessages.length && previousMessages[i + 1].role === 'assistant') {
                    validMsgs.push(msg);
                    validMsgs.push(previousMessages[i + 1]);
                    i += 2;
                } else {
                    i++;
                }
            } else {
                i++;
            }
        }
        return validMsgs;
    };

    const handleGoToStep2 = async () => {
        if (!userQuery.trim() || stage1Responses.length === 0) return;
        setIsLoading(true);
        try {
            if (!manualTitle || manualTitle === 'New Conversation') await generateTitle(userQuery);
            const cleanHistory = getValidHistory();
            const data = await api.getStage2Prompt(userQuery, stage1Responses, cleanHistory);
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
            const cleanHistory = getValidHistory();
            const promptData = await api.getStage3Prompt(userQuery, stage1Responses, processed.stage2_results, cleanHistory);
            setStage3Prompt(promptData.prompt);
            setStage2Responses(processed.stage2_results);
            setAggregateRankings(processed.aggregate_rankings);

            const scores = calculateCurrentScores(processed.stage2_results, labelToModel);
            const winners = Object.entries(scores)
                .filter(([_, score]) => score.rankIndex === 0)
                .map(([model, _]) => model);

            if (winners.length > 0) {
                const winner = winners[0];
                setStage3Response(prev => ({ ...prev, model: winner }));
                setPreselectionReason(`Model "${winner}" was preselected because it had the highest scores in Stage 2.`);
            } else if (!stage3Response.model || stage3Response.model === 'Web ChatBot Chairman') {
                if (stage1Responses.length > 0) {
                    setStage3Response(prev => ({ ...prev, model: stage1Responses[0].model }));
                    setPreselectionReason('');
                }
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
            // Finalize Stage 3 model name with suffix if needed
            let finalStage3Model = stage3Response.model;
            if (lastThinkingUsed === true && lastAutomationProvider !== 'ai_studio') {
                const hasThinkingSuffix = finalStage3Model.toLowerCase().includes('thinking') ||
                    finalStage3Model.toLowerCase().includes('[ext.');
                if (!hasThinkingSuffix) {
                    if (lastAutomationProvider === 'claude') {
                        finalStage3Model += ' [Ext. Thinking]';
                    } else if (lastAutomationProvider === 'chatgpt') {
                        finalStage3Model += ' Thinking';
                    }
                }
            }

            const messageData = {
                user_query: userQuery,
                stage1: stage1Responses,
                stage2: stage2Responses,
                stage3: { ...stage3Response, model: finalStage3Model },
                metadata: { label_to_model: labelToModel, aggregate_rankings: aggregateRankings },
                title: manualTitle
            };
            await api.saveWebChatBotMessage(conversationId, messageData);
            alert('Conversation saved!');
            localStorage.removeItem(draftKey);
            onComplete();
        } catch (error) {
            alert('Failed to save message');
        } finally {
            setIsLoading(false);
        }
    };

    const [viewingResponse, setViewingResponse] = useState(null);
    const [viewingMode, setViewingMode] = useState('preview'); // 'preview' or 'source'

    const renderStep1 = () => (
        <div className="wizard-step">
            <h3>{isFollowUp ? 'Step 1: Follow Up Opinions' : 'Step 1: Initial Opinions'}</h3>
            <p className="step-desc">Enter query and add model responses. Click existing response to view full content.</p>
            <div className="automation-settings">
                <label>Automation Model:</label>
                <div className="automation-input-row">
                    <div className="model-select-wrapper">
                        <select id="automation-model-select" value={aiStudioModel} onChange={(e) => setAiStudioModel(e.target.value)} className="automation-model-select" aria-label="Automation Model">
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
                <label htmlFor="user-query">Your Question:</label>
                <textarea id="user-query" value={userQuery} onChange={(e) => setUserQuery(e.target.value)} rows={4} />
            </div>
            <div className={stage1Responses.length > 0 ? "prompt-col-layout" : ""}>
                <div className="responses-list" style={stage1Responses.length > 0 ? { flex: 2, marginBottom: 0 } : {}}>
                    {stage1Responses.length === 0 && <div className="no-responses-hint" style={{ color: 'var(--text-muted)', fontSize: '13px', fontStyle: 'italic', textAlign: 'center', padding: '12px' }}>No responses added yet.</div>}
                    {stage1Responses.map((r, i) => (
                        <div key={i} className="response-item clickable-response-item" onClick={() => setViewingResponse(r)} title="Click to view full response">
                            <div className="response-header">
                                <span className="response-model-label">Model {String.fromCharCode(65 + i)}:</span> <ModelBadge model={r.model} />:
                            </div>
                            <div className="response-preview">
                                {r.response.substring(0, 50)}...
                            </div>
                        </div>
                    ))}
                </div>
                {stage1Responses.length > 0 && <MappingBox labelToModel={labelToModel} scores={currentScores} />}
            </div>
            <div className="add-response-form">
                <div className="model-input-group">
                    <select id="current-model-select" value={currentModel} onChange={(e) => setCurrentModel(e.target.value)} className="model-select" aria-label="Current Model">
                        <option value="">Select Model...</option>
                        {llmNames.map(name => <option key={name} value={name}>{name}</option>)}
                    </select>
                    {lastThinkingUsed !== null && (
                        <span className={`thinking-indicator ${lastThinkingUsed ? 'thinking-on' : 'thinking-off'}`} title={lastThinkingUsed ? 'Thinking was enabled' : 'Thinking was not enabled'}>
                            {lastThinkingUsed ? '🧠 Thinking' : '💭 No Thinking'}
                        </span>
                    )}
                </div>

                <div className="input-tabs-container">
                    <div className="input-tabs">
                        <button
                            type="button"
                            className={`input-tab ${!showPreview ? 'active' : ''}`}
                            onClick={() => setShowPreview(false)}
                        >
                            Write
                        </button>
                        <button
                            type="button"
                            className={`input-tab ${showPreview ? 'active' : ''}`}
                            onClick={() => setShowPreview(true)}
                        >
                            Preview
                        </button>
                    </div>
                    <div className="input-content-wrapper" key={showPreview ? 'preview' : 'write'}>
                        {showPreview ? (
                            <div className="input-preview-content markdown-content">
                                {currentText ? (
                                    <ReactMarkdown
                                        remarkPlugins={[remarkMath, remarkGfm]}
                                        rehypePlugins={[rehypeKatex]}
                                    >
                                        {currentText}
                                    </ReactMarkdown>
                                ) : (
                                    <span style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>Nothing to preview</span>
                                )}
                            </div>
                        ) : (
                            <textarea value={currentText} onChange={(e) => setCurrentText(e.target.value)} rows={8} placeholder="Model Response" />
                        )}
                    </div>
                </div>
                <div className="add-response-actions">
                    <button onClick={addStage1Response} disabled={!currentModel || !currentText}>Add Response</button>
                    <div className="automation-row">
                        <button
                            onClick={() => handleRunAutomation(isFollowUp ? getContextText() : userQuery, providerInfo.key)}
                            className={`automation-btn ${providerInfo.key}-btn`}
                            disabled={isAutomating || !userQuery || !currentModel}
                            style={providerInfo.color ? { backgroundColor: providerInfo.color } : {}}
                        >
                            Run via {providerInfo.label}
                        </button>
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

            {/* Response Viewer Modal */}
            {viewingResponse && (
                <div className="response-modal-overlay" onClick={() => setViewingResponse(null)}>
                    <div className="response-modal-content" onClick={e => e.stopPropagation()} data-testid="response-modal">
                        <div className="response-modal-header">
                            <h3><ModelBadge model={viewingResponse.model} /> Response</h3>
                            <button className="response-modal-close-btn" onClick={() => setViewingResponse(null)}>×</button>
                        </div>
                        <div className="response-modal-body">
                            <div className="input-tabs">
                                <button
                                    className={`input-tab ${viewingMode === 'preview' ? 'active' : ''}`}
                                    onClick={() => setViewingMode('preview')}
                                >
                                    Preview
                                </button>
                                <button
                                    className={`input-tab ${viewingMode === 'source' ? 'active' : ''}`}
                                    onClick={() => setViewingMode('source')}
                                >
                                    Source
                                </button>
                            </div>
                            <div className="response-modal-content-area">
                                {viewingMode === 'preview' ? (
                                    <div className="markdown-content">
                                        <ReactMarkdown
                                            remarkPlugins={[remarkMath, remarkGfm]}
                                            rehypePlugins={[rehypeKatex]}
                                        >
                                            {viewingResponse.response}
                                        </ReactMarkdown>
                                    </div>
                                ) : (
                                    <textarea
                                        readOnly
                                        value={viewingResponse.response}
                                        style={{ cursor: 'text' }}
                                    />
                                )}
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );

    const renderStep2 = () => (
        <div className="wizard-step">
            <h3>Step 2: Peer Review</h3>
            <div className="wizard-title-display"><strong>Title:</strong> {manualTitle || 'Generating...'}</div>
            <div className="prompt-col-layout">
                <div className="prompt-box">
                    <label>Stage 2 Prompt:</label>
                    <div className="prompt-preview">{stage2Prompt}</div>
                    <button onClick={() => copyToClipboard(stage2Prompt)} className="copy-btn">Copy Prompt</button>
                </div>
                <MappingBox labelToModel={labelToModel} scores={currentScores} />
            </div>
            <div className="responses-list">
                {stage2Responses.map((r, i) => {
                    const label = Object.entries(labelToModel).find(([_, m]) => m === r.model)?.[0]?.replace('Response ', '') || '?';
                    return (
                        <div key={i} className="response-item">
                            <div className="response-header">
                                <span className="response-model-label">Model {label}:</span> <ModelBadge model={r.model} />:
                            </div>
                            <div className="response-preview">
                                {r.ranking.substring(0, 50)}...
                            </div>
                        </div>
                    );
                })}
            </div>
            <div className="add-response-form">
                <div className="model-input-group">
                    <select
                        value={currentModel}
                        onChange={(e) => setCurrentModel(e.target.value)}
                        className="model-select"
                        aria-label="Current Model"
                    >
                        <option value="">Select Reviewer</option>
                        {llmNames.map(name => <option key={name} value={name}>{name}</option>)}
                    </select>
                    {lastThinkingUsed !== null && (
                        <span className={`thinking-indicator ${lastThinkingUsed ? 'thinking-on' : 'thinking-off'}`} title={lastThinkingUsed ? 'Thinking was enabled' : 'Thinking was not enabled'}>
                            {lastThinkingUsed ? '🧠 Thinking' : '💭 No Thinking'}
                        </span>
                    )}
                </div>
                <textarea value={currentText} onChange={(e) => setCurrentText(e.target.value)} rows={8} placeholder="Paste Ranking" />
                <div className="add-response-actions">
                    <button onClick={addStage2Response} disabled={!currentModel || !currentText}>Add Ranking</button>
                    <div className="automation-row">
                        <button
                            onClick={() => handleRunAutomation(stage2Prompt, providerInfo.key)}
                            className={`automation-btn ${providerInfo.key}-btn`}
                            disabled={isAutomating || !stage2Prompt || !currentModel}
                            style={providerInfo.color ? { backgroundColor: providerInfo.color } : {}}
                        >
                            Run via {providerInfo.label}
                        </button>
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
        <div className="wizard-step step3-wizard">
            <h3>Step 3: Synthesis</h3>
            <div className="prompt-col-layout">
                <div className="prompt-box">
                    <label>Chairman Prompt:</label>
                    <div className="prompt-preview">{stage3Prompt}</div>
                    <button onClick={() => copyToClipboard(stage3Prompt)} className="copy-btn">Copy Prompt</button>
                </div>
                <MappingBox labelToModel={labelToModel} scores={currentScores} showScoreExplanation={true} />
            </div>
            <div className="stage3-synthesis-section">
                <label>Final Synthesis:</label>
                <div className="stage3-controls-row">
                    <div className="model-input-group">
                        <select
                            value={stage3Response.model}
                            onChange={(e) => setStage3Response({ ...stage3Response, model: e.target.value })}
                            className="model-select"
                            aria-label="Select Synthesis Model"
                        >
                            <option value="">Select Synthesis Model</option>
                            <option value="Web ChatBot Chairman">Web ChatBot Chairman</option>
                            {llmNames.map(name => <option key={name} value={name}>{name}</option>)}
                        </select>
                        {lastThinkingUsed !== null && (
                            <span className={`thinking-indicator ${lastThinkingUsed ? 'thinking-on' : 'thinking-off'}`} title={lastThinkingUsed ? 'Thinking was enabled' : 'Thinking was not enabled'}>
                                {lastThinkingUsed ? '🧠 Thinking' : '💭 No Thinking'}
                            </span>
                        )}
                    </div>
                    <button
                        onClick={() => handleRunStage3Automation(stage3Prompt, providerInfo.key)}
                        className={`automation-btn stage3-auto-btn ${providerInfo.key}-btn`}
                        disabled={isAutomating || !stage3Prompt || stage3Response.model === 'Web ChatBot Chairman'}
                        style={providerInfo.color ? { backgroundColor: providerInfo.color } : {}}
                    >
                        Run via {providerInfo.label}
                    </button>
                </div>
                {preselectionReason && (
                    <div className="preselection-explanation" style={{ fontSize: '12px', color: 'var(--text-muted)', fontStyle: 'italic' }}>
                        {preselectionReason}
                    </div>
                )}

                <div className="input-tabs-container stage3-tabs-container">
                    <div className="input-tabs">
                        <button
                            type="button"
                            className={`input-tab ${!showStep3Preview ? 'active' : ''}`}
                            onClick={() => setShowStep3Preview(false)}
                        >
                            Write
                        </button>
                        <button
                            type="button"
                            className={`input-tab ${showStep3Preview ? 'active' : ''}`}
                            onClick={() => setShowStep3Preview(true)}
                        >
                            Preview
                        </button>
                    </div>
                    <div className="input-content-wrapper" key={showStep3Preview ? 'preview' : 'write'}>
                        {showStep3Preview ? (
                            <div className="input-preview-content markdown-content">
                                {stage3Response.response ? (
                                    <ReactMarkdown
                                        remarkPlugins={[remarkMath, remarkGfm]}
                                        rehypePlugins={[rehypeKatex]}
                                    >
                                        {stage3Response.response}
                                    </ReactMarkdown>
                                ) : (
                                    <span style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>Nothing to preview</span>
                                )}
                            </div>
                        ) : (
                            <textarea value={stage3Response.response || ''} onChange={(e) => setStage3Response({ ...stage3Response, response: e.target.value })} placeholder="Final answer..." />
                        )}
                    </div>
                </div>
            </div>
            <div className="wizard-actions">
                <div className="left-actions">
                    <button onClick={() => setStep(2)} className="secondary-btn">Back</button>
                    <button onClick={() => { if (window.confirm('Reset?')) { localStorage.removeItem(draftKey); window.location.reload(); } }} className="secondary-btn discard-btn">Discard</button>
                </div>
                <button onClick={handleComplete} className="primary-btn complete-btn" disabled={!stage3Response.response}>Finish & Save</button>
            </div>
        </div>

    );

    if (isLoading) return <div className="web-chatbot-wizard-loading">Processing...</div>;

    return (
        <div className="web-chatbot-wizard">
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
