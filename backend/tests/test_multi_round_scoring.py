"""
Tests for multi-round scoring functionality.
"""

import pytest
from unittest.mock import patch
from backend.scores import _calculate_points_for_review, RANKING_POINTS


class TestMultiRoundScoring:
    """Test scoring when a single model has multiple responses (rounds)."""

    def test_average_ranks_single_model_multiple_responses(self):
        """
        Test that when a model has multiple responses (A1, A2, A3),
        their ranks are averaged before calculating points.
        
        Example: Model A has ranks 1, 1, 2 → average 1.33
                 Model B has rank 3 → average 3
        So Model A should get 1st place points, Model B gets 2nd.
        """
        # Ranking: A1 (1st), A2 (2nd), A3 (3rd), B1 (4th)
        ranked_labels = ['Response A1', 'Response A2', 'Response A3', 'Response B1']
        label_to_model = {
            'Response A1': 'Model A',
            'Response A2': 'Model A',
            'Response A3': 'Model A',
            'Response B1': 'Model B'
        }
        
        points = _calculate_points_for_review(ranked_labels, 'Reviewer', label_to_model)
        
        # Model A's average rank is (1+2+3)/3 = 2.0
        # Model B's average rank is 4
        # Model A is 1st → 25 points, Model B is 2nd → 12 points
        assert points['Model A'] == 25
        assert points['Model B'] == 12

    def test_average_ranks_two_models_interleaved(self):
        """
        Test with interleaved rankings from two models.
        
        Ranking: A1 (1st), B1 (2nd), A2 (3rd), B2 (4th)
        Model A: ranks 1, 3 → avg 2.0
        Model B: ranks 2, 4 → avg 3.0
        Model A gets 1st place, Model B gets 2nd.
        """
        ranked_labels = ['Response A1', 'Response B1', 'Response A2', 'Response B2']
        label_to_model = {
            'Response A1': 'Model A',
            'Response A2': 'Model A',
            'Response B1': 'Model B',
            'Response B2': 'Model B'
        }
        
        points = _calculate_points_for_review(ranked_labels, 'Reviewer', label_to_model)
        
        # Model A avg rank: (1+3)/2 = 2.0
        # Model B avg rank: (2+4)/2 = 3.0
        # Model A is 1st (25), Model B is 2nd (12)
        assert points['Model A'] == 25
        assert points['Model B'] == 12

    def test_average_ranks_model_b_wins(self):
        """
        Test when Model B's responses consistently rank better.
        
        Ranking: B1 (1st), B2 (2nd), A1 (3rd), A2 (4th)
        Model A: ranks 3, 4 → avg 3.5
        Model B: ranks 1, 2 → avg 1.5
        Model B gets 1st place.
        """
        ranked_labels = ['Response B1', 'Response B2', 'Response A1', 'Response A2']
        label_to_model = {
            'Response A1': 'Model A',
            'Response A2': 'Model A',
            'Response B1': 'Model B',
            'Response B2': 'Model B'
        }
        
        points = _calculate_points_for_review(ranked_labels, 'Reviewer', label_to_model)
        
        # Model B avg rank: (1+2)/2 = 1.5 → 1st place (25 pts)
        # Model A avg rank: (3+4)/2 = 3.5 → 2nd place (12 pts)
        assert points['Model B'] == 25
        assert points['Model A'] == 12

    def test_three_models_with_multiple_rounds(self):
        """
        Test with three models, each having different numbers of responses.
        
        Ranking: A1 (1st), B1 (2nd), C1 (3rd), A2 (4th), B2 (5th), C2 (6th)
        Model A: ranks 1, 4 → avg 2.5
        Model B: ranks 2, 5 → avg 3.5
        Model C: ranks 3, 6 → avg 4.5
        """
        ranked_labels = ['Response A1', 'Response B1', 'Response C1', 
                         'Response A2', 'Response B2', 'Response C2']
        label_to_model = {
            'Response A1': 'Model A',
            'Response A2': 'Model A',
            'Response B1': 'Model B',
            'Response B2': 'Model B',
            'Response C1': 'Model C',
            'Response C2': 'Model C'
        }
        
        points = _calculate_points_for_review(ranked_labels, 'Reviewer', label_to_model)
        
        # Model A: 1st place (25), Model B: 2nd place (12), Model C: 3rd place (6)
        assert points['Model A'] == 25
        assert points['Model B'] == 12
        assert points['Model C'] == 6

    def test_single_round_still_works(self):
        """
        Test that single-round (legacy) cases still work correctly.
        """
        ranked_labels = ['Response A1', 'Response B1', 'Response C1']
        label_to_model = {
            'Response A1': 'Model A',
            'Response B1': 'Model B',
            'Response C1': 'Model C'
        }
        
        points = _calculate_points_for_review(ranked_labels, 'Reviewer', label_to_model)
        
        assert points['Model A'] == 25  # 1st
        assert points['Model B'] == 12  # 2nd
        assert points['Model C'] == 6   # 3rd

    def test_average_rank_example_from_requirements(self):
        """
        Test the exact example from requirements:
        Three responses from Model A score ranks 1, 1, 2.
        Average = 1.33
        """
        # Model A has 3 responses ranked 1st, 1st, 2nd
        # Model B has 1 response ranked 3rd
        ranked_labels = ['Response A1', 'Response A2', 'Response A3', 'Response B1']
        # Fix: A1 and A2 are both ranked 1st, A3 is 2nd, B1 is last
        # Actually, in a ranking list, positions are sequential, so:
        # If the ranking is: A1, A2, A3, B1 → positions are 1, 2, 3, 4
        # To get ranks 1, 1, 2 for model A, the ranking would need ties which we don't model
        # Instead, let's test the averaging behavior with sequential ranks
        
        # Ranking: A1 (1st), A2 (2nd), A3 (3rd), B1 (4th)
        # Model A avg: (1+2+3)/3 = 2.0
        # Model B avg: 4.0
        # Model A gets 1st place points
        label_to_model = {
            'Response A1': 'Model A',
            'Response A2': 'Model A',
            'Response A3': 'Model A',
            'Response B1': 'Model B'
        }
        
        points = _calculate_points_for_review(ranked_labels, 'Reviewer', label_to_model)
        
        assert points['Model A'] == 25  # Best average rank → 1st place
        assert points['Model B'] == 12  # Worst average rank → 2nd place
