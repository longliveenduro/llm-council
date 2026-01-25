import pytest
from browser_automation.chatgpt_automation import clean_chatgpt_text
from browser_automation.claude_automation import clean_claude_text
from browser_automation.ai_studio_automation import clean_ai_studio_text

# --- ChatGPT Tests ---

def test_chatgpt_cleaning():
    text = """The expansion of the universe is accelerating.
NobelPrize.org
+1
This is due to dark energy.
NASA Science
+2"""
    cleaned = clean_chatgpt_text(text)
    assert "NobelPrize.org" not in cleaned
    assert "NASA Science" not in cleaned
    assert "+1" not in cleaned
    assert "+2" not in cleaned
    assert "accelerating." in cleaned
    assert "dark energy." in cleaned

def test_chatgpt_math_placeholder():
    # Verify that math placeholders (created by JS) are preserved 
    text = "The formula is $E=mc^2$."
    cleaned = clean_chatgpt_text(text)
    assert "$E=mc^2$" in cleaned

# --- Claude Tests ---

def test_claude_cleaning():
    text = """Analyzed the request for dark energy.
15s
Dark energy is a mysterious force...
Claude is AI and can make mistakes. Please double-check responses.
Copy to clipboard"""
    cleaned = clean_claude_text(text)
    
    # "Analyzed the request..." is a thinking summary, should be removed
    assert "Analyzed the request" not in cleaned
    # "15s" is a duration, should be removed
    assert "15s" not in cleaned
    # Disclaimer and UI buttons should be removed
    assert "Claude is AI" not in cleaned
    assert "Copy to clipboard" not in cleaned
    # The actual content should remain
    assert "Dark energy is a mysterious force" in cleaned

def test_claude_math_preservation():
    text = "Newton's law: $F = ma$."
    cleaned = clean_claude_text(text)
    assert "$F = ma$" in cleaned

# --- AI Studio Tests ---

def test_ai_studio_cleaning():
    text = """Run
Gemini is processing...
Dark energy makes up 68% of the universe.
Stop
Edit"""
    cleaned = clean_ai_studio_text(text)
    assert "Run" not in cleaned
    assert "Stop" not in cleaned
    assert "Edit" not in cleaned
    assert "makes up 68%" in cleaned

# --- Cross-Model Consistency Test ---

@pytest.mark.parametrize("clean_func", [clean_chatgpt_text, clean_claude_text, clean_ai_studio_text])
def test_general_whitespace_cleanup(clean_func):
    text = "\n\n  Hello World  \n\n\n\n  "
    cleaned = clean_func(text)
    assert cleaned == "Hello World"
