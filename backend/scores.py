"""
Module for tracking and persisting model success rates (highscores).
"""

import json
import os
from typing import List, Dict, Any
from pathlib import Path
from .config import DATA_DIR


# Points for rankings (0-indexed: 1st, 2nd, 3rd...)
RANKING_POINTS = {
    0: 25,  # 1st place
    1: 12,  # 2nd place
    2: 6,   # 3rd place
    3: 3,   # 4th place
    4: 2,   # 5th place
    5: 1,   # 6th place
    # 7th or lower (index 6+) gets 0 points
}

SCORES_FILE = os.path.join(str(Path(DATA_DIR).parent), "model_scores.json")

def get_scores() -> Dict[str, int]:
    """
    Retrieve current model scores.
    
    Returns:
        Dict mapping model names to their total score.
    """
    if not os.path.exists(SCORES_FILE):
        return {}
    
    try:
        with open(SCORES_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading scores: {e}")
        return {}


def save_scores(scores: Dict[str, int]):
    """
    Save scores to disk.
    
    Args:
        scores: Dict mapping model names to their total score.
    """
    try:
        with open(SCORES_FILE, 'w') as f:
            json.dump(scores, f, indent=2)
    except Exception as e:
        print(f"Error saving scores: {e}")


def update_scores(stage2_results: List[Dict[str, Any]], label_to_model: Dict[str, str]):
    """
    Update scores based on Stage 2 rankings.
    
    Args:
        stage2_results: List of dicts containing 'model' (reviewer) and 'ranking' (text).
        label_to_model: Mapping from anonymous labels (Response A) to model names.
    """
    from .council import parse_ranking_from_text
    current_scores = get_scores()
    
    # Ensure all participating models are tracked, even if they get 0 points
    for model_name in label_to_model.values():
        if model_name not in current_scores:
            current_scores[model_name] = 0
            
    for result in stage2_results:
        reviewer_model = result.get('model')
        ranking_text = result.get('ranking') or ""
        
        # Parse the ranking
        # This returns a list of labels like ['Response A', 'Response C', ...]
        ranked_labels = parse_ranking_from_text(ranking_text)
        
        # Calculate points for this review
        points_awarded = _calculate_points_for_review(ranked_labels, reviewer_model, label_to_model)
        
        # Apply points
        for model_name, points in points_awarded.items():
            current_scores[model_name] = current_scores.get(model_name, 0) + points
            
    save_scores(current_scores)


def _calculate_points_for_review(
    ranked_labels: List[str], 
    reviewer_model: str, 
    label_to_model: Dict[str, str]
) -> Dict[str, int]:
    """
    Calculate points awarded by a single reviewer, excluding self-ranking.
    
    Args:
        ranked_labels: List of labels (e.g. ['Response A', 'Response B']) in ranked order.
        reviewer_model: The name of the model doing the reviewing.
        label_to_model: Mapping from label to model name.
        
    Returns:
        Dict mapping model names to points earned from this review.
    """
    points_map = {}
    
    # Filter out the reviewer from the ranking (self-ranking exclusion)
    clean_ranking_models = []
    
    for label in ranked_labels:
        model_name = label_to_model.get(label)
        if model_name and model_name != reviewer_model:
            clean_ranking_models.append(model_name)
            
    # Award points based on position in clean list
    for i, model_name in enumerate(clean_ranking_models):
        points = RANKING_POINTS.get(i, 0)
        if points > 0:
            points_map[model_name] = points
            
    return points_map
