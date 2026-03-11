"""
Comprehensive model evaluation module.
Supports multiple models and extended metrics.
"""

import os
import sys
import logging
import math
import numpy as np
from typing import List, Dict, Callable, Optional, Tuple
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# Add parent of lti_recommender_project to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lti_recommender_project.settings')

import django
django.setup()

from django.db import transaction
from django.db.models import Count, Q

from lti_recommender_project.apps.interactions.models import UserInteraction
from lti_recommender_project.apps.resources.models import EducationalResource

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ModelEvaluator:
    """
    Evaluates recommendation models with comprehensive metrics.
    """
    
    def __init__(self, k: int = 5, test_ratio: float = 0.2, min_interactions: int = 5, max_users: int = 100):
        """
        Initialize evaluator.
        
        Args:
            k: Number of recommendations to evaluate
            test_ratio: Ratio of interactions to use for testing
            min_interactions: Minimum interactions per user for evaluation
            max_users: Maximum number of users to evaluate (to prevent excessive resource usage)
        """
        self.k = k
        self.test_ratio = test_ratio
        self.min_interactions = min_interactions
        self.max_users = max_users
    
    def evaluate_model(
        self, 
        get_recommendations: Callable[[str, str, int], List[Dict]],
        model_name: str = "Model"
    ) -> Dict:
        """
        Evaluate a recommendation model.
        
        Args:
            get_recommendations: Function that takes (user_id, context_id, limit) 
                                and returns list of recommendations
            model_name: Name of the model for reporting
            
        Returns:
            Dictionary with evaluation metrics
        """
        logger.info(f"Evaluating {model_name}...")
        
        # Get users with enough interactions
        users = list(UserInteraction.objects.values('lti_user_id').annotate(
            count=Count('id')
        ).filter(count__gte=self.min_interactions).order_by('?')[:self.max_users].values_list('lti_user_id', flat=True))
        
        if not users:
            logger.warning(f"No users with {self.min_interactions}+ interactions")
            return {'error': 'Insufficient data'}
        
        # Metrics accumulators
        precisions = []
        recalls = []
        ndcgs = []
        mrrs = []
        hit_rates = []
        all_recommended_ids = set()
        
        for user_id in users:
            metrics = self._evaluate_user(user_id, get_recommendations)
            if metrics:
                precisions.append(metrics['precision'])
                recalls.append(metrics['recall'])
                ndcgs.append(metrics['ndcg'])
                mrrs.append(metrics['mrr'])
                hit_rates.append(metrics['hit'])
                all_recommended_ids.update(metrics['recommended_ids'])
        
        # Aggregate metrics
        total_resources = EducationalResource.objects.count()
        
        results = {
            'model': model_name,
            'k': self.k,
            'n_users_evaluated': len(precisions),
            'precision_at_k': np.mean(precisions) if precisions else 0,
            'recall_at_k': np.mean(recalls) if recalls else 0,
            'f1_score': self._f1(np.mean(precisions), np.mean(recalls)) if precisions else 0,
            'ndcg_at_k': np.mean(ndcgs) if ndcgs else 0,
            'mrr': np.mean(mrrs) if mrrs else 0,
            'hit_rate': np.mean(hit_rates) if hit_rates else 0,
            'coverage': len(all_recommended_ids) / total_resources if total_resources > 0 else 0,
            'unique_items_recommended': len(all_recommended_ids),
            'total_items': total_resources,
        }
        
        # Calculate MAP@K
        results['map_at_k'] = self._calculate_map(users, get_recommendations)
        
        return results
    
    def _evaluate_user(
        self, 
        user_id: str, 
        get_recommendations: Callable
    ) -> Optional[Dict]:
        """Evaluate recommendations for a single user."""
        
        # Get user interactions sorted by time
        interactions = list(UserInteraction.objects.filter(
            lti_user_id=user_id
        ).order_by('timestamp'))
        
        if len(interactions) < self.min_interactions:
            return None
        
        # Split into train/test
        split_idx = int(len(interactions) * (1 - self.test_ratio))
        train_set = interactions[:split_idx]
        test_set = interactions[split_idx:]
        
        if not test_set or not train_set:
            return None
        
        test_resource_ids = {i.resource_id for i in test_set}
        context_id = train_set[0].lti_context_id if train_set else interactions[0].lti_context_id
        
        try:
            with transaction.atomic():
                # Temporarily remove test interactions
                for i in test_set:
                    i.delete()
                
                # Get recommendations
                recs = get_recommendations(user_id, context_id, self.k)
                
                # Extract recommended IDs
                rec_ids = []
                for r in recs:
                    if isinstance(r, dict):
                        rec_ids.append(r.get('id') or r.get('resource', {}).get('id') or 
                                       (r['resource'].id if hasattr(r.get('resource'), 'id') else None))
                    else:
                        rec_ids.append(r.id if hasattr(r, 'id') else r)
                rec_ids = [rid for rid in rec_ids if rid is not None]
                
                # Calculate metrics
                hits = sum(1 for rid in rec_ids if rid in test_resource_ids)
                
                # Precision & Recall
                precision = hits / self.k if self.k > 0 else 0
                recall = hits / len(test_resource_ids) if test_resource_ids else 0
                
                # NDCG
                dcg = sum(
                    (1 if rid in test_resource_ids else 0) / math.log2(i + 2)
                    for i, rid in enumerate(rec_ids)
                )
                ideal_hits = min(len(test_resource_ids), self.k)
                idcg = sum(1 / math.log2(i + 2) for i in range(ideal_hits))
                ndcg = dcg / idcg if idcg > 0 else 0
                
                # MRR
                mrr = 0
                for i, rid in enumerate(rec_ids):
                    if rid in test_resource_ids:
                        mrr = 1 / (i + 1)
                        break
                
                # Hit (at least one relevant item)
                hit = 1 if hits > 0 else 0
                
                # Force rollback
                raise ValueError("Rollback")
                
        except ValueError as e:
            if str(e) == "Rollback":
                return {
                    'precision': precision,
                    'recall': recall,
                    'ndcg': ndcg,
                    'mrr': mrr,
                    'hit': hit,
                    'recommended_ids': set(rec_ids),
                }
            raise
        
        return None
    
    def _calculate_map(
        self, 
        users: List[str], 
        get_recommendations: Callable
    ) -> float:
        """Calculate Mean Average Precision."""
        aps = []
        
        for user_id in users[:20]:  # Sample for efficiency
            interactions = list(UserInteraction.objects.filter(
                lti_user_id=user_id
            ).order_by('timestamp'))
            
            if len(interactions) < self.min_interactions:
                continue
            
            split_idx = int(len(interactions) * (1 - self.test_ratio))
            test_set = interactions[split_idx:]
            test_ids = {i.resource_id for i in test_set}
            context_id = interactions[0].lti_context_id
            
            try:
                recs = get_recommendations(user_id, context_id, self.k)
                rec_ids = [r.get('id') or r['resource'].id if isinstance(r, dict) else r.id 
                          for r in recs if r]
                
                # Calculate AP
                hits = 0
                precision_sum = 0
                for i, rid in enumerate(rec_ids):
                    if rid in test_ids:
                        hits += 1
                        precision_sum += hits / (i + 1)
                
                ap = precision_sum / min(len(test_ids), self.k) if test_ids else 0
                aps.append(ap)
            except Exception:
                continue
        
        return np.mean(aps) if aps else 0
    
    def _f1(self, precision: float, recall: float) -> float:
        """Calculate F1 score."""
        if precision + recall == 0:
            return 0
        return 2 * (precision * recall) / (precision + recall)
    
    def compare_models(self, models: List[Tuple[str, Callable]]) -> Dict:
        """
        Compare multiple models.
        
        Args:
            models: List of (model_name, get_recommendations_func) tuples
            
        Returns:
            Dictionary with comparison results
        """
        results = {}
        for name, func in models:
            results[name] = self.evaluate_model(func, name)
        return results
    
    def print_report(self, results: Dict):
        """Print evaluation report."""
        print("\n" + "=" * 60)
        print(f"         MODEL EVALUATION REPORT - {results.get('model', 'Unknown')}")
        print("=" * 60)
        print(f"Users Evaluated: {results.get('n_users_evaluated', 0)}")
        print(f"K (recommendations): {results.get('k', 5)}")
        print("-" * 60)
        
        metrics = [
            ('Precision@K', 'precision_at_k'),
            ('Recall@K', 'recall_at_k'),
            ('F1 Score', 'f1_score'),
            ('NDCG@K', 'ndcg_at_k'),
            ('MAP@K', 'map_at_k'),
            ('MRR', 'mrr'),
            ('Hit Rate', 'hit_rate'),
            ('Coverage', 'coverage'),
        ]
        
        for label, key in metrics:
            value = results.get(key, 0)
            if key == 'coverage':
                print(f"• {label}: {value:.2%}")
            else:
                print(f"• {label}: {value:.4f}")
        
        print(f"\nUnique Items Recommended: {results.get('unique_items_recommended', 0)} / {results.get('total_items', 0)}")
        print("=" * 60)


