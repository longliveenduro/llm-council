import asyncio
import os
import sys
import base64
import uuid
from typing import List, Dict, Any, Optional
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import storage

from .council import (
    run_full_council, generate_conversation_title, stage1_collect_responses,
    stage2_collect_rankings, stage3_synthesize_final, calculate_aggregate_rankings,
    build_ranking_prompt, build_chairman_prompt, parse_ranking_from_text,
    run_ai_studio_automation, run_chatgpt_automation, run_claude_automation,
    check_automation_session, clear_automation_session, run_interactive_login,
    get_ai_studio_models, get_claude_models
)

from .storage import get_cached_models, save_cached_models
from .scores import get_scores, update_scores
from .utils import clean_model_name

app = FastAPI(title="LLM Council API")

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount images directory for serving
IMAGES_DIR = Path("backend/data/images")
IMAGES_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/api/images", StaticFiles(directory=str(IMAGES_DIR)), name="images")

# Add backend directory to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))


class CreateConversationRequest(BaseModel):
    """Request to create a new conversation."""
    pass


class SendMessageRequest(BaseModel):
    """Request to send a message in a conversation."""
    content: str


class ConversationMetadata(BaseModel):
    """Conversation metadata for list view."""
    id: str
    created_at: str
    title: str
    message_count: int


class Conversation(BaseModel):
    """Full conversation with all messages."""
    id: str
    created_at: str
    title: str
    messages: List[Dict[str, Any]]


class WebChatBotStage2Request(BaseModel):
    user_query: str
    stage1_results: List[Dict[str, Any]]
    previous_messages: List[Dict[str, Any]] = []


class WebChatBotRankingProcessRequest(BaseModel):
    stage2_results: List[Dict[str, Any]]
    label_to_model: Dict[str, str]


class WebChatBotStage3Request(BaseModel):
    user_query: str
    stage1_results: List[Dict[str, Any]]
    stage2_results: List[Dict[str, Any]]
    previous_messages: List[Dict[str, Any]] = []


class SaveWebChatBotMessageRequest(BaseModel):
    stage1: List[Dict[str, Any]]
    stage2: List[Dict[str, Any]]
    stage3: Dict[str, Any]
    metadata: Dict[str, Any]
    user_query: str
    title: str = None  # Optional manual title
    image: Optional[str] = None # Legacy: Base64 encoded image string
    images: Optional[List[str]] = None # Base64 encoded image strings

class AutomationRequest(BaseModel):
    prompt: str
    model: str = "Gemini 2.5 Flash"
    provider: str = "ai_studio"  # "ai_studio" or "chatgpt"
    image: Optional[str] = None # Legacy: Base64 encoded image string
    images: Optional[List[str]] = None # Base64 encoded image strings


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "LLM Council API"}


@app.get("/api/conversations", response_model=List[ConversationMetadata])
async def list_conversations():
    """List all conversations (metadata only)."""
    return storage.list_conversations()


@app.get("/api/scores")
async def get_model_scores():
    """Get persistent model highscores."""
    return get_scores()



@app.post("/api/conversations", response_model=Conversation)
async def create_conversation(request: CreateConversationRequest):
    """Create a new conversation."""
    conversation_id = str(uuid.uuid4())
    conversation = storage.create_conversation(conversation_id)
    return conversation


