from abc import ABC, abstractmethod
from typing import Dict, Any

class AbstractPredictor(ABC):
    """
    Abstract base class for predicting player prop probabilities.
    Any new model implementation must inherit from this and implement
    these underlying methods.
    """
    
    @abstractmethod
    def predict_point_estimate(self, player_id: int, stat: str, date: str) -> float:
        """
        Returns a point estimate (expected value) for a given player's stat 
        on a specific calendar date. 
        
        Args:
            player_id (int): ID of the player to predict for
            stat (str): Stat to predict (e.g., 'PTS', 'AST', 'REB')
            date (str): The date of the game (YYYY-MM-DD). The implementation 
                        must ensure it only uses data strictly BEFORE this date.
        """
        pass
        
    @abstractmethod
    def predict_conformal_probability(self, player_id: int, stat: str, threshold: float, date: str) -> Dict[str, float]:
        """
        Returns the conformal probability of the player's stat exceeding the threshold.
        
        Returns:
            dict: A dictionary with 'p_over' and 'p_under' probabilities.
        """
        pass

    @abstractmethod
    def setup(self):
        """
        Any necessary setup, loading model weights, or caching data should happen here.
        """
        pass
