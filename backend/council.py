"""3-stage LLM Council orchestration."""

from typing import List, Dict, Any, Tuple
from .openrouter import query_models_parallel, query_model
from .config import COUNCIL_MODELS, CHAIRMAN_MODEL
from .scores import update_scores
from .utils import clean_model_name
import subprocess
import os
import sys
import asyncio
from pathlib import Path
import shutil


# Browser data directories for automation sessions
AI_STUDIO_BROWSER_DATA = Path(__file__).parent.parent / "browser_automation" / ".ai_studio_browser_data"
CHATGPT_BROWSER_DATA = Path(__file__).parent.parent / "browser_automation" / ".chatgpt_browser_data"
CLAUDE_BROWSER_DATA = Path(__file__).parent.parent / "browser_automation" / ".claude_browser_data"

# Global locks to prevent concurrent browser sessions for the same provider
AI_STUDIO_LOCK = asyncio.Lock()
CHATGPT_LOCK = asyncio.Lock()
CLAUDE_LOCK = asyncio.Lock()

TEMP_IMAGES_DIR = Path(__file__).parent.parent / "browser_automation" / "temp_images"
TEMP_IMAGES_DIR.mkdir(parents=True, exist_ok=True)


def _save_temp_image(base64_data: str) -> str:
    """Save base64 image to a temporary file and return path."""
    import base64
    import uuid
    
    try:
        if ',' in base64_data:
            header, encoded = base64_data.split(',', 1)
            ext = header.split(';')[0].split('/')[1]
        else:
            encoded = base64_data
            ext = "jpg"
            
        filename = f"{uuid.uuid4()}.{ext}"
        filepath = TEMP_IMAGES_DIR / filename
        
        with open(filepath, "wb") as f:
            f.write(base64.b64decode(encoded))
            
        print(f"Saved temp image: {filepath}")
        return str(filepath)
    except Exception as e:
        print(f"Error saving temp image: {e}")
        return None


def get_browser_data_dir(provider: str) -> Path:
    """Get the browser data directory for a provider."""
    if provider == "chatgpt":
        return CHATGPT_BROWSER_DATA
    if provider == "claude":
        return CLAUDE_BROWSER_DATA
    return AI_STUDIO_BROWSER_DATA


def check_automation_session(provider: str) -> bool:
    """
    Check if a browser session exists for the given provider.
    
    A session is considered valid if the browser data directory exists
    and contains typical Chromium profile files.
    """
    data_dir = get_browser_data_dir(provider)
    
    if not data_dir.exists():
        return False
    
    # Check for typical Chromium profile indicators
    # These files/dirs are created when Chromium stores login state
    indicators = ["Default", "Local State", "Cookies"]
    
    for indicator in indicators:
        if (data_dir / indicator).exists():
            return True
    
    return False


def clear_automation_session(provider: str) -> bool:
    """
    Clear the browser session data for a provider.
    
    Returns True if session was cleared, False if no session existed.
    """
    data_dir = get_browser_data_dir(provider)
    
    if not data_dir.exists():
        return False
    
    try:
        shutil.rmtree(data_dir)
        return True
    except Exception as e:
        print(f"Error clearing session for {provider}: {e}")
        return False


