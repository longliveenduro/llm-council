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
            // Try to extract numbered list format (e.g., "1. Response A" or "1. Response A1")
            const numberedMatches = rankingSection.match(/\d+\.\s*Response [A-Z]\d*/g);
            if (numberedMatches) {
                return numberedMatches.map(m => m.match(/Response [A-Z]\d*/)[0]);
            }

            // Fallback: Extract all "Response X" patterns in order
            const matches = rankingSection.match(/Response [A-Z]\d*/g);
            return matches || [];
        }
    }

    // Fallback: try to find any "Response X" patterns in order in the whole text
    const matches = rankingText.match(/Response [A-Z]\d*/g);
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
            rankIndex: currentRankIndex,
            count: item.count
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
    const [selectedImages, setSelectedImages] = useState(savedDraft.selectedImages || (savedDraft.selectedImage ? [savedDraft.selectedImage] : []));
    const [roundsPerModel, setRoundsPerModel] = useState(savedDraft.roundsPerModel || 1); // Number of rounds (responses) per model
    const [showChairmanPrompt, setShowChairmanPrompt] = useState(false); // Step 3 Prompt Toggle

    // Input State for current item
    const [currentModel, setCurrentModel] = useState(savedDraft.currentModel || llmNames[0] || '');
    const [currentText, setCurrentText] = useState(savedDraft.currentText || '');
    const [showPreview, setShowPreview] = useState(false); // Step 1 Preview Toggle - default to Write mode
    const [showStep3Preview, setShowStep3Preview] = useState(false); // Step 3 Preview Toggle - default to Write mode
    const [lastThinkingUsed, setLastThinkingUsed] = useState(null); // null, true, or false - tracks if last automation used thinking
    const [lastAutomationProvider, setLastAutomationProvider] = useState(null); // tracks which provider was used for last automation
    const [isCurrentResponseError, setIsCurrentResponseError] = useState(false); // tracks if the current automation result is an error
    const [currentErrorType, setCurrentErrorType] = useState(null); // tracks the specific machine-readable error type

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
            aggregateRankings, aiStudioModel, currentModel, currentText, preselectionReason,
            selectedImages, roundsPerModel
        };
        localStorage.setItem(draftKey, JSON.stringify(draft));
    }, [draftKey, step, userQuery, stage1Responses, stage2Prompt, labelToModel, stage2Responses, stage3Prompt, stage3Response, manualTitle, aggregateRankings, aiStudioModel, currentModel, currentText, selectedImages, roundsPerModel]);

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
            const titleData = await api.runAutomation(titlePrompt, 'Gemini Flash Latest', 'ai_studio');
            if (titleData.error || !titleData.response) {
                console.error('Failed to generate title:', titleData.error_msgs);
                return;
            }
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

            // Check for existing response with EXACT model name (thinking vs non-thinking are different)
            const existingIdx = stage1Responses.findIndex(r => r.model === modelNameToUse);
            let newResponses;

            if (existingIdx !== -1) {
                if (!window.confirm(`A response from "${modelNameToUse}" has already been added. Do you want to overwrite it?`)) {
                    return;
                }
                newResponses = [...stage1Responses];
                newResponses[existingIdx] = { model: modelNameToUse, response: currentText };
            } else {
                newResponses = [...stage1Responses, { model: modelNameToUse, response: currentText }];
            }

            setStage1Responses(newResponses);

            // Immediately update mapping with grouped labels (A1, A2, B1, B2...)
            // Group responses by model name to assign letter prefixes
            const modelOrder = []; // Track order of unique models
            const modelCounts = {}; // Track count per model for round numbers

            const newMapping = {};
            newResponses.forEach((r) => {
                const modelKey = r.model;
                if (!modelCounts[modelKey]) {
                    modelCounts[modelKey] = 0;
                    modelOrder.push(modelKey);
                }
                modelCounts[modelKey]++;
                const letterIdx = modelOrder.indexOf(modelKey);
                const letter = String.fromCharCode(65 + letterIdx);
                const roundNum = modelCounts[modelKey];
                newMapping[`Response ${letter}${roundNum}`] = r.model;
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

        // In Step 1, run multiple rounds based on roundsPerModel
        const numRounds = step === 1 ? roundsPerModel : 1;

        try {
            // Lookup best model for the requested provider
            let modelToUse = null;
            if (automationModels[provider] && automationModels[provider].length > 0) {
                modelToUse = automationModels[provider][0].name;
            }

            if (!modelToUse) {
                // Fallback if not loaded yet
                if (provider === 'ai_studio') modelToUse = 'Gemini 3 Pro Preview';
                if (provider === 'chatgpt') modelToUse = 'ChatGPT 5.2';
                if (provider === 'claude') modelToUse = 'Claude 4.5 Sonnet';
            }

            const norm = (name) => name ? name.toLowerCase().replace(/\s+/g, '') : '';

            if (provider === 'chatgpt') {
                // Ensure thinking is requested
                if (!modelToUse.toLowerCase().includes('thinking') && !modelToUse.toLowerCase().includes('o1')) {
                    modelToUse += ' Thinking';
                }
            } else if (provider === 'claude') {
                // Ensure thinking is requested
                if (!modelToUse.toLowerCase().includes('thinking')) {
                    modelToUse += ' [Ext. Thinking]';
                }
            }

            // Check for overwrite if rerunning multi-round
            if (step === 1 && numRounds > 1) {
                const existingForModel = stage1Responses.filter(r => norm(r.model) === norm(modelToUse));
                if (existingForModel.length > 0) {
                    if (!window.confirm(`Responses from "${modelToUse}" have already been added. Do you want to overwrite all ${existingForModel.length} existing responses for this model with ${numRounds} new ones?`)) {
                        setIsAutomating(false);
                        return;
                    }
                    // Clear existing responses for this model
                    setStage1Responses(prev => prev.filter(r => norm(r.model) !== norm(modelToUse)));
                }
            }

            // Run automation for each round
            for (let round = 1; round <= numRounds; round++) {
                const data = await api.runAutomation(prompt, modelToUse, provider, null, selectedImages);

                // Track error state
                setIsCurrentResponseError(data.error);
                setCurrentErrorType(data.error_type);

                const responseText = data.response || data.error_msgs;

                // Logic to set lastThinkingUsed: If no error and modelName implies thinking, we know it worked.
                // We use modelToUse here because data.thinking_used is removed.
                let thinkingUsedEffective = false;
                if (!data.error) {
                    thinkingUsedEffective = modelToUse.toLowerCase().includes('thinking') || modelToUse.toLowerCase().includes('o1');
                }

                if (step === 1 && numRounds > 1) {
                    // Auto-add response for multi-round mode - ONLY if no error
                    if (data.error) {
                        setCurrentText(responseText);
                        setLastThinkingUsed(false);
                        alert(`Automation round ${round} failed: ${data.error_msgs}`);
                        break; // Stop multi-round on error
                    }

                    // Determine model name with thinking suffix
                    let modelNameToUse = modelToUse;
                    // For Claude/ChatGPT, clean and re-add appropriate suffix based on actual thinking used
                    if (provider === 'claude' || provider === 'chatgpt') {
                        // Get base model name from llmNames
                        const baseModel = (llmNames || []).find(n => norm(n).includes(provider === 'claude' ? 'claude' : 'chatgpt'));
                        if (baseModel) {
                            modelNameToUse = baseModel;
                        }
                        // Add thinking suffix if thinking was used
                        if (thinkingUsedEffective === true) {
                            const hasThinkingSuffix = modelNameToUse.toLowerCase().includes('thinking') ||
                                modelNameToUse.toLowerCase().includes('[ext.');
                            if (!hasThinkingSuffix) {
                                if (provider === 'claude') {
                                    modelNameToUse += ' [Ext. Thinking]';
                                } else if (provider === 'chatgpt') {
                                    modelNameToUse += ' Thinking';
                                }
                            }
                        }
                    }

                    // Add response directly to stage1Responses (no overwrite warning for multi-round)
                    setStage1Responses(prev => {
                        const newResponses = [...prev, { model: modelNameToUse, response: responseText }];

                        // Update mapping with grouped labels
                        const modelOrder = [];
                        const modelCounts = {};
                        const newMapping = {};
                        newResponses.forEach((r) => {
                            const modelKey = r.model;
                            if (!modelCounts[modelKey]) {
                                modelCounts[modelKey] = 0;
                                modelOrder.push(modelKey);
                            }
                            modelCounts[modelKey]++;
                            const letterIdx = modelOrder.indexOf(modelKey);
                            const letter = String.fromCharCode(65 + letterIdx);
                            const roundNum = modelCounts[modelKey];
                            newMapping[`Response ${letter}${roundNum}`] = r.model;
                        });
                        setLabelToModel(newMapping);

                        return newResponses;
                    });
                } else if (step === 1 && numRounds === 1) {
                    // Single round - store in currentText for manual add
                    setCurrentText(responseText);
                    setLastThinkingUsed(thinkingUsedEffective);
                    setLastAutomationProvider(provider);
                    // Update currentModel to the base model
                    if (provider === 'claude' || provider === 'chatgpt') {
                        const baseModel = (llmNames || []).find(n => norm(n).includes(provider === 'claude' ? 'claude' : 'chatgpt'));
                        if (baseModel) {
                            setCurrentModel(baseModel);
                        }
                    }
                } else {
                    // Stage 2 - single run, set text
                    setCurrentText(responseText);
                    setLastThinkingUsed(thinkingUsedEffective);
                    setLastAutomationProvider(provider);
                }
            }

            // After multi-round, advance to next model in council
            if (step === 1 && numRounds > 1 && !isCurrentResponseError) {
                const nextIdx = llmNames.indexOf(currentModel) + 1;
                setCurrentModel(nextIdx > 0 && nextIdx < llmNames.length ? llmNames[nextIdx] : '');
                setCurrentText('');
            }
        } catch (error) {
            setCurrentText(`Exception in frontend: ${error.message}`);
            setIsCurrentResponseError(true);
            setCurrentErrorType('generic_error');
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
            // Use the best available model for this provider
            let modelToUse = null;
            if (automationModels[provider] && automationModels[provider].length > 0) {
                modelToUse = automationModels[provider][0].name;
            }
            const norm = (name) => name ? name.toLowerCase().replace(/\s+/g, '') : '';

            // For Stage 3, we prefer the user's explicit selection if it matches the provider, 
            // but relying on selectedAutomationModel is safer given the new "best model" paradigm.
            // If the user selected a model in the Stage 3 dropdown, we might want to respect that?
            // BUT, the request said "Use the highest available version number". 
            // So sticking to selectedAutomationModel (which is the Sort-Order best) is correct.

            if (provider === 'chatgpt') {
                // For ChatGPT, always ensure thinking suffix logic applies if needed
                if (!modelToUse) modelToUse = 'ChatGPT 5.2';
                if (!modelToUse.toLowerCase().includes('thinking') && !modelToUse.toLowerCase().includes('o1')) {
                    modelToUse += ' Thinking';
                }
            } else if (provider === 'claude') {
                if (!modelToUse) modelToUse = 'Claude 4.5 Sonnet';
                if (!modelToUse.toLowerCase().includes('thinking')) {
                    modelToUse += ' [Ext. Thinking]';
                }
            }


            const data = await api.runAutomation(prompt, modelToUse, provider, null, selectedImages); // Pass images if present (likely only for Step 1, but keeping consistent)
            console.log(`Automation successful for ${provider}, setting response`);

            // Track error state
            setIsCurrentResponseError(data.error);
            setCurrentErrorType(data.error_type);

            // Logic to set lastThinkingUsed: If no error and modelName implies thinking, we know it worked.
            let thinkingUsedEffective = false;
            if (!data.error) {
                thinkingUsedEffective = modelToUse.toLowerCase().includes('thinking') || modelToUse.toLowerCase().includes('o1');
            }

            setLastThinkingUsed(thinkingUsedEffective);
            setLastAutomationProvider(provider);

            // Clean display model and set response in one update
            let finalDisplayModel = stage3Response.model;
            if (!data.error && (provider === 'claude' || provider === 'chatgpt')) {
                const baseModel = (llmNames || []).find(n => norm(n).includes(provider === 'claude' ? 'claude' : 'chatgpt'));
                if (baseModel) {
                    finalDisplayModel = baseModel;
                }
            }

            setStage3Response(prev => ({
                ...prev,
                response: data.response || data.error_msgs,
                model: finalDisplayModel
            }));
        } catch (error) {
            setStage3Response(prev => ({
                ...prev,
                response: `Exception in frontend: ${error.message}`
            }));
            setIsCurrentResponseError(true);
            setCurrentErrorType('generic_error');
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
                metadata: { label_to_model: labelToModel, aggregate_rankings: aggregateRankings, rounds_per_model: roundsPerModel },
                title: manualTitle,
                images: selectedImages,
                image: selectedImages.length > 0 ? selectedImages[0] : null // Legacy support
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
                <label>Automation Targets (Best Available):</label>
                <div className="automation-targets-list">
                    {Object.entries(automationModels).length === 0 && <span>Loading models...</span>}
                    {Object.entries(automationModels).map(([provider, models]) => {
                        if (!models || models.length === 0) return null;
                        const bestModel = models[0].name;
                        const providerLabel = provider === 'ai_studio' ? 'Gemini' : (provider === 'chatgpt' ? 'ChatGPT' : 'Claude');
                        return (
                            <div key={provider} className="best-model-badge-row">
                                <span className="provider-name">{providerLabel}:</span>
                                <span className="c-model-name">{bestModel}</span>
                                <button
                                    className="small-add-btn"
                                    onClick={() => {
                                        if (onAddLlmName) {
                                            onAddLlmName(bestModel);
                                            setCurrentModel(bestModel);
                                        }
                                    }}
                                    disabled={llmNames.includes(bestModel)}
                                    title="Add to Council"
                                >
                                    {llmNames.includes(bestModel) ? '✓' : '+'}
                                </button>
                            </div>
                        );
                    })}
                </div>
            </div>
            <div className="form-group rounds-per-model-section">
                <label htmlFor="rounds-per-model">Rounds per Model:</label>
                <div className="rounds-input-wrapper">
                    <input
                        type="number"
                        id="rounds-per-model"
                        value={roundsPerModel}
                        onChange={(e) => setRoundsPerModel(Math.max(1, parseInt(e.target.value) || 1))}
                        min="1"
                        max="10"
                        className="rounds-input"
                        aria-label="Rounds per Model"
                    />
                    <span className="rounds-hint">Each model will provide this many independent responses</span>
                </div>
            </div>
            <div className="form-group">
                <label htmlFor="user-query">Your Question:</label>
                <textarea id="user-query" value={userQuery} onChange={(e) => setUserQuery(e.target.value)} rows={4} />
            </div>

            {/* Image Upload Section */}
            <div className="form-group image-upload-section">
                <label>Attach Images (Optional):</label>
                <div className="image-input-wrapper">
                    <input
                        type="file"
                        accept="image/*"
                        multiple
                        onChange={(e) => {
                            const files = Array.from(e.target.files);
                            if (files.length > 0) {
                                // Upload multiple files immediately
                                Promise.all(files.map(file => {
                                    return api.uploadImage(file)
                                        .then(data => data.url)
                                        .catch(err => {
                                            console.error("Error uploading file", err);
                                            alert(`Failed to upload ${file.name}`);
                                            return null;
                                        });
                                })).then(results => {
                                    // Filter out failures
                                    const validUrls = results.filter(url => url !== null);
                                    setSelectedImages(prev => [...prev, ...validUrls]);
                                    // Reset input
                                    e.target.value = null;
                                });
                            }
                        }}
                        style={{ display: 'none' }}
                        id="image-upload-input"
                    />
                    <label htmlFor="image-upload-input" className="image-upload-btn secondary-btn">
                        {selectedImages.length > 0 ? 'Add More Images' : '📷 Add Images'}
                    </label>
                    {selectedImages.map((img, idx) => (
                        <div key={idx} className="image-preview-container">
                            <img src={api.getImageUrl(img)} alt={`Preview ${idx}`} className="image-preview-thumb" />
                            <button className="remove-image-btn" onClick={() => setSelectedImages(prev => prev.filter((_, i) => i !== idx))} title="Remove Image">×</button>
                        </div>
                    ))}
                </div>
            </div>

            <div className={stage1Responses.length > 0 ? "prompt-col-layout" : ""}>
                <div className="responses-list" style={stage1Responses.length > 0 ? { flex: 2, marginBottom: 0 } : {}}>
                    {stage1Responses.length === 0 && <div className="no-responses-hint" style={{ color: 'var(--text-muted)', fontSize: '13px', fontStyle: 'italic', textAlign: 'center', padding: '12px' }}>No responses added yet.</div>}
                    {(() => {
                        const modelCounts = {};
                        const modelOrder = [];
                        return stage1Responses.map((r, i) => {
                            const modelKey = r.model;
                            if (!modelCounts[modelKey]) {
                                modelCounts[modelKey] = 0;
                                modelOrder.push(modelKey);
                            }
                            modelCounts[modelKey]++;
                            const letterIdx = modelOrder.indexOf(modelKey);
                            const letter = String.fromCharCode(65 + letterIdx);
                            const roundNum = modelCounts[modelKey];
                            const label = `${letter}${roundNum}`;

                            return (
                                <div key={i} className="response-item clickable-response-item" onClick={() => setViewingResponse(r)} title="Click to view full response">
                                    <div className="response-header">
                                        <span className="response-model-label">Model {label}:</span> <ModelBadge model={r.model} />:
                                    </div>
                                    <div className="response-preview">
                                        {r.response.substring(0, 50)}...
                                    </div>
                                </div>
                            );
                        });
                    })()}
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
                            <textarea value={currentText} onChange={(e) => { setCurrentText(e.target.value); setIsCurrentResponseError(false); }} rows={8} placeholder="Model Response" />
                        )}
                        {isCurrentResponseError && (
                            <div className={`error-indicator-box ${currentErrorType}`}>
                                <span className="error-icon">⚠️</span>
                                <span className="error-message">Error in automation. Check the message above.</span>
                            </div>
                        )}
                    </div>
                </div>
                <div className="add-response-actions">
                    <button onClick={addStage1Response} disabled={!currentModel || !currentText || isCurrentResponseError}>Add Response</button>
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
            {aggregateRankings && aggregateRankings.length > 0 && (
                <div className="aggregate-rankings-wizard">
                    <h4>Aggregate Rankings (Street Cred)</h4>
                    <p className="stage-description">
                        Combined results across all peer evaluations (lower score is better):
                    </p>
                    <div className="aggregate-list">
                        {aggregateRankings.map((agg, index) => (
                            <div key={index} className="aggregate-item">
                                <span className="rank-position">#{index + 1}</span>
                                <span className="rank-model-container">
                                    <ModelBadge model={agg.model} />
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
                <textarea value={currentText} onChange={(e) => { setCurrentText(e.target.value); setIsCurrentResponseError(false); }} rows={8} placeholder="Paste Ranking" />
                {isCurrentResponseError && (
                    <div className={`error-indicator-box ${currentErrorType}`}>
                        <span className="error-icon">⚠️</span>
                        <span className="error-message">Error in automation. Check the ranking above.</span>
                    </div>
                )}
                <div className="add-response-actions">
                    <button onClick={addStage2Response} disabled={!currentModel || !currentText || isCurrentResponseError}>Add Ranking</button>
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
            <div className="step-header">
                <h3>Step 3: Synthesis</h3>
            </div>

            <div className="step3-scroll-area">
                <div className="step3-top-layout">
                    <div className={`prompt-container-card ${showChairmanPrompt ? 'prompt-expanded' : 'prompt-collapsed'}`}>
                        <div className="prompt-card-header" onClick={() => setShowChairmanPrompt(!showChairmanPrompt)}>
                            <span className="prompt-title">
                                <span className="toggle-icon">{showChairmanPrompt ? '▼' : '▶'}</span>
                                Chairman Prompt
                            </span>
                            <button
                                onClick={(e) => { e.stopPropagation(); copyToClipboard(stage3Prompt); }}
                                className="copy-prompt-btn-mini"
                                title="Copy Prompt"
                            >
                                Copy
                            </button>
                        </div>
                        {showChairmanPrompt && (
                            <div className="prompt-preview-content">
                                {stage3Prompt}
                            </div>
                        )}
                    </div>
                    <div className="mapping-container-card">
                        <MappingBox labelToModel={labelToModel} scores={currentScores} showScoreExplanation={true} />
                    </div>
                </div>

                <div className="stage3-main-content">
                    <div className="synthesis-card">
                        <div className="card-header">
                            <label>Final Synthesis</label>
                        </div>
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
                            <div className="preselection-explanation">
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
                                    <textarea
                                        value={stage3Response.response || ''}
                                        onChange={(e) => { setStage3Response({ ...stage3Response, response: e.target.value }); setIsCurrentResponseError(false); }}
                                        placeholder="Enter the final consensus or summary here..."
                                        rows={12}
                                    />
                                )}
                                {isCurrentResponseError && (
                                    <div className={`error-indicator-box ${currentErrorType}`}>
                                        <span className="error-icon">⚠️</span>
                                        <span className="error-message">Error in automation. Check the synthesis above.</span>
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>

                    {aggregateRankings && aggregateRankings.length > 0 && (
                        <div className="aggregate-rankings-card">
                            <div className="card-header">
                                <h4>Aggregate Rankings (Street Cred)</h4>
                                <span className="header-hint">Combined results across all peer evaluations (lower score is better)</span>
                            </div>
                            <div className="aggregate-list">
                                {aggregateRankings.map((agg, index) => (
                                    <div key={index} className="aggregate-item-modern">
                                        <div className="rank-badge">#{index + 1}</div>
                                        <div className="rank-model-info">
                                            <ModelBadge model={agg.model} />
                                        </div>
                                        <div className="rank-stats">
                                            <span className="rank-avg-value">Avg: {agg.average_rank.toFixed(2)}</span>
                                            <span className="rank-votes-count">{agg.rankings_count} votes</span>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                </div>
            </div>

            <div className="wizard-actions">
                <div className="left-actions">
                    <button onClick={() => setStep(2)} className="secondary-btn">Back</button>
                    <button onClick={() => { if (window.confirm('Reset?')) { localStorage.removeItem(draftKey); window.location.reload(); } }} className="secondary-btn discard-btn">Discard</button>
                </div>
                <button onClick={handleComplete} className="primary-btn complete-btn" disabled={!stage3Response.response || isCurrentResponseError}>Finish & Save</button>
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
