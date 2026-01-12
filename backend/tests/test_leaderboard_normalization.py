import pytest
import os
import json
from unittest.mock import patch
from backend.scores import update_scores, get_scores, SCORES_FILE
from backend.utils import clean_model_name

@pytest.fixture
def mock_scores_file(tmp_path):
    import backend.scores
    original_path = backend.scores.SCORES_FILE
    test_file = tmp_path / "test_model_scores.json"
    backend.scores.SCORES_FILE = str(test_file)
    yield test_file
    backend.scores.SCORES_FILE = original_path

def test_leaderboard_normalization_aggregation(mock_scores_file):
    """Test that points for 'Model Thinking' and 'Model' are aggregated under 'Model'."""
    # Round 1: ChatGPT 5.2 Thinking gets 25 points
    stage2_results_1 = [
        {'model': 'Reviewer', 'ranking': 'FINAL RANKING:\n1. Response A (ChatGPT 5.2 Thinking)'}
    ]
    label_to_model_1 = {'Response A': 'ChatGPT 5.2 Thinking'}
    
    update_scores(stage2_results_1, label_to_model_1)
    scores = get_scores()
    assert "ChatGPT 5.2" in scores
    assert "ChatGPT 5.2 Thinking" not in scores
    first_score = scores["ChatGPT 5.2"]
    
    # Round 2: Chat GPT 5.2 (clean) gets lower points (e.g. 2nd place = 12 pts)
    stage2_results_2 = [
        {'model': 'Reviewer', 'ranking': 'FINAL RANKING:\n1. Response B\n2. Response A'}
    ]
    label_to_model_2 = {'Response A': 'Chat GPT 5.2', 'Response B': 'Other Model'}
    
    update_scores(stage2_results_2, label_to_model_2)
    scores = get_scores()
    
    # Both should have contributed to "ChatGPT 5.2"
    assert "ChatGPT 5.2" in scores
    # Expected: (25.0 * 0.8) + (12.0 * 0.2) = 20.0 + 2.4 = 22.4
    assert scores["ChatGPT 5.2"] == 22.4
    
    # Check that no legacy names exist
    assert "ChatGPT 5.2 Thinking" not in scores
    assert "Chat GPT 5.2" not in scores