async def run_interactive_login(provider: str) -> dict:
    """
    Launch a headful browser for the user to log in interactively.
    This uses the automation scripts with the --login flag.
    
    Returns a dict with status and message.
    """
    script_map = {
        "chatgpt": Path(__file__).parent.parent / "browser_automation" / "chatgpt_automation.py",
        "claude": Path(__file__).parent.parent / "browser_automation" / "claude_automation.py",
        "ai_studio": Path(__file__).parent.parent / "browser_automation" / "ai_studio_automation.py",
    }
    
    script_path = script_map.get(provider)
    if not script_path:
        return {"success": False, "message": f"Unknown provider: {provider}"}
        
    cmd = [sys.executable, str(script_path), "--login"]
    
    if provider == "ai_studio":
        lock = AI_STUDIO_LOCK 
    elif provider == "chatgpt":
        lock = CHATGPT_LOCK
    else:
        lock = CLAUDE_LOCK
        
    async with lock:
        try:
            print(f"Executing login script for {provider}...")
            
            # We want to see the output in real-time or capture it to determine success
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Wait for process to complete (it has its own timeout logic)
            # We enforce a slightly longer timeout here just in case
            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=320)
            except asyncio.TimeoutError:
                process.kill()
                return {"success": False, "message": "Login script timed out (backend wrapper)."}
                
            stdout_str = stdout.decode().strip()
            stderr_str = stderr.decode().strip()
            
            print(f"Login script finished. Return code: {process.returncode}")
            # print(f"Stdout: {stdout_str}") # Optional debug calling
            
            if process.returncode == 0 and "Successfully logged in" in stdout_str:
                msg = f"Successfully logged in to {provider}"
                if provider == "chatgpt":
                    if "Memory turned OFF" in stdout_str:
                        msg += " (Memory verified: OFF)"
                    elif "Memory is already OFF" in stdout_str:
                        msg += " (Memory verified: OFF)"
                    elif "Failed to turn off Memory" in stdout_str:
                        msg += " (WARNING: Failed to auto-disable Memory)"
                        
                return {"success": True, "message": msg}
            else:
                failure_reason = "Unknown error"
                if "Login timed out" in stdout_str:
                    failure_reason = "Login timed out via script logic."
                elif stderr_str:
                    failure_reason = f"Script error: {stderr_str}"
                    
                return {"success": False, "message": f"Login failed. {failure_reason}"}
                
        except Exception as e:
            return {"success": False, "message": f"Login execution failed: {str(e)}"}


async def stage1_collect_responses(
    user_query: str
) -> List[Dict[str, Any]]:
    """
    Stage 1: Collect individual responses from all council models.

    Args:
        user_query: The user's question
        manual_responses: Optional list of manual responses [{'model': '...', 'response': '...'}]

    Returns:
        List of dicts with 'model' and 'response' keys
    """
    messages = [{"role": "user", "content": user_query}]

    # Query all models in parallel
    responses = await query_models_parallel(COUNCIL_MODELS, messages)

    # Format results
    stage1_results = []
    for model, response in responses.items():
        if response is not None:  # Only include successful responses
            stage1_results.append({
                "model": clean_model_name(model),
                "response": response.get('content', '')
            })



    return stage1_results


