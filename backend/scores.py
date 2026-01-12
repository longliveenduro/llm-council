"""
Module for tracking and persisting model success rates (highscores).
"""

import json
import os
from typing import List, Dict, Any
from pathlib import Path
from .config import DATA_DIR
from .utils import clean_model_name


# Points for rankings (0-indexed: 1st, 2nd, 3rd...)

# Exponential Moving Average weight (0.2 = valid for last ~5 runs)
EMA_ALPHA = 0.2

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

def get_scores() -> Dict[str, float]:
    """
    Retrieve current model scores.
    
    Returns:
        Dict mapping model names to their score (float).
    """
    if not os.path.exists(SCORES_FILE):
        return {}
    
    try:
        with open(SCORES_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading scores: {e}")
        return {}


def save_scores(scores: Dict[str, float]):
    """
    Save scores to disk.
    
    Args:
        scores: Dict mapping model names to their score.
    """
    try:
        with open(SCORES_FILE, 'w') as f:
            json.dump(scores, f, indent=2)
    except Exception as e:
        print(f"Error saving scores: {e}")


def update_scores(stage2_results: List[Dict[str, Any]], label_to_model: Dict[str, str]):
    """
    Update scores based on Stage 2 rankings using Exponential Moving Average.
    
    Args:
        stage2_results: List of dicts containing 'model' (reviewer) and 'ranking' (text).
        label_to_model: Mapping from anonymous labels (Response A) to model names.
    """
    from .council import parse_ranking_from_text
    current_scores = get_scores()
    
    # 1. Detect and reset legacy scores (accumulated integers) if found
    # Since max points per round is 25, any score significantly higher is legacy.
    for model, score in list(current_scores.items()):
        if score > 25:
            print(f"Resetting legacy score for {model}: {score} -> 0")
            current_scores[model] = 0.0

    # 2. Calculate raw points for THIS round for all models
    # We track total points and number of reviews for this specific round
    round_stats = {model: {'points': 0, 'reviews': 0} for model in label_to_model.values()}

    for result in stage2_results:
        reviewer_model = result.get('model')
        ranking_text = result.get('ranking') or ""
        
        # Parse the ranking
        ranked_labels = parse_ranking_from_text(ranking_text)
        
        # Calculate points for this single review
        points_map = _calculate_points_for_review(ranked_labels, reviewer_model, label_to_model)
        
        # Aggregate stats for the round
        for model, points in points_map.items():
            if model in round_stats:
                round_stats[model]['points'] += points
                round_stats[model]['reviews'] += 1
                
    # 3. Apply EMA updates
    for model, stats in round_stats.items():
        if stats['reviews'] == 0:
            continue
            
        # The score for this specific round is the average of points received
        # (e.g. if Model A got 25 pts from one reviewer and 12 from another, round_score is 18.5)
        round_avg_score = stats['points'] / stats['reviews']
        
        # CLEAN MODEL NAME BEFORE SAVING/CHECKING
        clean_name = clean_model_name(model)
        prev_score = current_scores.get(clean_name)
        
        if prev_score is None or prev_score == 0:
            # New model or first run: initialize with this round's score directly
            # This gives new models a "fast start" to their actual performance level
            current_scores[clean_name] = round_avg_score
        else:
            # Existing model: Apply EMA decay
            # New Score = (Previous * (1 - Alpha)) + (Round * Alpha)
            new_score = (prev_score * (1 - EMA_ALPHA)) + (round_avg_score * EMA_ALPHA)
            current_scores[clean_name] = round(new_score, 2)
            
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
        if model_name: 
            # We treat self-ranked models as VALID votes (since they are anonymized)
            clean_ranking_models.append(model_name)
            
    # Award points based on position in clean list
    for i, model_name in enumerate(clean_ranking_models):
        points = RANKING_POINTS.get(i, 0)
        if points > 0:
            points_map[model_name] = points
            
    return points_map
