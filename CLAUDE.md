# CLAUDE.md - Technical Notes for LLM Council

This file contains technical details, architectural decisions, and important implementation notes for future development sessions.

## Project Overview

LLM Council is a 3-stage deliberation system where multiple LLMs collaboratively answer user questions. The key innovation is anonymized peer review in Stage 2, preventing models from playing favorites.

## Architecture

### Backend Structure (`backend/`)

**`config.py`**
- Contains `COUNCIL_MODELS` (list of OpenRouter model identifiers)
- Contains `CHAIRMAN_MODEL` (model that synthesizes final answer)
- Uses environment variable `OPENROUTER_API_KEY` from `.env`
- Backend runs on **port 8001**

**`openrouter.py`**
- `query_model()`: Single async model query using httpx
- `query_models_parallel()`: Parallel queries using `asyncio.gather()`

**`council.py`** - The Core Logic
- `stage1_collect_responses()`: Parallel queries to all council models
- `stage2_collect_rankings()`: Anonymizes responses and prompts for peer review
- `stage3_synthesize_final()`: Chairman synthesis from all responses + rankings
- Includes helper methods for automation login/logout and model syncing

**Browser Automation (`browser_automation/`)** - Web ChatBot Engine
- `ai_studio_automation.py`: Playwright script for Google AI Studio
- `chatgpt_automation.py`: Playwright script for ChatGPT
- Uses persistent context in `.ai_studio_browser_data` and `.chatgpt_browser_data`
- Supports headful login via interactive commands

### Frontend Structure (`frontend/src/`)

**`App.jsx`**
- Main orchestration: manages conversations and automation status
- Handles theme persistence (light/dark)

**`components/WebChatBotWizard.jsx`**
- Orchestrates the semi-automated 3-stage process
- Interfaces with backend automation endpoints

**`components/Sidebar.jsx`**
- Displays council members, conversation history, and automation controls
- Includes theme toggle and automation login/sync buttons

**Styling (`index.css` & `*.css`)**
- Supports **Dark Mode** via `[data-theme='dark']` and CSS variables
- Primary color: #4a90e2 (blue)
- Global markdown styling with `.markdown-content` class

## Key Design Decisions

### Browser Automation
- **Playwright over Selenium**: Better reliability and modern API
- **Persistent Context**: Saves cookies/sessions locally to avoid repeated logins
- **Interactive Login**: Launches a visible browser window for the user to handle 2FA/Captchas once

### Dark Mode
- Implementation via CSS variables for easy maintenance
- Icon filters (`invert`) used to adapt brand logos to dark backgrounds

## Important Implementation Details

### Testing Framework
- **`run_tests.sh`**: Unified script to run all tests
- **Backend**: Pytest in `backend/tests/` (Smoke tests + Automation extraction tests)
- **Frontend**: Vitest for component testing (`App.test.jsx`)
- Ensure Node 20+ is used for frontend tests

### Port Configuration
- Backend: 8001
- Frontend: 5173 (Vite default)

## Common Gotchas

1. **Module Import Errors**: Always run backend as `python -m backend.main` from project root
2. **Playwright Drivers**: Must run `playwright install chromium` on new environments
3. **CORS**: Check `main.py` if frontend port changes

## Data Flow Summary

```
User Query
    ↓
Stage 1: Parallel OpenRouter OR Manual Automation → [responses]
    ↓
Stage 2: Anonymize → Peer Review → [rankings]
    ↓
Stage 3: Chairman synthesis
    ↓
Return: {stage1, stage2, stage3, metadata}
```
