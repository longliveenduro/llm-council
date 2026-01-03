
import pytest
import os
import json
from unittest.mock import patch
from backend.scores import update_scores, get_scores, _calculate_points_for_review, SCORES_FILE

@pytest.fixture
def mock_scores_file(tmp_path):
    """Setup a temporary scores file."""
    # Override SCORES_FILE for testing
    # Since we can't easily patch the constant in the module without reloading,
    # we'll mock the functions that use it or monkeypatch if possible.
    # Actually, simpler to just check logic first. 
    # But integration test needs file writing.
    
    # Let's save the original path and restore it
    import backend.scores
    original_path = backend.scores.SCORES_FILE
    
    test_file = tmp_path / "test_model_scores.json"
    backend.scores.SCORES_FILE = str(test_file)
    
    yield test_file
    
    backend.scores.SCORES_FILE = original_path

def test_calculate_points_basic():
    """Test basic point calculation logic."""
    label_to_model = {
        "Response A": "Model A",
        "Response B": "Model B",
        "Response C": "Model C"
    }
    
    # Reviewer is Model C
    # Ranking: A (1st), B (2nd)
    ranked_labels = ["Response A", "Response B"]
    points = _calculate_points_for_review(ranked_labels, "Model C", label_to_model)
    
    assert points["Model A"] == 25  # 1st place
    assert points["Model B"] == 12  # 2nd place
    assert "Model C" not in points

def test_calculate_points_includes_self_ranking():
    """Test that self-ranking is INCLUDED in the score."""
    label_to_model = {
        "Response A": "Model A", # The Reviewer
        "Response B": "Model B",
        "Response C": "Model C"
    }
    
    # Reviewer is Model A
    # Ranking: A (1st), B (2nd), C (3rd)
    # Effect: A stays 1st (25 pts), B is 2nd (12 pts), C is 3rd (6 pts)
    ranked_labels = ["Response A", "Response B", "Response C"]
    points = _calculate_points_for_review(ranked_labels, "Model A", label_to_model)
    
    assert points["Model A"] == 25 # Self-vote counts!
    assert points["Model B"] == 12 
    assert points["Model C"] == 6

@patch('backend.scores.get_scores')
@patch('backend.scores.save_scores')
def test_update_scores_initial(mock_save, mock_get):
    """Test that new models get their first round average as initial score."""
    mock_get.return_value = {}
    
    # Setup: Model A gets ranked 1st by Model B (25 pts)
    # Model B gets ranked 1st by Model A (25 pts)
    stage2_results = [
        {'model': 'Model B', 'ranking': 'FINAL RANKING:\n1. Response A (Model A)'},
        {'model': 'Model A', 'ranking': 'FINAL RANKING:\n1. Response B (Model B)'}
    ]
    label_to_model = {
        'Response A': 'Model A',
        'Response B': 'Model B'
    }
    
    update_scores(stage2_results, label_to_model)
    
    # Verify save was called
    mock_save.assert_called_once()
    saved_scores = mock_save.call_args[0][0]
    
    # Model A: 1 review, 25 points -> Avg 25.0
    # Model B: 1 review, 25 points -> Avg 25.0
    assert saved_scores['Model A'] == 25.0
    assert saved_scores['Model B'] == 25.0


@patch('backend.scores.get_scores')
@patch('backend.scores.save_scores')
def test_update_scores_decay(mock_save, mock_get):
    """Test that existing scores decay towards new performance."""
    # Initial score 10.0
    mock_get.return_value = {'Model A': 10.0}
    
    # Model A gets ranked 1st (25 pts) this round
    stage2_results = [
        {'model': 'Model B', 'ranking': 'FINAL RANKING:\n1. Response A (Model A)'}
    ]
    label_to_model = {
        'Response A': 'Model A',
        'Response B': 'Model B'
    }
    
    update_scores(stage2_results, label_to_model)
    
    saved_scores = mock_save.call_args[0][0]
    
    # Expected: (10.0 * 0.8) + (25.0 * 0.2) = 8.0 + 5.0 = 13.0
    assert saved_scores['Model A'] == 13.0


@patch('backend.scores.get_scores')
@patch('backend.scores.save_scores')
def test_legacy_reset(mock_save, mock_get):
    """Test that legacy high scores are reset to 0."""
    mock_get.return_value = {'Model A': 500} # Legacy accumulated score
    
    # Model A performs poorly (3rd place = 6 pts)
    stage2_results = [
        {'model': 'Model B', 'ranking': 'FINAL RANKING:\n1. Response X\n2. Response Y\n3. Response A'}
    ]
    label_to_model = {
        'Response A': 'Model A',
        'Response X': 'Model X',
        'Response Y': 'Model Y'
    }
    
    update_scores(stage2_results, label_to_model)
    
    saved_scores = mock_save.call_args[0][0]
    
    # Legacy score 500 should be treated as 0 for the "previous" part of EMA
    # But since it's reset to 0.0, the "new model" logic kicks in
    # So it takes the round score directly.
    # Round score = 6.0
    assert saved_scores['Model A'] == 6.0
