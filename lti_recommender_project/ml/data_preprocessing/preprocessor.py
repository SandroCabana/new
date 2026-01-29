"""
Data preprocessing utilities for recommendation models.
Handles data transformation, splitting, and validation.
"""

import logging
from typing import List, Dict, Tuple, Optional
from collections import defaultdict
import numpy as np

logger = logging.getLogger(__name__)


class DataPreprocessor:
    """
    Preprocessor for recommendation model training data.
    Handles data extraction, cleaning, and splitting.
    """
    
    def __init__(self, min_interactions_per_user: int = 2, min_interactions_per_item: int = 1):
        """
        Initialize the preprocessor.
        
        Args:
            min_interactions_per_user: Minimum interactions required per user
            min_interactions_per_item: Minimum interactions required per item
        """
        self.min_interactions_per_user = min_interactions_per_user
        self.min_interactions_per_item = min_interactions_per_item
    
    def get_interaction_data(
        self, 
        context_id: Optional[str] = None
    ) -> List[Dict]:
        """
        Extract interaction data from the database.
        
        Args:
            context_id: Optional context filter
            
        Returns:
            List of interaction dictionaries
        """
        from lti_recommender_project.apps.interactions.models import UserInteraction
        
        queryset = UserInteraction.objects.select_related('resource')
        
        if context_id:
            queryset = queryset.filter(lti_context_id=context_id)
        
        interactions = []
        for interaction in queryset:
            # Calculate effective rating
            if interaction.rating:
                rating = float(interaction.rating)
            elif interaction.completion_percentage:
                rating = 1.0 + (interaction.completion_percentage / 100.0) * 4.0
            else:
                rating = 3.0  # Default neutral rating for views
            
            interactions.append({
                'user_id': interaction.lti_user_id,
                'item_id': interaction.resource_id,
                'rating': rating,
                'timestamp': interaction.timestamp,
                'interaction_type': interaction.interaction_type,
                'context_id': interaction.lti_context_id,
            })
        
        logger.info(f"Extracted {len(interactions)} interactions")
        return interactions
    
    def filter_cold_start(
        self, 
        interactions: List[Dict]
    ) -> List[Dict]:
        """
        Filter out users and items with too few interactions.
        
        Args:
            interactions: List of interaction dictionaries
            
        Returns:
            Filtered list of interactions
        """
        # Count interactions per user and item
        user_counts = defaultdict(int)
        item_counts = defaultdict(int)
        
        for interaction in interactions:
            user_counts[interaction['user_id']] += 1
            item_counts[interaction['item_id']] += 1
        
        # Filter interactions
        filtered = [
            interaction for interaction in interactions
            if user_counts[interaction['user_id']] >= self.min_interactions_per_user
            and item_counts[interaction['item_id']] >= self.min_interactions_per_item
        ]
        
        logger.info(
            f"Filtered from {len(interactions)} to {len(filtered)} interactions. "
            f"Users: {len(user_counts)} -> {len(set(i['user_id'] for i in filtered))}, "
            f"Items: {len(item_counts)} -> {len(set(i['item_id'] for i in filtered))}"
        )
        
        return filtered
    
    def temporal_split(
        self, 
        interactions: List[Dict],
        test_ratio: float = 0.2
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        Split data temporally - earlier interactions for training, later for testing.
        
        Args:
            interactions: List of interaction dictionaries
            test_ratio: Ratio of data to use for testing
            
        Returns:
            Tuple of (train_interactions, test_interactions)
        """
        # Sort by timestamp
        sorted_interactions = sorted(interactions, key=lambda x: x['timestamp'])
        
        split_idx = int(len(sorted_interactions) * (1 - test_ratio))
        
        train = sorted_interactions[:split_idx]
        test = sorted_interactions[split_idx:]
        
        logger.info(f"Temporal split: {len(train)} train, {len(test)} test")
        return train, test
    
    def leave_one_out_split(
        self, 
        interactions: List[Dict]
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        Leave-one-out split - use last interaction per user for testing.
        
        Args:
            interactions: List of interaction dictionaries
            
        Returns:
            Tuple of (train_interactions, test_interactions)
        """
        # Group by user and sort by timestamp
        user_interactions = defaultdict(list)
        for interaction in interactions:
            user_interactions[interaction['user_id']].append(interaction)
        
        train = []
        test = []
        
        for user_id, user_ints in user_interactions.items():
            sorted_ints = sorted(user_ints, key=lambda x: x['timestamp'])
            
            if len(sorted_ints) >= 2:
                train.extend(sorted_ints[:-1])
                test.append(sorted_ints[-1])
            else:
                train.extend(sorted_ints)
        
        logger.info(f"Leave-one-out split: {len(train)} train, {len(test)} test")
        return train, test
    
    def build_user_item_matrix(
        self, 
        interactions: List[Dict]
    ) -> Tuple[np.ndarray, Dict, Dict]:
        """
        Build a user-item interaction matrix.
        
        Args:
            interactions: List of interaction dictionaries
            
        Returns:
            Tuple of (matrix, user_id_map, item_id_map)
        """
        # Create ID mappings
        unique_users = sorted(set(i['user_id'] for i in interactions))
        unique_items = sorted(set(i['item_id'] for i in interactions))
        
        user_id_map = {uid: idx for idx, uid in enumerate(unique_users)}
        item_id_map = {iid: idx for idx, iid in enumerate(unique_items)}
        
        # Build matrix
        matrix = np.zeros((len(unique_users), len(unique_items)))
        
        for interaction in interactions:
            user_idx = user_id_map[interaction['user_id']]
            item_idx = item_id_map[interaction['item_id']]
            matrix[user_idx, item_idx] = interaction['rating']
        
        logger.info(f"Built matrix of shape {matrix.shape}")
        return matrix, user_id_map, item_id_map
    
    def get_statistics(self, interactions: List[Dict]) -> Dict:
        """
        Calculate dataset statistics.
        
        Args:
            interactions: List of interaction dictionaries
            
        Returns:
            Dictionary of statistics
        """
        if not interactions:
            return {'error': 'No interactions'}
        
        ratings = [i['rating'] for i in interactions]
        unique_users = set(i['user_id'] for i in interactions)
        unique_items = set(i['item_id'] for i in interactions)
        
        return {
            'n_interactions': len(interactions),
            'n_users': len(unique_users),
            'n_items': len(unique_items),
            'sparsity': 1 - (len(interactions) / (len(unique_users) * len(unique_items))),
            'avg_rating': np.mean(ratings),
            'std_rating': np.std(ratings),
            'min_rating': np.min(ratings),
            'max_rating': np.max(ratings),
            'avg_interactions_per_user': len(interactions) / len(unique_users),
            'avg_interactions_per_item': len(interactions) / len(unique_items),
        }


# Singleton instance
_preprocessor_instance: Optional[DataPreprocessor] = None


def get_preprocessor() -> DataPreprocessor:
    """
    Get the singleton instance of the data preprocessor.
    
    Returns:
        DataPreprocessor instance
    """
    global _preprocessor_instance
    
    if _preprocessor_instance is None:
        _preprocessor_instance = DataPreprocessor()
    
    return _preprocessor_instance
