import pytest
from backend.council import sort_claude_models

def test_sort_claude_models_priority():
    models = [
        {"name": "Claude 3.5 Sonnet", "id": "claude-3-5-sonnet"},
        {"name": "Claude 4.5 Opus", "id": "claude-4-5-opus"},
        {"name": "Claude 4.5 Sonnet", "id": "claude-4-5-sonnet"},
        {"name": "Claude 3 Opus", "id": "claude-3-opus"},
    ]
    
    sorted_models = sort_claude_models(models)
    
    # Expected order:
    # 1. Claude 4.5 Sonnet (30000 + 5000 = 35000)
    # 2. Claude 4.5 Opus   (30000 + 3000 = 33000)
    # 3. Claude 3.5 Sonnet (20000 + 5000 = 25000)
    # 4. Claude 3 Opus     (10000 + 3000 = 13000)
    
    assert sorted_models[0]['name'] == "Claude 4.5 Sonnet"
    assert sorted_models[1]['name'] == "Claude 4.5 Opus"
    assert sorted_models[2]['name'] == "Claude 3.5 Sonnet"
    assert sorted_models[3]['name'] == "Claude 3 Opus"