def evaluate_all_models():
    """Evaluate all available recommendation models."""
    
    evaluator = ModelEvaluator(k=5, test_ratio=0.2, min_interactions=5)
    
    all_results = {}
    
    # Import recommendation engines
    from lti_recommender_project.apps.recommendations.services.recommendation_engine import get_recommendation_engine
    
    # 1. Hybrid engine
    print("\n" + "=" * 60)
    print("                EVALUATING ALL MODELS")
    print("=" * 60)
    
    hybrid_engine = get_recommendation_engine()
    
    def hybrid_get_recs(user_id, context_id, limit):
        return hybrid_engine.get_recommendations(user_id, context_id, limit, exclude_viewed=True)
    
    hybrid_results = evaluator.evaluate_model(hybrid_get_recs, "Hybrid (Content+User+Popularity)")
    evaluator.print_report(hybrid_results)
    all_results['Hybrid'] = hybrid_results
    
    # 2. SVD model
    try:
        from lti_recommender_project.ml.models.matrix_factorization import get_svd_model
        svd_model = get_svd_model()
        
        if svd_model._is_fitted:
            svd_results = evaluator.evaluate_model(
                svd_model.get_recommendations, 
                "SVD Matrix Factorization"
            )
            evaluator.print_report(svd_results)
            all_results['SVD'] = svd_results
    except Exception as e:
        logger.info(f"SVD model not available: {e}")
    
    # 3. NCF model
    try:
        from lti_recommender_project.ml.models.neural_cf import get_ncf_model
        ncf_model = get_ncf_model()
        
        if ncf_model._is_fitted:
            ncf_results = evaluator.evaluate_model(
                ncf_model.get_recommendations,
                "Neural Collaborative Filtering"
            )
            evaluator.print_report(ncf_results)
            all_results['NCF'] = ncf_results
    except Exception as e:
        logger.info(f"NCF model not available: {e}")
    
    # 4. Sequential model
    try:
        from lti_recommender_project.ml.models.sequential_rec import get_sequential_model
        seq_model = get_sequential_model()
        
        if seq_model._is_fitted:
            seq_results = evaluator.evaluate_model(
                seq_model.get_recommendations,
                "Sequential (GRU4Rec)"
            )
            evaluator.print_report(seq_results)
            all_results['Sequential'] = seq_results
    except Exception as e:
        logger.info(f"Sequential model not available: {e}")
    
    # 5. Factorization Machine
    try:
        from lti_recommender_project.ml.models.factorization_machine import get_fm_model
        fm_model = get_fm_model()
        
        if fm_model._is_fitted:
            fm_results = evaluator.evaluate_model(
                fm_model.get_recommendations,
                "Factorization Machine"
            )
            evaluator.print_report(fm_results)
            all_results['FM'] = fm_results
    except Exception as e:
        logger.info(f"FM model not available: {e}")
    
    # 6. Ensemble model
    try:
        from lti_recommender_project.ml.models.ensemble import get_ensemble_recommender
        ensemble = get_ensemble_recommender(strategy='weighted_average')
        
        ensemble_results = evaluator.evaluate_model(
            ensemble.get_recommendations,
            "Ensemble (Weighted Average)"
        )
        evaluator.print_report(ensemble_results)
        all_results['Ensemble'] = ensemble_results
    except Exception as e:
        logger.info(f"Ensemble model not available: {e}")
    
    # Print comparison summary
    print("\n" + "=" * 60)
    print("                 COMPARISON SUMMARY")
    print("=" * 60)
    print(f"{'Model':<30} {'Precision@5':<12} {'F1':<10} {'NDCG@5':<10}")
    print("-" * 60)
    for name, results in all_results.items():
        if 'error' not in results:
            print(f"{name:<30} {results['precision_at_k']:.4f}       {results['f1_score']:.4f}     {results['ndcg_at_k']:.4f}")
    print("=" * 60)
    
    return all_results


if __name__ == '__main__':
    evaluate_all_models()


