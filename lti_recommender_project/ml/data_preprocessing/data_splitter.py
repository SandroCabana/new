"""
Data Splitter for Recommendation System.
Provides proper train/test split strategies for different model types.
"""

import random
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class DataSplitter:
    """
    Splits interaction data for proper model evaluation.
    
    Strategies:
    - user_stratified: 80/20 split per user (for CF models)
    - temporal: last N% of events per user (for sequential models)
    - leave_one_out: last item per user for test (for ranking eval)
    """
    
    def __init__(self, interactions: List[Dict], random_seed: int = 42):
        """
        Args:
            interactions: List of dicts with keys: user_id, item_id, rating, timestamp
            random_seed: For reproducibility
        """
        self.interactions = interactions
        self.random_seed = random_seed
        random.seed(random_seed)
        
        # Group by user
        self.user_interactions = defaultdict(list)
        for i, interaction in enumerate(interactions):
            self.user_interactions[interaction['user_id']].append((i, interaction))
        
        logger.info(f"DataSplitter initialized: {len(interactions)} interactions, {len(self.user_interactions)} users")
    
    def user_stratified_split(
        self,
        test_ratio: float = 0.2,
        min_train_per_user: int = 1
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        Split by percentage per user (for SVD, NCF, FM).
        Ensures each user has at least min_train_per_user in training.
        
        Returns:
            (train_data, test_data)
        """
        train_data = []
        test_data = []
        
        for user_id, user_items in self.user_interactions.items():
            n_items = len(user_items)
            
            if n_items <= min_train_per_user:
                # All goes to training
                train_data.extend([item for _, item in user_items])
                continue
            
            # Shuffle user's interactions
            shuffled = list(user_items)
            random.shuffle(shuffled)
            
            # Calculate split point
            n_test = max(1, int(n_items * test_ratio))
            n_train = n_items - n_test
            
            # Ensure minimum training items
            if n_train < min_train_per_user:
                n_train = min_train_per_user
                n_test = n_items - n_train
            
            train_data.extend([item for _, item in shuffled[:n_train]])
            test_data.extend([item for _, item in shuffled[n_train:]])
        
        logger.info(f"User-stratified split: train={len(train_data)}, test={len(test_data)}")
        return train_data, test_data
    
    def temporal_split(
        self,
        test_ratio: float = 0.2,
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        Split by time within each user (for Sequential models).
        Earlier events → train, later events → test.
        
        Returns:
            (train_data, test_data)
        """
        train_data = []
        test_data = []
        
        for user_id, user_items in self.user_interactions.items():
            # Sort by timestamp
            sorted_items = sorted(user_items, key=lambda x: x[1].get('timestamp', 0))
            n_items = len(sorted_items)
            
            if n_items <= 1:
                train_data.extend([item for _, item in sorted_items])
                continue
            
            # Split point
            n_test = max(1, int(n_items * test_ratio))
            n_train = n_items - n_test
            
            train_data.extend([item for _, item in sorted_items[:n_train]])
            test_data.extend([item for _, item in sorted_items[n_train:]])
        
        logger.info(f"Temporal split: train={len(train_data)}, test={len(test_data)}")
        return train_data, test_data
    
    def leave_one_out_split(self) -> Tuple[List[Dict], List[Dict]]:
        """
        Leave-one-out split: last interaction per user goes to test.
        Used for ranking evaluation (Hit@K, NDCG).
        
        Returns:
            (train_data, test_data)
        """
        train_data = []
        test_data = []
        
        for user_id, user_items in self.user_interactions.items():
            if len(user_items) <= 1:
                train_data.extend([item for _, item in user_items])
                continue
            
            # Sort by timestamp
            sorted_items = sorted(user_items, key=lambda x: x[1].get('timestamp', 0))
            
            # Last item to test
            train_data.extend([item for _, item in sorted_items[:-1]])
            test_data.append(sorted_items[-1][1])
        
        logger.info(f"Leave-one-out split: train={len(train_data)}, test={len(test_data)}")
        return train_data, test_data
    
    def get_negative_samples(
        self,
        user_id: str,
        n_samples: int = 99,
        all_items: Optional[set] = None
    ) -> List[str]:
        """
        Get negative samples for a user (items they haven't interacted with).
        Used for ranking evaluation with BPR/NCE loss.
        
        Args:
            user_id: User to get negatives for
            n_samples: Number of negative samples
            all_items: Set of all item IDs (calculated if not provided)
        
        Returns:
            List of item IDs the user hasn't interacted with
        """
        if all_items is None:
            all_items = set(i['item_id'] for i in self.interactions)
        
        user_items = set(i['item_id'] for _, i in self.user_interactions.get(user_id, []))
        available = list(all_items - user_items)
        
        if len(available) <= n_samples:
            return available
        
        return random.sample(available, n_samples)


def prepare_data_for_training(
    split_type: str = 'user_stratified',
    test_ratio: float = 0.2,
    random_seed: int = 42
) -> Tuple[List[Dict], List[Dict], Dict]:
    """
    Main function to prepare train/test data from Django models.
    
    Args:
        split_type: 'user_stratified', 'temporal', or 'leave_one_out'
        test_ratio: Fraction for test set
        random_seed: For reproducibility
    
    Returns:
        (train_data, test_data, stats)
    """
    # Import Django models
    import os
    import sys
    from pathlib import Path
    
    PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
    sys.path.insert(0, str(PROJECT_ROOT))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lti_recommender_project.settings')
    
    import django
    django.setup()
    
    from lti_recommender_project.apps.interactions.models import UserInteraction
    from lti_recommender_project.apps.resources.models import EducationalResource
    
    # Extract interactions
    interactions = []
    for ui in UserInteraction.objects.select_related('resource').all():
        rating = ui.rating if ui.rating else 3  # Default rating
        if ui.completion_percentage:
            # Use completion as implicit rating if no explicit rating
            rating = max(1, min(5, int(ui.completion_percentage / 20)))
        
        interactions.append({
            'user_id': ui.lti_user_id,
            'item_id': ui.resource.id,
            'rating': rating,
            'timestamp': ui.timestamp.timestamp() if ui.timestamp else 0,
            'context_id': ui.lti_context_id,
        })
    
    # Create splitter
    splitter = DataSplitter(interactions, random_seed)
    
    # Split based on type
    if split_type == 'temporal':
        train_data, test_data = splitter.temporal_split(test_ratio)
    elif split_type == 'leave_one_out':
        train_data, test_data = splitter.leave_one_out_split()
    else:
        train_data, test_data = splitter.user_stratified_split(test_ratio)
    
    # Calculate stats
    train_users = set(d['user_id'] for d in train_data)
    test_users = set(d['user_id'] for d in test_data)
    train_items = set(d['item_id'] for d in train_data)
    test_items = set(d['item_id'] for d in test_data)
    
    stats = {
        'total_interactions': len(interactions),
        'train_interactions': len(train_data),
        'test_interactions': len(test_data),
        'train_users': len(train_users),
        'test_users': len(test_users),
        'train_items': len(train_items),
        'test_items': len(test_items),
        'cold_start_users': len(test_users - train_users),
        'cold_start_items': len(test_items - train_items),
        'split_type': split_type,
        'test_ratio': test_ratio,
    }
    
    logger.info(f"Data prepared: {stats}")
    
    return train_data, test_data, stats


if __name__ == '__main__':
    # Test the splitter
    logging.basicConfig(level=logging.INFO)
    
    train, test, stats = prepare_data_for_training(
        split_type='user_stratified',
        test_ratio=0.2
    )
    
    print("\n" + "=" * 50)
    print("DATA SPLIT STATISTICS")
    print("=" * 50)
    for key, value in stats.items():
        print(f"  {key}: {value}")
    print("=" * 50)