@app.delete("/api/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """Delete a conversation."""
    success = storage.delete_conversation(conversation_id)
    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"status": "success", "id": conversation_id}


class UpdateTitleRequest(BaseModel):
    title: str


@app.patch("/api/conversations/{conversation_id}/title")
async def update_conversation_title(conversation_id: str, request: UpdateTitleRequest):
    """Update conversation title."""
    try:
        storage.update_conversation_title(conversation_id, request.title)
        return {"status": "success", "id": conversation_id, "title": request.title}
    except ValueError:
        raise HTTPException(status_code=404, detail="Conversation not found")


@app.get("/api/conversations/{conversation_id}", response_model=Conversation)
async def get_conversation(conversation_id: str):
    """Get a specific conversation with all its messages."""
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@app.post("/api/conversations/{conversation_id}/message")
async def send_message(conversation_id: str, request: SendMessageRequest):
    """
    Send a message and run the 3-stage council process.
    Returns the complete response with all stages.
    """
    # Check if conversation exists
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check if this is the first message
    is_first_message = len(conversation["messages"]) == 0

    # Add user message
    storage.add_user_message(conversation_id, request.content)

    # If this is the first message, generate a title
    if is_first_message:
        title = await generate_conversation_title(request.content)
        storage.update_conversation_title(conversation_id, title)

    # Run the 3-stage council process
    stage1_results, stage2_results, stage3_result, metadata = await run_full_council(
        request.content
    )

    # Add assistant message with all stages
    storage.add_assistant_message(
        conversation_id,
        stage1_results,
        stage2_results,
        stage3_result,
        metadata
    )

    # Return the complete response with metadata
    return {
        "stage1": stage1_results,
        "stage2": stage2_results,
        "stage3": stage3_result,
        "metadata": metadata
    }


@app.post("/api/conversations/{conversation_id}/message/stream")
async def send_message_stream(conversation_id: str, request: SendMessageRequest):
    """
    Send a message and stream the 3-stage council process.
    Returns Server-Sent Events as each stage completes.
    """
    # Check if conversation exists
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check if this is the first message
    is_first_message = len(conversation["messages"]) == 0

    async def event_generator():
        try:
            # Add user message
            storage.add_user_message(conversation_id, request.content)

            # Start title generation in parallel (don't await yet)
            title_task = None
            if is_first_message:
                title_task = asyncio.create_task(generate_conversation_title(request.content))

            # Stage 1: Collect responses
            yield f"data: {json.dumps({'type': 'stage1_start'})}\n\n"
            stage1_results = await stage1_collect_responses(
                request.content,
                manual_responses=request.manual_responses
            )
            yield f"data: {json.dumps({'type': 'stage1_complete', 'data': stage1_results})}\n\n"

            # Stage 2: Collect rankings
            yield f"data: {json.dumps({'type': 'stage2_start'})}\n\n"
            stage2_results, label_to_model = await stage2_collect_rankings(request.content, stage1_results)
            aggregate_rankings = calculate_aggregate_rankings(stage2_results, label_to_model)
            yield f"data: {json.dumps({'type': 'stage2_complete', 'data': stage2_results, 'metadata': {'label_to_model': label_to_model, 'aggregate_rankings': aggregate_rankings}})}\n\n"

            # Stage 3: Synthesize final answer
            yield f"data: {json.dumps({'type': 'stage3_start'})}\n\n"
            stage3_result = await stage3_synthesize_final(request.content, stage1_results, stage2_results)
            yield f"data: {json.dumps({'type': 'stage3_complete', 'data': stage3_result})}\n\n"

            # Wait for title generation if it was started
            if title_task:
                title = await title_task
                storage.update_conversation_title(conversation_id, title)
                yield f"data: {json.dumps({'type': 'title_complete', 'data': {'title': title}})}\n\n"

            # Save complete assistant message
            storage.add_assistant_message(
                conversation_id,
                stage1_results,
                stage2_results,
                stage3_result,
                {"label_to_model": label_to_model, "aggregate_rankings": aggregate_rankings}
            )

            # Send completion event
            yield f"data: {json.dumps({'type': 'complete'})}\n\n"

        except Exception as e:
            # Send error event
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


# --- Web ChatBot Helper Endpoints ---

@app.post("/api/web-chatbot/run-automation")
async def web_chatbot_run_automation(request: AutomationRequest):
    """Run automation for a prompt using specified provider."""
    try:
        # Collect images from either field
        images = []
        if request.images:
            images.extend(request.images)
        if request.image and request.image not in images:
            images.append(request.image)
            
        if request.provider == "chatgpt":
            response, thinking_used = await run_chatgpt_automation(request.prompt, request.model, images=images)
        elif request.provider == "claude":
            response, thinking_used = await run_claude_automation(request.prompt, request.model, images=images)
        else:
            # Default to AI Studio - Gemini always has thinking enabled
            response = await run_ai_studio_automation(request.prompt, request.model, images=images)
            thinking_used = True  # Gemini thinking is always on by default
            
        return {"response": response, "thinking_used": thinking_used}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/web-chatbot/stage2-prompt")
async def web_chatbot_stage2_prompt(request: WebChatBotStage2Request):
    """Generate the Stage 2 prompt and label mapping."""
    # Create anonymized labels
    labels = [chr(65 + i) for i in range(len(request.stage1_results))]
    
    # Create mapping
    label_to_model = {
        f"Response {label}": result['model']
        for label, result in zip(labels, request.stage1_results)
    }
    
    prompt = build_ranking_prompt(
        request.user_query, 
        request.stage1_results, 
        labels,
        context_messages=request.previous_messages
    )
    
    return {
        "prompt": prompt,
        "label_to_model": label_to_model
    }


@app.post("/api/web-chatbot/process-rankings")
async def web_chatbot_process_rankings(request: WebChatBotRankingProcessRequest):
    """Parse manual rankings and calculate aggregate."""
    processed_results = []
    
    for result in request.stage2_results:
        full_text = result.get('ranking', '')
        parsed = parse_ranking_from_text(full_text)
        processed_results.append({
            "model": result['model'],
            "ranking": full_text,
            "parsed_ranking": parsed
        })
        
    # Parse manual rankings and calculate aggregate
    # Ensure label_to_model uses clean names
    clean_label_to_model = {label: clean_model_name(model) for label, model in request.label_to_model.items()}
    
    aggregate_rankings = calculate_aggregate_rankings(processed_results, clean_label_to_model)
    
    # Update persistent scores
    update_scores(processed_results, clean_label_to_model)
    
    return {
        "stage2_results": processed_results,
        "aggregate_rankings": aggregate_rankings
    }


@app.post("/api/web-chatbot/stage3-prompt")
async def web_chatbot_stage3_prompt(request: WebChatBotStage3Request):
    """Generate the Stage 3 prompt."""
    prompt = build_chairman_prompt(
        request.user_query, 
        request.stage1_results, 
        request.stage2_results,
        context_messages=request.previous_messages
    )
    return {"prompt": prompt}


@app.post("/api/conversations/{conversation_id}/message/web-chatbot")
async def save_web_chatbot_message(conversation_id: str, request: SaveWebChatBotMessageRequest):
    """Save a fully constructed Web ChatBot message."""
    # Check if conversation exists
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    is_first_message = len(conversation["messages"]) == 0

    # Add user message
    user_metadata = {}
    
    image_list = []
    if request.images:
        image_list.extend(request.images)
    if request.image and request.image not in image_list:
        image_list.append(request.image)
        
    if image_list:
        user_metadata["image_urls"] = []
        # Also keep first image in "image_url" for legacy support
        
        for idx, img_b64 in enumerate(image_list):
            try:
                # Expecting "data:image/jpeg;base64,..."
                if ',' in img_b64:
                    header, encoded = img_b64.split(',', 1)
                    ext = header.split(';')[0].split('/')[1]
                else:
                    encoded = img_b64
                    ext = "jpg" # Default
                
                image_data = base64.b64decode(encoded)
                filename = f"{uuid.uuid4()}.{ext}"
                filepath = IMAGES_DIR / filename
                
                with open(filepath, "wb") as f:
                    f.write(image_data)
                
                url = f"/api/images/{filename}"
                user_metadata["image_urls"].append(url)
                print(f"Saved image to {filepath}")
                
                if idx == 0:
                    user_metadata["image_url"] = url
                    
            except Exception as e:
                print(f"Error saving image: {e}")
                # Don't fail the whole request, just log error

    storage.add_user_message(conversation_id, request.user_query, metadata=user_metadata)

    # Handle Title
    if is_first_message:
        if request.title:
            # Use manual title if provided
            storage.update_conversation_title(conversation_id, request.title)
        else:
            # Generate title in background otherwise
            asyncio.create_task(
                _generate_and_save_title(conversation_id, request.user_query)
            )

    # Clean model names in results before saving
    cleaned_stage1 = []
    for s1 in request.stage1:
        cleaned_stage1.append({**s1, "model": clean_model_name(s1.get("model", ""))})
    
    cleaned_stage2 = []
    for s2 in request.stage2:
        cleaned_stage2.append({**s2, "model": clean_model_name(s2.get("model", ""))})
        
    cleaned_stage3 = {
        **request.stage3,
        "model": clean_model_name(request.stage3.get("model", ""))
    }

    # Add assistant message
    storage.add_assistant_message(
        conversation_id,
        cleaned_stage1,
        cleaned_stage2,
        cleaned_stage3,
        request.metadata
    )

    return {"status": "success"}


async def _generate_and_save_title(conversation_id: str, query: str):
    """Helper to generate title in background."""
    try:
        title = await generate_conversation_title(query)
        storage.update_conversation_title(conversation_id, title)
    except Exception:
        pass


# --- Automation Session Endpoints ---

@app.get("/api/automation/status")
async def get_automation_status():
    """Get login status for all automation providers."""
    return {
        "ai_studio": check_automation_session("ai_studio"),
        "chatgpt": check_automation_session("chatgpt"),
        "claude": check_automation_session("claude")
    }


@app.post("/api/automation/login/{provider}")
async def login_automation(provider: str):
    """Launch interactive login for a provider."""
    if provider not in ["ai_studio", "chatgpt", "claude"]:
        raise HTTPException(status_code=400, detail="Invalid provider. Use 'ai_studio', 'chatgpt', or 'claude'.")
    
    result = await run_interactive_login(provider)
    
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("message", "Login failed"))
    
    return result


@app.post("/api/automation/logout/{provider}")
async def logout_automation(provider: str):
    """Clear session data for a provider."""
    if provider not in ["ai_studio", "chatgpt", "claude"]:
        raise HTTPException(status_code=400, detail="Invalid provider. Use 'ai_studio', 'chatgpt', or 'claude'.")
    
    success = clear_automation_session(provider)
    return {"success": success, "provider": provider}


@app.get("/api/automation/models/{provider}")
async def get_automation_models(provider: str):
    """Get available models for a provider (cached)."""
    if provider == "ai_studio":
        # Try cache first
        cached = get_cached_models(provider)
        return cached if cached else []
    elif provider == "chatgpt":
        # For now, just return hardcoded ChatGPT models as we don't have a list script yet
        return [
            {"name": "ChatGPT 4o", "id": "gpt-4o"},
            {"name": "ChatGPT 4o mini", "id": "gpt-4o-mini"},
            {"name": "ChatGPT o1", "id": "o1"},
            {"name": "ChatGPT o1 thinking", "id": "o1-preview"},
        ]
    elif provider == "claude":
        return await get_claude_models()
    else:
        raise HTTPException(status_code=400, detail="Invalid provider")


@app.post("/api/automation/models/{provider}/sync")
async def sync_automation_models(provider: str):
    """Force a sync of models for a provider."""
    if provider == "ai_studio":
        models = await get_ai_studio_models()
        if models:
            save_cached_models(provider, models)
        return {"success": True, "models": models}
    elif provider == "chatgpt":
        # No sync implemented for ChatGPT yet, just return the hardcoded ones
        return {"success": True, "models": [
            {"name": "ChatGPT 4o", "id": "gpt-4o"},
            {"name": "ChatGPT 4o mini", "id": "gpt-4o-mini"},
            {"name": "ChatGPT o1", "id": "o1"},
            {"name": "ChatGPT o1 thinking", "id": "o1-preview"},
        ]}
    elif provider == "claude":
        # No sync implemented for Claude yet
        models = await get_claude_models()
        return {"success": True, "models": models}
    else:
        raise HTTPException(status_code=400, detail="Invalid provider")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
