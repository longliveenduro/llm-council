import pytest
from browser_automation.claude_automation import clean_claude_text

def test_clean_claude_text_removes_garbage():
    text = "Some response\nClaude is AI and can make mistakes. Please double-check responses.\nMore response"
    cleaned = clean_claude_text(text)
    assert "Claude is AI and can make mistakes" not in cleaned
    assert "Some response\nMore response" in cleaned

def test_clean_claude_text_removes_timestamps():
    text = "Response start\n3:29 AM\nResponse end"
    cleaned = clean_claude_text(text)
    assert "3:29 AM" not in cleaned
    assert "Response start\nResponse end" in cleaned

def test_clean_claude_text_removes_redundant_prompt():
    prompt = "What is the capital of France?"
    text = "What is the capital of France?\nThe capital of France is Paris."
    cleaned = clean_claude_text(text, prompt=prompt)
    assert prompt not in cleaned
    assert "The capital of France is Paris." in cleaned

def test_clean_claude_text_removes_multiple_new_lines():
    text = "Line 1\n\n\n\nLine 2"
    cleaned = clean_claude_text(text)
    assert "Line 1\n\nLine 2" == cleaned

def test_clean_claude_text_removes_model_names():
    text = "Claude 3.5 Sonnet\nHere is your answer."
    cleaned = clean_claude_text(text)
    assert "Claude 3.5 Sonnet" not in cleaned
    assert "Here is your answer." in cleaned

def test_clean_claude_text_appends_thinking_tag():
    text = "Detailed reasoning about the problem."
    cleaned = clean_claude_text(text, model="claude-3-5-sonnet-thinking")
    assert "[Ext. Thinking]" in cleaned
    assert "Detailed reasoning about the problem." in cleaned

def test_clean_claude_text_does_not_double_append_thinking_tag():
    text = "[Ext. Thinking]\n\nAlready has the tag."
    cleaned = clean_claude_text(text, model="claude-3-5-sonnet-thinking")
    # Should not have [Ext. Thinking] twice
    assert cleaned.count("[Ext. Thinking]") == 1
    assert "Already has the tag." in cleaned

def test_clean_claude_text_removes_notify_me():
    text = "Here is the actual response.\n\nWant to be notified when Claude responds? Notify"
    cleaned = clean_claude_text(text)
    assert "Want to be notified when Claude responds? Notify" not in cleaned
    assert cleaned == "Here is the actual response."

def test_clean_claude_text_removes_thinking_duration():
    text = "Thinking summary\n\n26s\n\nActual response text."
    cleaned = clean_claude_text(text)
    assert "26s" not in cleaned
    assert "Thinking summary" not in cleaned 
    assert "Actual response text." in cleaned

def test_clean_claude_text_removes_empty_prompt_preamble():
    text = "The user prompt is empty, so I cannot provide a summary in the user's language. However, based on the thinking block provided, here is a summary: Weighed formatting compliance against philosophical comprehensiveness.\n\n26s\n\nLet me evaluate each response carefully."
    cleaned = clean_claude_text(text)
    assert "The user prompt is empty" not in cleaned
    assert "26s" not in cleaned
    assert "Let me evaluate" in cleaned

def test_clean_claude_text_removes_short_thinking_summary():
    # Example 1 from user
    text = "Weighed philosophical perspectives on existence's fundamental mystery.\n\nThis is a classic philosophical question about existence itself"
    cleaned = clean_claude_text(text)
    assert "Weighed philosophical perspectives" not in cleaned
    assert "This is a classic philosophical question" in cleaned

def test_clean_claude_text_removes_notify_me_split():
    text = "Here is the actual response.\n\nWant to be notified when Claude responds?\nNotify"
    cleaned = clean_claude_text(text)
    assert "Want to be notified when Claude responds?" not in cleaned
    assert "Notify" not in cleaned
    assert cleaned == "Here is the actual response."

def test_clean_claude_text_removes_elaborate_thinking_summary():
    text = "This is one of the most fundamental philosophical questions ever asked - why does anything exist at all? It's a question that has puzzled philosophers, theologians, and scientists for millennia. Let me think about how to approach this thoughtfully.\n\nThe user is asking about the fundamental question of existence itself. This isn't asking for my personal opinion necessarily, but exploring this deep philosophical question. I should:\n\nAcknowledge the profundity of the question\nPresent different philosophical and scientific perspectives evenhandedly\n\nActual response starts here."
    cleaned = clean_claude_text(text)
    assert "fundamental philosophical questions" not in cleaned
    assert "The user is asking" not in cleaned
    assert "Acknowledge the profundity" not in cleaned
    assert "Actual response starts here." in cleaned
