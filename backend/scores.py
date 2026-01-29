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

def get_scores_file_path() -> str:
    """Get the path to the scores file, which is one level up from DATA_DIR."""
    return os.path.join(str(Path(DATA_DIR).parent), "model_scores.json")

# Compatibility with existing code
SCORES_FILE = get_scores_file_path()

def get_scores() -> Dict[str, float]:
    """
    Retrieve current model scores.
    
    Returns:
        Dict mapping model names to their score (float).
    """
    scores_file = get_scores_file_path()
    if not os.path.exists(scores_file):
        return {}
    
    try:
        with open(scores_file, 'r') as f:
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
        scores_file = get_scores_file_path()
        with open(scores_file, 'w') as f:
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
) -> Dict[str, float]:
    """
    Calculate points awarded by a single reviewer.
    
    For multi-round scenarios where a model has multiple responses (A1, A2, A3),
    we average the ranks of all responses from that model before calculating points.
    
    Args:
        ranked_labels: List of labels (e.g. ['Response A1', 'Response B1']) in ranked order.
        reviewer_model: The name of the model doing the reviewing.
        label_to_model: Mapping from label to model name.
        
    Returns:
        Dict mapping model names to points earned from this review.
    """
    # First, collect all rank positions (1-indexed) for each model
    model_ranks = {}  # model_name -> list of rank positions
    
    for i, label in enumerate(ranked_labels):
        model_name = label_to_model.get(label)
        if model_name:
            rank_position = i + 1  # 1-indexed rank
            if model_name not in model_ranks:
                model_ranks[model_name] = []
            model_ranks[model_name].append(rank_position)
    
    # Calculate average rank per model
    model_avg_ranks = {}
    for model_name, ranks in model_ranks.items():
        model_avg_ranks[model_name] = sum(ranks) / len(ranks)
    
    # Sort models by their average rank to determine final positions
    sorted_models = sorted(model_avg_ranks.items(), key=lambda x: x[1])
    
    # Award points based on position in the averaged ranking
    points_map = {}
    for i, (model_name, avg_rank) in enumerate(sorted_models):
        points = RANKING_POINTS.get(i, 0)
        if points > 0:
            points_map[model_name] = points
            
    return points_map