async def stage2_collect_rankings(
    user_query: str,
    stage1_results: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    """
    Stage 2: Each model ranks the anonymized responses.

    Args:
        user_query: The original user query
        stage1_results: Results from Stage 1

    Returns:
        Tuple of (rankings list, label_to_model mapping)
    """
    # Create anonymized labels for responses (Response A, Response B, etc.)
    labels = [chr(65 + i) for i in range(len(stage1_results))]  # A, B, C, ...

    # Create mapping from label to model name
    label_to_model = {
        f"Response {label}": result['model']
        for label, result in zip(labels, stage1_results)
    }

    # Build the ranking prompt
    ranking_prompt = build_ranking_prompt(user_query, stage1_results, labels)

    messages = [{"role": "user", "content": ranking_prompt}]

    # Get rankings from all council models in parallel
    responses = await query_models_parallel(COUNCIL_MODELS, messages)

    # Format results
    stage2_results = []
    for model, response in responses.items():
        if response is not None:
            full_text = response.get('content', '')
            parsed = parse_ranking_from_text(full_text)
            stage2_results.append({
                "model": clean_model_name(model),
                "ranking": full_text,
                "parsed_ranking": parsed
            })

    return stage2_results, label_to_model



def _format_context(context_messages: List[Dict[str, Any]]) -> str:
    """Format previous conversation history for context."""
    if not context_messages:
        return ""
        
    text = "PREVIOUS CONTEXT:\n\n"
    turn_count = 1
    
    for msg in context_messages:
        if msg.get('role') == 'user':
            text += f"User Question {turn_count}: {msg.get('content', '')}\n"
        elif msg.get('role') == 'assistant':
            # Extract final response
            response = "(No response)"
            if 'stage3' in msg and isinstance(msg['stage3'], dict):
                response = msg['stage3'].get('response', '')
            
            text += f"LLM Answer {turn_count}: {response}\n\n"
            turn_count += 1
            
    text += "CURRENT TASK:\n"
    return text


def build_ranking_prompt(
    user_query: str, 
    stage1_results: List[Dict[str, Any]], 
    labels: List[str],
    context_messages: List[Dict[str, Any]] = None
) -> str:
    """
    Build the prompt for Stage 2 (Peer Rankings).

    Args:
        user_query: The original user query
        stage1_results: Results from Stage 1
        labels: List of anonymized labels (can be A, B, C or A1, A2, B1, B2...)
        context_messages: Optional list of previous messages

    Returns:
        The complete prompt string
    """
    responses_text = "\n\n".join([
        f"Response {label}:\n{result['response']}"
        for label, result in zip(labels, stage1_results)
    ])

    context_section = _format_context(context_messages)
    
    # Check if this is a multi-round scenario by looking at the labels
    # Multi-round labels have format like A1, A2, B1 (letter + number)
    is_multi_round = len(labels) > 0 and len(labels[0]) > 1 and labels[0][-1].isdigit()
    
    multi_round_note = ""
    if is_multi_round:
        # Build explanation of which responses are from the same model
        model_groups = {}
        for label, result in zip(labels, stage1_results):
            letter = label[0] if len(label) > 0 else label
            if letter not in model_groups:
                model_groups[letter] = []
            model_groups[letter].append(label)
        
        if any(len(group) > 1 for group in model_groups.values()):
            group_explanations = []
            for letter, group_labels in sorted(model_groups.items()):
                if len(group_labels) > 1:
                    group_explanations.append(f"Responses {', '.join(group_labels)} are from the same model (generated in separate, independent sessions)")
            multi_round_note = "\n\nNOTE ON RESPONSES:\n" + "\n".join(group_explanations) + "\n\nEach response should be evaluated on its own merits, regardless of which model produced it.\n"

    return f"""You are evaluating different responses to the following question:

{context_section}
Question: {user_query}

Here are the responses from different models (anonymized):

{responses_text}
{multi_round_note}
Your task:
1. First, evaluate each response individually. For each response, explain what it does well and what it does poorly.
2. Then, at the very end of your response, provide a final ranking.

IMPORTANT: Your final ranking MUST be formatted EXACTLY as follows:
- Start with the line "FINAL RANKING:" (all caps, with colon)
- Then list the responses from best to worst as a numbered list
- Each line should be: number, period, space, then ONLY the response label (e.g., "1. Response A1")
- Do not add any other text or explanations in the ranking section

Example of the correct format for your ENTIRE response:

Response A1 provides good detail on X but misses Y...
Response A2 is accurate but lacks depth on Z...
Response B1 offers the most comprehensive answer...

FINAL RANKING:
1. Response B1
2. Response A1
3. Response A2

Now provide your evaluation and ranking:"""


async def stage3_synthesize_final(
    user_query: str,
    stage1_results: List[Dict[str, Any]],
    stage2_results: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Stage 3: Chairman synthesizes final response.

    Args:
        user_query: The original user query
        stage1_results: Individual model responses from Stage 1
        stage2_results: Rankings from Stage 2

    Returns:
        Dict with 'model' and 'response' keys
    """
    # Note: stage3_synthesize_final is only used by the automated path, which doesn't
    # currently pass context (though it could). For manual manual_stage3_prompt,
    # we call build_chairman_prompt directly.
    # To keep automated path safe, we pass None for now or update it later if needed.
    
    chairman_prompt = build_chairman_prompt(user_query, stage1_results, stage2_results)

    messages = [{"role": "user", "content": chairman_prompt}]

    # Query the chairman model
    response = await query_model(CHAIRMAN_MODEL, messages)
    
    if response is None:
        # Fallback if chairman fails
        return {
            "model": CHAIRMAN_MODEL,
            "response": "Error: Unable to generate final synthesis."
        }

    return {
        "model": clean_model_name(CHAIRMAN_MODEL),
        "response": response.get('content', '')
    }


def build_chairman_prompt(
    user_query: str,
    stage1_results: List[Dict[str, Any]],
    stage2_results: List[Dict[str, Any]],
    context_messages: List[Dict[str, Any]] = None
) -> str:
    """
    Build the prompt for Stage 3 (Chairman Synthesis).
    Uses anonymized labels (Response A, B...) to prevent bias if the chairman
    is one of the council members.

    Args:
        user_query: The original user query
        stage1_results: Individual model responses from Stage 1
        stage2_results: Rankings from Stage 2
        context_messages: Optional list of previous messages

    Returns:
        The complete prompt string
    """
    # Check if this is a multi-round scenario by looking at stage1 model names
    # Group responses by model to create grouped labels
    model_order = []
    model_counts = {}
    labels = []
    
    for result in stage1_results:
        model_key = result['model']
        if model_key not in model_counts:
            model_counts[model_key] = 0
            model_order.append(model_key)
        model_counts[model_key] += 1
        letter_idx = model_order.index(model_key)
        letter = chr(65 + letter_idx)
        round_num = model_counts[model_key]
        labels.append(f"{letter}{round_num}")
    
    # Check if multi-round (any model has more than 1 response)
    is_multi_round = any(count > 1 for count in model_counts.values())
    
    # Map model names to labels for Stage 2 section
    model_to_label = {}
    for label, result in zip(labels, stage1_results):
        # For multi-round, a model may have multiple labels, just track last one for reviewer matching
        model_to_label[result['model']] = f"Response {label}"

    # Format Stage 1 (Anonymized)
    stage1_text = "\n\n".join([
        f"Response {label}:\n{result['response']}"
        for label, result in zip(labels, stage1_results)
    ])
    
    # Build multi-round note if applicable
    multi_round_note = ""
    if is_multi_round:
        model_groups = {}
        for label, result in zip(labels, stage1_results):
            letter = label[0]
            if letter not in model_groups:
                model_groups[letter] = []
            model_groups[letter].append(label)
        
        group_explanations = []
        for letter, group_labels in sorted(model_groups.items()):
            if len(group_labels) > 1:
                group_explanations.append(f"Responses {', '.join(group_labels)} are from the same model (generated in separate, independent sessions)")
        if group_explanations:
            multi_round_note = "\n\nNOTE: " + "; ".join(group_explanations) + "\n"

    # Format Stage 2 (Anonymized attribution)
    # We want to show "Response A1's Ranking: ..." instead of "Model X's Ranking: ..."
    stage2_parts = []
    for result in stage2_results:
        # Find which label corresponds to this model
        reviewer_label = model_to_label.get(result['model'], result['model']) # Fallback if not found
        stage2_parts.append(f"Ranking by {reviewer_label}:\n{result['ranking']}")

    stage2_text = "\n\n".join(stage2_parts)

    context_section = _format_context(context_messages)

    return f"""You are the Chairman of an LLM Council. Multiple AI models have provided responses to a user's question, and then ranked each other's responses.

{context_section}
Original Question: {user_query}

STAGE 1 - Individual Responses (Anonymized):
{stage1_text}
{multi_round_note}
STAGE 2 - Peer Rankings (Anonymized):
{stage2_text}

Your task as Chairman is to synthesize all of this information into a single, comprehensive, accurate answer to the user's original question. Consider:
- The individual responses and their insights
- The peer rankings and what they reveal about response quality
- Any patterns of agreement or disagreement
- The previous conversation context (if any) to ensure continuity

Provide a clear, well-reasoned final answer that represents the council's collective wisdom:"""


def parse_ranking_from_text(ranking_text: str) -> List[str]:
    """
    Parse the FINAL RANKING section from the model's response.

    Args:
        ranking_text: The full text response from the model

    Returns:
        List of response labels in ranked order (e.g., ['Response A1', 'Response B1'])
    """
    import re

    # Look for "FINAL RANKING:" section
    if "FINAL RANKING:" in ranking_text:
        # Extract everything after "FINAL RANKING:"
        parts = ranking_text.split("FINAL RANKING:")
        if len(parts) >= 2:
            ranking_section = parts[1]
            # Try to extract numbered list format with optional round number (e.g., "1. Response A1" or "1. Response A")
            # This pattern matches: number, period, optional space, "Response X" with optional digit(s)
            numbered_matches = re.findall(r'\d+\.\s*Response [A-Z]\d*', ranking_section)
            if numbered_matches:
                # Extract just the "Response X" or "Response X1" part
                return [re.search(r'Response [A-Z]\d*', m).group() for m in numbered_matches]

            # Fallback: Extract all "Response X" or "Response X1" patterns in order
            matches = re.findall(r'Response [A-Z]\d*', ranking_section)
            return matches

    # Fallback: try to find any "Response X" or "Response X1" patterns in order
    matches = re.findall(r'Response [A-Z]\d*', ranking_text)
    return matches


def calculate_aggregate_rankings(
    stage2_results: List[Dict[str, Any]],
    label_to_model: Dict[str, str]
) -> List[Dict[str, Any]]:
    """
    Calculate aggregate rankings across all models.

    Args:
        stage2_results: Rankings from each model
        label_to_model: Mapping from anonymous labels to model names

    Returns:
        List of dicts with model name and average rank, sorted best to worst
    """
    from collections import defaultdict

    # Track positions for each model
    model_positions = defaultdict(list)

    for ranking in stage2_results:
        ranking_text = ranking['ranking']

        # Parse the ranking from the structured format
        parsed_ranking = parse_ranking_from_text(ranking_text)

        for position, label in enumerate(parsed_ranking, start=1):
            if label in label_to_model:
                model_name = label_to_model[label]
                model_positions[model_name].append(position)

    # Calculate average position for each model
    aggregate = []
    for model, positions in model_positions.items():
        if positions:
            avg_rank = sum(positions) / len(positions)
            aggregate.append({
                "model": model,
                "average_rank": round(avg_rank, 2),
                "rankings_count": len(positions)
            })

    # Sort by average rank (lower is better)
    aggregate.sort(key=lambda x: x['average_rank'])

    return aggregate


async def generate_conversation_title(user_query: str) -> str:
    """
    Generate a short title for a conversation based on the first user message.

    Args:
        user_query: The first user message

    Returns:
        A short title (3-5 words)
    """
    title_prompt = f"""Generate a very short title (3-5 words maximum) that summarizes the following question.
The title should be concise and descriptive. Do not use quotes or punctuation in the title.

Question: {user_query}

Title:"""

    # Use AI Studio automation for title generation (using a Flash model)
    title = await run_ai_studio_automation(title_prompt, model="Gemini 2.5 Flash")

    if not title or title.startswith("Error:"):
        # Fallback to a generic title if automation fails
        return "New Conversation"

    # Clean up the title - remove quotes, limit length
    title = title.strip('"\'')

    # Truncate if too long
    if len(title) > 50:
        title = title[:47] + "..."

    return title


async def run_ai_studio_automation(prompt: str, model: str, images: list = None, image_base64: str = None) -> str:
    """
    Run the AI Studio automation script via subprocess.
    """
    script_path = Path(__file__).parent.parent / "browser_automation" / "ai_studio_automation.py"
    
    args = [sys.executable, str(script_path), prompt, "--model", model]
    
    temp_image_paths = []
    
    # Handle single legacy image arg if provided
    if image_base64:
        if os.path.exists(image_base64):
            # It's a path
            args.extend(["--image", image_base64])
        else:
            # It's base64
            path = _save_temp_image(image_base64)
            if path: temp_image_paths.append(path)
        
    # Handle list of images
    if images:
        for img in images:
            if os.path.exists(img):
                # It's a pre-existing path (e.g. from upload)
                args.extend(["--image", img])
            else:
                # It's base64, save to temp
                path = _save_temp_image(img)
                if path: temp_image_paths.append(path)
            
    for path in temp_image_paths:
        args.extend(["--image", path])
    
    async with AI_STUDIO_LOCK:
        try:
            print(f"Executing AI Studio automation...")
            # Run subprocess and capture output
            process = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
        
            stdout, stderr = await process.communicate()
            
            # Cleanup temp images
            for path in temp_image_paths:
                if path and os.path.exists(path):
                    try:
                        os.remove(path)
                    except:
                        pass
            
            if process.returncode != 0:
                error_msg = stderr.decode().strip()
                print(f"AI Studio Automation Error (Code {process.returncode}): {error_msg}")
                return f"Error: AI Studio automation script failed. {error_msg}"
                
            output = stdout.decode().strip()
            # Print full output for debugging
            print("-" * 20 + " AI Studio Automation Output " + "-" * 20)
            print(output)
            print("-" * 70)
            
            # Use unique delimiters to extract the real response
            if "RESULT_START" in output and "RESULT_END" in output:
                response = output.split("RESULT_START")[1].split("RESULT_END")[0].strip()
                
                # Check for footnotes in the response (format [^1], [^2], etc.)
                # If they exist, ensure corresponding definitions are present
                if "[^1]" in response:
                    # Basic check: if we see footnote markers but no "Sources:" or similar section at end
                    # We might want to append the raw sources from output if we captured them separately
                    # But for now, just returning the extraction is good.
                    pass
                    
                return response
                
            return output
        except Exception as e:
            print(f"Subprocess Exception: {e}")
            return f"Error running automation: {str(e)}"


def sort_gemini_models(models: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """
    Sort Gemini models based on capability:
    1. Version number (higher is better)
    2. Tier (Ultra > Pro > Flash)
    3. "Thinking" models as tiebreaker
    """
    def get_model_score(model):
        name = model['name'].lower()
        model_id = model.get('id', '').lower()
        score = 0
        
        # 0. Brand Priority (Highest Priority)
        # Ensure Gemini models are always preferred over others (like Imagen)
        # Prefer "Gemini" in the display name over just in the ID
        if "gemini" in name:
            score += 2000000
        elif "gemini" in model_id:
            score += 1000000

        # Helper to check name or ID for a keyword
        def contains(keyword):
            return keyword in name or keyword in model_id

        # 1. Version number (Highest Priority within brand)
        if contains("4.0"): # Anticipating Future
            score += 40000
        elif contains("4"):
            score += 40000
        elif contains("3.5"):
            score += 35000
        elif contains("3"):
            score += 30000
        elif contains("2.5"):
            score += 25000
        elif contains("2"):
            score += 20000
        elif contains("1.5"):
            score += 15000
            
        # 2. Tier (Second Priority)
        if contains("ultra"):
            score += 5000
        elif contains("pro"):
            score += 3000
        elif contains("flash-lite"):
            score += 1000
        elif contains("flash"):
            score += 2000
            
        # 3. "Thinking" preference (Third Priority - tiebreaker within version/tier)
        if contains("thinking") or contains("reasoning"):
            score += 200
            
        # 4. "Preview" preference (Fourth Priority - tiebreaker)
        if contains("preview"):
            score += 100
            
async def get_ai_studio_models() -> List[Dict[str, str]]:
    """
    Get the list of available models from AI Studio, sorted by capability.
    """
    script_path = Path(__file__).parent.parent / "browser_automation" / "ai_studio_automation.py"
    args = [sys.executable, str(script_path), "--list-models"]
    
    async with AI_STUDIO_LOCK:
        try:
            process = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
        
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                return []
                
            output = stdout.decode().strip()
            models = []
            
            if "MODELS_BEGIN" in output and "MODELS_END" in output:
                model_section = output.split("MODELS_BEGIN")[1].split("MODELS_END")[0].strip()
                for line in model_section.split("\n"):
                    if "|" in line:
                        name, model_id = line.split("|", 1)
                        models.append({"name": name.strip(), "id": model_id.strip()})
            
            # Sort models based on user criteria
            sorted_models = sort_gemini_models(models)
            
            return sorted_models
        except Exception as e:
            print(f"Error getting AI Studio models: {e}")
            return []


async def run_chatgpt_automation(prompt: str, model: str = "auto", images: list = None, image_base64: str = None) -> tuple[str, bool]:
    """
    Run the ChatGPT automation script via subprocess.
    
    Returns:
        Tuple of (response_text, thinking_used)
    """
    script_path = Path(__file__).parent.parent / "browser_automation" / "chatgpt_automation.py"
    
    args = [sys.executable, str(script_path), prompt, "--model", model]
    
    temp_image_paths = []
    
    if image_base64:
        path = _save_temp_image(image_base64)
        if path: temp_image_paths.append(path)
        
    if images:
        for img in images:
            if os.path.exists(img):
                # Pre-existing path (e.g. from upload)
                args.extend(["--image", img])
            else:
                path = _save_temp_image(img)
                if path: temp_image_paths.append(path)
    
    for path in temp_image_paths:
        args.extend(["--image", path])
    
    async with CHATGPT_LOCK:
        try:
            print(f"Executing ChatGPT automation...")
            # Run subprocess and capture output
            process = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
        
            stdout, stderr = await process.communicate()
            
            # Cleanup temp images
            for path in temp_image_paths:
                if path and os.path.exists(path):
                    try:
                        os.remove(path)
                    except:
                        pass
            
            if process.returncode != 0:
                error_msg = stderr.decode().strip()
                print(f"ChatGPT Automation Error (Code {process.returncode}): {error_msg}")
                return f"Error: ChatGPT automation script failed. {error_msg}", False
                
            output = stdout.decode().strip()
            # Print full output for debugging
            print("-" * 20 + " ChatGPT Automation Output " + "-" * 20)
            print(output)
            print("-" * 67)
            
            # Parse THINKING_USED marker
            thinking_used = False
            if "THINKING_USED=true" in output:
                thinking_used = True
            elif "THINKING_USED=false" in output:
                thinking_used = False
            
            # Use unique delimiters to extract the real response
            if "RESULT_START" in output and "RESULT_END" in output:
                response = output.split("RESULT_START")[1].split("RESULT_END")[0].strip()
                return response, thinking_used
                
            # Fallback
            if "Response:" in output:
                response = output.split("Response:")[-1].strip()
                return response, thinking_used
                
            return output, thinking_used
        except Exception as e:
            print(f"Subprocess Exception: {e}")
            return f"Error running automation: {str(e)}", False



async def run_claude_automation(prompt: str, model: str = "auto", images: list = None, image_base64: str = None) -> tuple[str, bool]:
    """
    Run the Claude automation script via subprocess.
    
    Returns:
        Tuple of (response_text, thinking_used)
    """
    script_path = Path(__file__).parent.parent / "browser_automation" / "claude_automation.py"
    
    # Use the same python interpreter as the current process
    args = [sys.executable, str(script_path), prompt, "--model", model]
    
    temp_image_paths = []
    
    if image_base64:
        path = _save_temp_image(image_base64)
        if path: temp_image_paths.append(path)
        
    if images:
        for img in images:
            if os.path.exists(img):
                # Pre-existing path
                args.extend(["--image", img])
            else:
                path = _save_temp_image(img)
                if path: temp_image_paths.append(path)
            
    for path in temp_image_paths:
        args.extend(["--image", path])
    
    async with CLAUDE_LOCK:
        try:
            print(f"Executing Claude automation...")
            # Run subprocess and capture output
            process = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
        
            stdout, stderr = await process.communicate()
            
            # Cleanup temp images
            for path in temp_image_paths:
                if path and os.path.exists(path):
                    try:
                        os.remove(path)
                    except:
                        pass
            
            if process.returncode != 0:
                error_msg = stderr.decode().strip()
                print(f"Claude Automation Error (Code {process.returncode}): {error_msg}")
                return f"Error: Claude automation script failed. {error_msg}", False
                
            output = stdout.decode().strip()
            # Print full output for debugging
            print("-" * 20 + " Claude Automation Output " + "-" * 20)
            print(output)
            print("-" * 67)
            
            # Parse THINKING_USED marker
            thinking_used = False
            if "THINKING_USED=true" in output:
                thinking_used = True
            elif "THINKING_USED=false" in output:
                thinking_used = False
            
            # Use unique delimiters to extract the real response
            if "RESULT_START" in output and "RESULT_END" in output:
                response = output.split("RESULT_START")[1].split("RESULT_END")[0].strip()
                return response, thinking_used
                
            return output, thinking_used
        except Exception as e:
            print(f"Subprocess Exception: {e}")
            return f"Error running automation: {str(e)}", False


async def get_claude_models() -> List[Dict[str, str]]:
    """
    Get the list of available models for Claude.
    Currently hardcoded as Claude doesn't easily expose model lists via simple automation.
    """
    return [
        {"name": "Claude 3.5 Sonnet", "id": "claude-3-5-sonnet"},
        {"name": "Claude 3.5 Sonnet [Ext. Thinking]", "id": "claude-3-5-sonnet-thinking"},
        {"name": "Claude 3 Opus", "id": "claude-3-opus"},
        {"name": "Claude 3 Haiku", "id": "claude-3-haiku"}
    ]



async def run_full_council(
    user_query: str
) -> Tuple[List, List, Dict, Dict]:
    """
    Run the complete 3-stage council process.

    Args:
        user_query: The user's question
        manual_responses: Optional list of manual responses

    Returns:
        Tuple of (stage1_results, stage2_results, stage3_result, metadata)
    """
    # Stage 1: Collect individual responses
    stage1_results = await stage1_collect_responses(user_query)

    # If no models responded successfully, return error
    if not stage1_results:
        return [], [], {"model": CHAIRMAN_MODEL, "response": "Error: No models available."}, {}

    # Stage 2: Collect rankings
    stage2_results, label_to_model = await stage2_collect_rankings(user_query, stage1_results)
    
    # Calculate aggregate rankings for metadata
    aggregate_rankings = calculate_aggregate_rankings(stage2_results, label_to_model)
    
    # Update persistent scores
    update_scores(stage2_results, label_to_model)

    # Stage 3: Synthesize final answer
    stage3_result = await stage3_synthesize_final(user_query, stage1_results, stage2_results)

    metadata = {
        "label_to_model": label_to_model,
        "aggregate_rankings": aggregate_rankings
    }

    return stage1_results, stage2_results, stage3_result, metadata


