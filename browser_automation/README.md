# Browser Automation for AI Studio

This module provides browser automation for interacting with Google AI Studio
without requiring API access. It uses Playwright to control a browser where
you're already logged in with your free Google account.

## Setup

1. Install Playwright:
```bash
pip install playwright
playwright install chromium
```

2. Launch Chrome with remote debugging enabled:
```bash
google-chrome --remote-debugging-port=9222
```

3. In that Chrome window, navigate to https://aistudio.google.com and log in with your Google account.

## Usage

### Single Prompt
```bash
python ai_studio_automation.py "What is the capital of France?"
```

### Interactive Mode
```bash
python ai_studio_automation.py --interactive
```

### With New Browser (for first-time setup)
```bash
python ai_studio_automation.py --new-browser --interactive
```

## How It Works

1. **Connect**: The script connects to your existing Chrome browser via the remote debugging protocol
2. **Navigate**: If not already on AI Studio, it navigates there
3. **Input**: It finds the prompt textarea and types your prompt
4. **Send**: It clicks the Run/Send button
5. **Extract**: It waits for the response and extracts the text

## Troubleshooting

### "Could not connect to browser"
Make sure Chrome is running with `--remote-debugging-port=9222`

### "Could not find chat input element"
The AI Studio UI may have changed. You may need to update the selectors in the script.

### Login Required
If you see a login page, log in manually in the browser first, then run the script again.
