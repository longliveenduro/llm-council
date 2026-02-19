import pytest
from backend.utils import clean_model_name

def test_clean_model_name_thinking():
    assert clean_model_name("ChatGPT 5.2 Thinking") == "ChatGPT 5.2"
    assert clean_model_name("Claude Sonnet 4.6 [Ext. Thinking]") == "Claude Sonnet 4.6"
    assert clean_model_name("Claude Sonnet 4.6 (Ext) Thinking") == "Claude Sonnet 4.6"
    assert clean_model_name("ChatGPT 5.2 [Thinking]") == "ChatGPT 5.2"
    assert clean_model_name("ChatGPT 5.2 (Thinking)") == "ChatGPT 5.2"

def test_clean_model_name_spacing():
    assert clean_model_name("Chat GPT 5.2") == "ChatGPT 5.2"
    assert clean_model_name("Chat GPT 5.2 Thinking") == "ChatGPT 5.2"

def test_clean_model_name_no_change():
    assert clean_model_name("Gemini 3 Pro Preview") == "Gemini 3 Pro Preview"
    assert clean_model_name("GPT-4o") == "GPT-4o"

def test_clean_model_name_empty():
    assert clean_model_name("") == ""
    assert clean_model_name(None) is None

def test_clean_model_name_case_insensitive():
    assert clean_model_name("ChatGPT 5.2 thinking") == "ChatGPT 5.2"
    assert clean_model_name("chat gpt 5.2") == "ChatGPT 5.2"
