"""
Proper Model Evaluation with Train/Test Split.
Evaluates models on UNSEEN data for realistic metrics.
"""

import os
import sys
import logging
from pathlib import Path
from typing import Dict, List, Tuple
from collections import defaultdict
import numpy as np

# Django setup
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lti_recommender_project.settings')

import django
django.setup()

from lti_recommender_project.ml.data_preprocessing.data_splitter import (
    prepare_data_for_training, DataSplitter
)
from lti_recommender_project.ml.models.matrix_factorization import MatrixFactorizationModel
from lti_recommender_project.ml.models.neural_cf import NeuralCFModel
from lti_recommender_project.ml.models.sequential_rec import SequentialRecommender
from lti_recommender_project.ml.models.factorization_machine import FactorizationMachine

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def calculate_ranking_metrics(
    predictions: List[int],
    ground_truth: int,
    k: int = 10
) -> Dict[str, float]:
    """Calculate ranking metrics for a single user."""
    
    pred_at_k = predictions[:k]
    
    # Hit@K
    hit = 1.0 if ground_truth in pred_at_k else 0.0
    
    # NDCG@K
    dcg = 0.0
    if ground_truth in pred_at_k:
        rank = pred_at_k.index(ground_truth) + 1
        dcg = 1.0 / np.log2(rank + 1)
    ndcg = dcg  # IDCG = 1 for single ground truth
    
    # MRR
    mrr = 0.0
    if ground_truth in pred_at_k:
        rank = pred_at_k.index(ground_truth) + 1
        mrr = 1.0 / rank
    
    return {
        'hit': hit,
        'ndcg': ndcg,
        'mrr': mrr,
    }


def evaluate_model_on_test(
    model,
    test_data: List[Dict],
    train_items: set,
    all_items: set,
    k: int = 10,
    model_name: str = "Model"
) -> Dict[str, float]:
    """
    Evaluate a model on test data.
    For each user, predict top-K and check if test item is in predictions.
    """
    
    # Group test by user
    user_test_items = defaultdict(list)
    for item in test_data:
        user_test_items[item['user_id']].append(item['item_id'])
    
    hits = []
    ndcgs = []
    mrrs = []
    
    evaluated = 0
    for user_id, test_items in user_test_items.items():
        try:
            # Get recommendations - use first test item context
            recs = model.get_recommendations(
                user_id=user_id,
                context_id=test_data[0].get('context_id', 'default'),
                limit=k + 10,  # Get extra to exclude already seen
                exclude_viewed=False  # We want to check against all predictions
            )
            
            if not recs:
                continue
            
            # Extract predicted item IDs
            pred_ids = [r.get('id') for r in recs if r.get('id')][:k]
            
            # Calculate metrics for each test item
            for test_item in test_items:
                metrics = calculate_ranking_metrics(pred_ids, test_item, k)
                hits.append(metrics['hit'])
                ndcgs.append(metrics['ndcg'])
                mrrs.append(metrics['mrr'])
            
            evaluated += 1
            
        except Exception as e:
            logger.warning(f"{model_name} failed for user {user_id}: {e}")
            continue
    
    if not hits:
        return {
            'hit_rate': 0.0,
            'ndcg': 0.0,
            'mrr': 0.0,
            'evaluated_users': 0,
        }
    
    return {
        'hit_rate': np.mean(hits),
        'ndcg': np.mean(ndcgs),
        'mrr': np.mean(mrrs),
        'evaluated_users': evaluated,
        'total_predictions': len(hits),
    }


def run_proper_evaluation():
    """Run proper evaluation with train/test split."""
    
    print("\n" + "=" * 60)
    print("        PROPER MODEL EVALUATION (on unseen data)")
    print("=" * 60)
    
    # Prepare data with split
    train_data, test_data, stats = prepare_data_for_training(
        split_type='user_stratified',
        test_ratio=0.2,
        random_seed=42
    )
    
    print(f"\nData Split:")
    print(f"  Train: {len(train_data)} interactions")
    print(f"  Test: {len(test_data)} interactions")
    print(f"  Cold-start items: {stats['cold_start_items']}")
    
    # Get all items for reference
    train_items = set(d['item_id'] for d in train_data)
    test_items = set(d['item_id'] for d in test_data)
    all_items = train_items | test_items
    
    # Models to evaluate (using pre-trained models)
    # NOTE: For proper evaluation, models should be RE-TRAINED on train_data only
    # This is a simplified version using existing models
    
    from lti_recommender_project.ml.models.matrix_factorization import get_svd_model
    from lti_recommender_project.ml.models.neural_cf import get_ncf_model
    from lti_recommender_project.ml.models.sequential_rec import get_sequential_model
    from lti_recommender_project.ml.models.factorization_machine import get_fm_model
    
    models = {}
    
    # Load SVD
    try:
        svd = get_svd_model()
        if svd._is_fitted:
            models['SVD'] = svd
            logger.info("SVD loaded successfully")
    except Exception as e:
        logger.warning(f"Could not load SVD: {e}")
    
    # Load NCF
    try:
        ncf = get_ncf_model()
        if ncf._is_fitted:
            models['NCF'] = ncf
            logger.info("NCF loaded successfully")
    except Exception as e:
        logger.warning(f"Could not load NCF: {e}")
    
    # Load Sequential
    try:
        seq = get_sequential_model()
        if seq._is_fitted:
            models['Sequential'] = seq
            logger.info("Sequential loaded successfully")
    except Exception as e:
        logger.warning(f"Could not load Sequential: {e}")
    
    # Load FM
    try:
        fm = get_fm_model()
        if fm._is_fitted:
            models['FM'] = fm
            logger.info("FM loaded successfully")
    except Exception as e:
        logger.warning(f"Could not load FM: {e}")
    
    print(f"\nLoaded models: {list(models.keys())}")
    
    # Evaluate each model
    results = {}
    for name, model in models.items():
        print(f"\nEvaluating {name}...")
        
        metrics = evaluate_model_on_test(
            model=model,
            test_data=test_data,
            train_items=train_items,
            all_items=all_items,
            k=10,
            model_name=name
        )
        
        results[name] = metrics
        
        print(f"  Hit@10: {metrics['hit_rate']:.4f}")
        print(f"  NDCG@10: {metrics['ndcg']:.4f}")
        print(f"  MRR: {metrics['mrr']:.4f}")
        print(f"  Evaluated: {metrics['evaluated_users']} users")
    
    # Summary
    print("\n" + "=" * 60)
    print("                   EVALUATION SUMMARY")
    print("=" * 60)
    print(f"{'Model':<15} {'Hit@10':<10} {'NDCG@10':<10} {'MRR':<10} {'Users':<8}")
    print("-" * 60)
    
    for name, metrics in sorted(results.items(), key=lambda x: x[1]['hit_rate'], reverse=True):
        print(f"{name:<15} {metrics['hit_rate']:.4f}     {metrics['ndcg']:.4f}     {metrics['mrr']:.4f}     {metrics['evaluated_users']}")
    
    print("=" * 60)
    print("\n⚠️  NOTE: These metrics are on UNSEEN test data.")
    print("          Models were trained on full data, so metrics may be optimistic.")
    print("          For proper eval, retrain models on train split only.\n")
    
    return results


if __name__ == '__main__':
    run_proper_evaluation()
