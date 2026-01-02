
import pytest
import os
import json
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

def test_calculate_points_self_ranking_exclusion():
    """Test that self-ranking is ignored and subsequent models shift up."""
    label_to_model = {
        "Response A": "Model A", # The Reviewer
        "Response B": "Model B",
        "Response C": "Model C"
    }
    
    # Reviewer is Model A
    # Ranking: A (1st), B (2nd), C (3rd)
    # Effect: A removed. B becomes 1st, C becomes 2nd.
    ranked_labels = ["Response A", "Response B", "Response C"]
    points = _calculate_points_for_review(ranked_labels, "Model A", label_to_model)
    
    assert "Model A" not in points
    assert points["Model B"] == 25 # Shifted to 1st
    assert points["Model C"] == 12 # Shifted to 2nd

def test_update_scores_integration(mock_scores_file):
    """Test full update flow with persistence."""
    stage2_results = [
        {
            "model": "Model X",
            "ranking": "FINAL RANKING:\n1. Response A\n2. Response B"
        },
        {
            "model": "Model Y",
            "ranking": "FINAL RANKING:\n1. Response B\n2. Response A" 
        }
    ]
    
    label_to_model = {
        "Response A": "Model A",
        "Response B": "Model B"
    }
    
    # Initial update
    update_scores(stage2_results, label_to_model)
    
    scores = get_scores()
    # Model X votes: A=25, B=12
    # Model Y votes: B=25, A=12
    # Totals: A=37, B=37
    assert scores["Model A"] == 37
    assert scores["Model B"] == 37
    
    # Second update (accumulates)
    update_scores(stage2_results, label_to_model)
    scores = get_scores()
    assert scores["Model A"] == 74
    assert scores["Model B"] == 74
