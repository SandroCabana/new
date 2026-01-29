"""
Ensemble Recommender that combines multiple recommendation models.
Uses weighted averaging with optional learned weights.
"""

import logging
from typing import List, Dict, Optional, Tuple
from pathlib import Path
import numpy as np
from collections import defaultdict

logger = logging.getLogger(__name__)


class EnsembleRecommender:
    """
    Ensemble that combines recommendations from multiple models.
    
    Strategies:
    - weighted_average: Weighted average of model scores
    - rank_fusion: Reciprocal Rank Fusion
    - voting: Majority voting
    """
    
    def __init__(
        self,
        strategy: str = 'weighted_average',
        weights: Optional[Dict[str, float]] = None
    ):
        self.strategy = strategy
        
        # Default weights based on evaluation performance
        self.weights = weights or {
            'hybrid': 0.25,
            'svd': 0.10,
            'ncf': 0.20,
            'sequential': 0.25,
            'fm': 0.20,
        }
        
        self.models = {}
        self._models_loaded = False
    
    def _load_models(self):
        """Lazy load all available models."""
        if self._models_loaded:
            return
        
        # Hybrid engine
        try:
            from lti_recommender_project.apps.recommendations.services.recommendation_engine import get_recommendation_engine
            hybrid = get_recommendation_engine()
            self.models['hybrid'] = {
                'get_recs': lambda uid, cid, limit: hybrid.get_recommendations(uid, cid, limit, exclude_viewed=True),
                'weight': self.weights.get('hybrid', 0.25)
            }
            logger.info("Loaded Hybrid model")
        except Exception as e:
            logger.warning(f"Could not load Hybrid model: {e}")
        
        # SVD
        try:
            from lti_recommender_project.ml.models.matrix_factorization import get_svd_model
            svd = get_svd_model()
            if svd._is_fitted:
                self.models['svd'] = {
                    'get_recs': svd.get_recommendations,
                    'weight': self.weights.get('svd', 0.10)
                }
                logger.info("Loaded SVD model")
        except Exception as e:
            logger.warning(f"Could not load SVD model: {e}")
        
        # NCF
        try:
            from lti_recommender_project.ml.models.neural_cf import get_ncf_model
            ncf = get_ncf_model()
            if ncf._is_fitted:
                self.models['ncf'] = {
                    'get_recs': ncf.get_recommendations,
                    'weight': self.weights.get('ncf', 0.20)
                }
                logger.info("Loaded NCF model")
        except Exception as e:
            logger.warning(f"Could not load NCF model: {e}")
        
        # Sequential
        try:
            from lti_recommender_project.ml.models.sequential_rec import get_sequential_model
            seq = get_sequential_model()
            if seq._is_fitted:
                self.models['sequential'] = {
                    'get_recs': seq.get_recommendations,
                    'weight': self.weights.get('sequential', 0.25)
                }
                logger.info("Loaded Sequential model")
        except Exception as e:
            logger.warning(f"Could not load Sequential model: {e}")
        
        # Factorization Machine
        try:
            from lti_recommender_project.ml.models.factorization_machine import get_fm_model
            fm = get_fm_model()
            if fm._is_fitted:
                self.models['fm'] = {
                    'get_recs': fm.get_recommendations,
                    'weight': self.weights.get('fm', 0.20)
                }
                logger.info("Loaded FM model")
        except Exception as e:
            logger.warning(f"Could not load FM model: {e}")
        
        self._models_loaded = True
        logger.info(f"Ensemble loaded {len(self.models)} models")
    
    def get_recommendations(
        self,
        user_id: str,
        context_id: str,
        limit: int = 10,
        exclude_viewed: bool = True
    ) -> List[Dict]:
        """
        Get ensemble recommendations combining all available models.
        """
        self._load_models()
        
        if not self.models:
            logger.warning("No models available for ensemble")
            return []
        
        if self.strategy == 'weighted_average':
            return self._weighted_average(user_id, context_id, limit)
        elif self.strategy == 'rank_fusion':
            return self._rank_fusion(user_id, context_id, limit)
        elif self.strategy == 'voting':
            return self._voting(user_id, context_id, limit)
        else:
            return self._weighted_average(user_id, context_id, limit)
    
    def _weighted_average(
        self,
        user_id: str,
        context_id: str,
        limit: int
    ) -> List[Dict]:
        """Combine recommendations using weighted average of scores."""
        
        # Collect scores from all models
        item_scores = defaultdict(lambda: {'total_weight': 0, 'weighted_score': 0, 'resource': None})
        
        for model_name, model_info in self.models.items():
            try:
                # Get extended recommendations
                recs = model_info['get_recs'](user_id, context_id, limit * 3)
                weight = model_info['weight']
                
                for rec in recs:
                    item_id = rec.get('id')
                    if item_id is None:
                        continue
                    
                    score = rec.get('score', 0)
                    
                    # Normalize score to 0-1 range (assuming 1-5 scale)
                    normalized_score = (score - 1) / 4 if isinstance(score, (int, float)) else 0.5
                    
                    item_scores[item_id]['weighted_score'] += weight * normalized_score
                    item_scores[item_id]['total_weight'] += weight
                    
                    if item_scores[item_id]['resource'] is None:
                        item_scores[item_id]['resource'] = rec
                        
            except Exception as e:
                logger.warning(f"Error getting recommendations from {model_name}: {e}")
                continue
        
        # Calculate final scores
        final_recommendations = []
        for item_id, data in item_scores.items():
            if data['total_weight'] > 0:
                final_score = data['weighted_score'] / data['total_weight']
                # Convert back to 1-5 scale
                rating_score = 1 + final_score * 4
                
                rec = data['resource'].copy()
                rec['score'] = rating_score
                rec['ensemble_weight'] = data['total_weight']
                rec['source'] = 'ensemble'
                final_recommendations.append(rec)
        
        # Sort by score
        final_recommendations.sort(key=lambda x: x['score'], reverse=True)
        
        return final_recommendations[:limit]
    
    def _rank_fusion(
        self,
        user_id: str,
        context_id: str,
        limit: int,
        k: int = 60
    ) -> List[Dict]:
        """
        Reciprocal Rank Fusion (RRF).
        
        RRF_score(d) = sum(1 / (k + rank_i(d)))
        """
        item_rrf_scores = defaultdict(lambda: {'rrf_score': 0, 'resource': None})
        
        for model_name, model_info in self.models.items():
            try:
                recs = model_info['get_recs'](user_id, context_id, limit * 2)
                
                for rank, rec in enumerate(recs, start=1):
                    item_id = rec.get('id')
                    if item_id is None:
                        continue
                    
                    # RRF score
                    rrf_contribution = 1.0 / (k + rank)
                    item_rrf_scores[item_id]['rrf_score'] += rrf_contribution
                    
                    if item_rrf_scores[item_id]['resource'] is None:
                        item_rrf_scores[item_id]['resource'] = rec
                        
            except Exception as e:
                logger.warning(f"Error in rank fusion for {model_name}: {e}")
                continue
        
        # Build final list
        final_recommendations = []
        for item_id, data in item_rrf_scores.items():
            rec = data['resource'].copy()
            rec['score'] = data['rrf_score'] * 100  # Scale for visibility
            rec['source'] = 'ensemble_rrf'
            final_recommendations.append(rec)
        
        final_recommendations.sort(key=lambda x: x['score'], reverse=True)
        
        return final_recommendations[:limit]
    
    def _voting(
        self,
        user_id: str,
        context_id: str,
        limit: int
    ) -> List[Dict]:
        """
        Majority voting - items appearing in more models rank higher.
        """
        item_votes = defaultdict(lambda: {'votes': 0, 'avg_rank': 0, 'rank_sum': 0, 'resource': None})
        
        for model_name, model_info in self.models.items():
            try:
                recs = model_info['get_recs'](user_id, context_id, limit)
                
                for rank, rec in enumerate(recs, start=1):
                    item_id = rec.get('id')
                    if item_id is None:
                        continue
                    
                    item_votes[item_id]['votes'] += 1
                    item_votes[item_id]['rank_sum'] += rank
                    
                    if item_votes[item_id]['resource'] is None:
                        item_votes[item_id]['resource'] = rec
                        
            except Exception as e:
                logger.warning(f"Error in voting for {model_name}: {e}")
                continue
        
        # Calculate average rank and sort
        for item_id, data in item_votes.items():
            data['avg_rank'] = data['rank_sum'] / data['votes']
        
        # Sort by votes (desc), then by avg_rank (asc)
        sorted_items = sorted(
            item_votes.items(),
            key=lambda x: (-x[1]['votes'], x[1]['avg_rank'])
        )
        
        final_recommendations = []
        for item_id, data in sorted_items[:limit]:
            rec = data['resource'].copy()
            rec['score'] = data['votes']
            rec['avg_rank'] = data['avg_rank']
            rec['source'] = 'ensemble_voting'
            final_recommendations.append(rec)
        
        return final_recommendations
    
    def set_weights(self, weights: Dict[str, float]):
        """Update model weights."""
        self.weights.update(weights)
        # Update loaded models
        for model_name in self.models:
            if model_name in weights:
                self.models[model_name]['weight'] = weights[model_name]
    
    def get_model_info(self) -> Dict:
        """Get information about loaded models."""
        self._load_models()
        return {
            'n_models': len(self.models),
            'models': list(self.models.keys()),
            'weights': {name: info['weight'] for name, info in self.models.items()},
            'strategy': self.strategy,
        }


# Singleton
_ensemble_instance: Optional[EnsembleRecommender] = None


def get_ensemble_recommender(strategy: str = 'weighted_average') -> EnsembleRecommender:
    """Get singleton ensemble recommender."""
    global _ensemble_instance
    
    if _ensemble_instance is None or _ensemble_instance.strategy != strategy:
        _ensemble_instance = EnsembleRecommender(strategy=strategy)
    
    return _ensemble_instance
