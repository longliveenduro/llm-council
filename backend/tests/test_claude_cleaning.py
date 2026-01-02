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
