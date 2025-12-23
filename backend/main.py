"""FastAPI backend for LLM Council."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any
import uuid
import json
import asyncio

from . import storage

from .council import (
    run_full_council, generate_conversation_title, stage1_collect_responses,
    stage2_collect_rankings, stage3_synthesize_final, calculate_aggregate_rankings,
    build_ranking_prompt, build_chairman_prompt, parse_ranking_from_text,
    run_ai_studio_automation
)

app = FastAPI(title="LLM Council API")

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


class ManualStage2Request(BaseModel):
    user_query: str
    stage1_results: List[Dict[str, Any]]
    previous_messages: List[Dict[str, Any]] = []


class ManualRankingProcessRequest(BaseModel):
    stage2_results: List[Dict[str, Any]]
    label_to_model: Dict[str, str]


class ManualStage3Request(BaseModel):
    user_query: str
    stage1_results: List[Dict[str, Any]]
    stage2_results: List[Dict[str, Any]]
    previous_messages: List[Dict[str, Any]] = []


class SaveManualMessageRequest(BaseModel):
    stage1: List[Dict[str, Any]]
    stage2: List[Dict[str, Any]]
    stage3: Dict[str, Any]
    metadata: Dict[str, Any]
    user_query: str
    title: str = None  # Optional manual title


class AutomationRequest(BaseModel):
    prompt: str
    model: str = "Gemini 3 Flash"





@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "LLM Council API"}


@app.get("/api/conversations", response_model=List[ConversationMetadata])
async def list_conversations():
    """List all conversations (metadata only)."""
    return storage.list_conversations()


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
        stage3_result
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
                stage3_result
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


# --- Manual Mode Helper Endpoints ---

@app.post("/api/manual/run-automation")
async def manual_run_automation(request: AutomationRequest):
    """Run AI Studio automation for a prompt."""
    try:
        response = await run_ai_studio_automation(request.prompt, request.model)
        return {"response": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/manual/stage2-prompt")
async def manual_stage2_prompt(request: ManualStage2Request):
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


@app.post("/api/manual/process-rankings")
async def manual_process_rankings(request: ManualRankingProcessRequest):
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
        
    aggregate_rankings = calculate_aggregate_rankings(processed_results, request.label_to_model)
    
    return {
        "stage2_results": processed_results,
        "aggregate_rankings": aggregate_rankings
    }


@app.post("/api/manual/stage3-prompt")
async def manual_stage3_prompt(request: ManualStage3Request):
    """Generate the Stage 3 prompt."""
    prompt = build_chairman_prompt(
        request.user_query, 
        request.stage1_results, 
        request.stage2_results,
        context_messages=request.previous_messages
    )
    return {"prompt": prompt}


@app.post("/api/conversations/{conversation_id}/message/manual")
async def save_manual_message(conversation_id: str, request: SaveManualMessageRequest):
    """Save a fully constructed manual message."""
    # Check if conversation exists
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    is_first_message = len(conversation["messages"]) == 0

    # Add user message
    storage.add_user_message(conversation_id, request.user_query)

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

    # Add assistant message
    storage.add_assistant_message(
        conversation_id,
        request.stage1,
        request.stage2,
        request.stage3
    )

    return {"status": "success"}


async def _generate_and_save_title(conversation_id: str, query: str):
    """Helper to generate title in background."""
    try:
        title = await generate_conversation_title(query)
        storage.update_conversation_title(conversation_id, title)
    except Exception:
        pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
