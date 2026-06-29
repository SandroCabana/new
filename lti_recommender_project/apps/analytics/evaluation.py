"""
Evaluación Offline de Sistemas de Recomendación.

Métricas estándar: Precision@K, Recall@K, NDCG@K, MRR, Hit@K.
Split temporal para evaluar como en producción real.
A/B Testing con asignación determinística.

Referente: Netflix Prize (NDCG@K), Spotify (temporal split).
"""
import numpy as np
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


# ============================================================================
# METRIC FUNCTIONS
# ============================================================================

def precision_at_k(recommended: List[int], relevant: List[int], k: int) -> float:
    """Precision@K: fracción de los top-K recomendados que son relevantes."""
    if k <= 0 or not recommended:
        return 0.0
    top_k = set(recommended[:k])
    relevant_set = set(relevant)
    return len(top_k & relevant_set) / k


def recall_at_k(recommended: List[int], relevant: List[int], k: int) -> float:
    """Recall@K: fracción de los relevantes que aparecen en top-K."""
    if not relevant or not recommended:
        return 0.0
    top_k = set(recommended[:k])
    relevant_set = set(relevant)
    return len(top_k & relevant_set) / len(relevant_set)


def ndcg_at_k(recommended: List[int], relevant: List[int], k: int) -> float:
    """
    NDCG@K: Normalized Discounted Cumulative Gain.
    Considera la posición — un ítem relevante en posición 1 vale más que en K.
    Métrica gold standard para sistemas de recomendación (Netflix Prize).
    """
    if not relevant or not recommended:
        return 0.0

    relevant_set = set(relevant)

    def dcg(items: List[int], k: int) -> float:
        score = 0.0
        for i, item in enumerate(items[:k]):
            if item in relevant_set:
                score += 1.0 / np.log2(i + 2)  # i+2 porque log2(1)=0
        return score

    actual_dcg = dcg(recommended, k)
    # Ideal: todos los relevantes primero
    ideal_items = list(relevant_set)[:k]
    ideal_dcg = dcg(ideal_items, k)

    return actual_dcg / ideal_dcg if ideal_dcg > 0 else 0.0


def mean_reciprocal_rank(recommended: List[int], relevant: List[int]) -> float:
    """MRR: posición del primer ítem relevante en la lista."""
    relevant_set = set(relevant)
    for i, item in enumerate(recommended):
        if item in relevant_set:
            return 1.0 / (i + 1)
    return 0.0


def hit_at_k(recommended: List[int], relevant: List[int], k: int) -> float:
    """Hit@K: 1 si al menos un ítem relevante está en top-K, 0 si no."""
    top_k = set(recommended[:k])
    return 1.0 if any(r in top_k for r in relevant) else 0.0


# ============================================================================
# OFFLINE EVALUATOR
# ============================================================================

class OfflineEvaluator:
    """
    Evaluador offline con split temporal estratificado.
    
    Split temporal: entrena con datos pasados, evalúa en datos futuros.
    Simula el entorno real de producción.
    Un ítem es 'relevante' si el usuario lo completó >50%.
    """

    def evaluate_model(
        self,
        model,
        test_ratio: float = 0.2,
        k_values: List[int] = [5, 10],
        min_completion: float = 50.0,
    ) -> Dict:
        """
        Evaluación offline con split temporal.
        
        Args:
            model: objeto con método get_recommendations(user_id, context_id, limit)
            test_ratio: fracción de datos para test (últimas interacciones)
            k_values: valores de K para Precision@K y NDCG@K
            min_completion: completion_percentage mínimo para considerar relevante
        """
        from lti_recommender_project.apps.interactions.models import UserInteraction

        interactions = list(
            UserInteraction.objects.order_by('timestamp').values(
                'lti_user_id', 'resource_id', 'timestamp', 'completion_percentage', 'lti_context_id'
            )
        )

        if len(interactions) < 10:
            logger.warning("Insufficient data for evaluation (< 10 interactions)")
            return {'error': 'insufficient_data', 'count': len(interactions)}

        # Split temporal
        split_idx = int(len(interactions) * (1 - test_ratio))
        train_set = interactions[:split_idx]
        test_set = interactions[split_idx:]

        # Build train history for filtering
        user_train = {}
        for i in train_set:
            uid = i['lti_user_id']
            if uid not in user_train:
                user_train[uid] = set()
            user_train[uid].add(i['resource_id'])

        # Group test interactions by user
        user_test: Dict[str, Dict] = {}
        for i in test_set:
            uid = i['lti_user_id']
            if uid not in user_test:
                user_test[uid] = {'relevant': [], 'context_id': i['lti_context_id']}
            if (i['completion_percentage'] or 0) >= min_completion:
                user_test[uid]['relevant'].append(i['resource_id'])

        max_k = max(k_values)
        metrics: Dict[str, List] = {f'precision@{k}': [] for k in k_values}
        metrics.update({f'recall@{k}': [] for k in k_values})
        metrics.update({f'ndcg@{k}': [] for k in k_values})
        metrics.update({f'hit@{k}': [] for k in k_values})
        metrics['mrr'] = []
        users_evaluated = 0

        for user_id, data in user_test.items():
            relevant = data['relevant']
            context_id = data['context_id']
            train_ids = user_train.get(user_id, set())

            if not relevant:
                continue

            try:
                # Disable exclude_viewed so the model can recommend the test items
                # We request more items to compensate for the ones we'll filter out
                recs = model.get_recommendations(user_id, context_id, limit=max_k * 5, exclude_viewed=False)
                
                # Exclude items the user saw during training, keep test items
                rec_ids = []
                for r in recs:
                    if 'id' in r and r['id'] not in train_ids:
                        rec_ids.append(r['id'])
                
                # Take only the top max_k after filtering
                rec_ids = rec_ids[:max_k]

                for k in k_values:
                    metrics[f'precision@{k}'].append(precision_at_k(rec_ids, relevant, k))
                    metrics[f'recall@{k}'].append(recall_at_k(rec_ids, relevant, k))
                    metrics[f'ndcg@{k}'].append(ndcg_at_k(rec_ids, relevant, k))
                    metrics[f'hit@{k}'].append(hit_at_k(rec_ids, relevant, k))

                metrics['mrr'].append(mean_reciprocal_rank(rec_ids, relevant))
                users_evaluated += 1

            except Exception as e:
                logger.debug(f"Evaluation failed for user {user_id}: {e}")
                continue

        if users_evaluated == 0:
            return {'error': 'no_users_evaluated'}

        return {
            'users_evaluated': users_evaluated,
            'test_interactions': len(test_set),
            'split_ratio': test_ratio,
            **{k: float(np.mean(v)) if v else 0.0 for k, v in metrics.items()},
        }

    def compare_models(self, models: Dict, k_values: List[int] = [5, 10]) -> Dict:
        """Evalúa múltiples modelos y retorna comparación."""
        results = {}
        for name, model in models.items():
            logger.info(f"Evaluating model: {name}")
            results[name] = self.evaluate_model(model, k_values=k_values)
        return results


# ============================================================================
# A/B TEST MANAGER
# ============================================================================

class ABTestManager:
    """
    A/B Testing entre estrategias de recomendación.
    Asignación determinística por hash del user_id (misma variante siempre).
    
    Variante A: weighted_average (control actual)
    Variante B: rank_fusion (Reciprocal Rank Fusion)
    """

    VARIANTS = {
        'A': {'strategy': 'weighted_average', 'description': 'Promedio ponderado (control)'},
        'B': {'strategy': 'rank_fusion', 'description': 'Reciprocal Rank Fusion (tratamiento)'},
    }

    @staticmethod
    def get_variant(user_id: str) -> str:
        """Asignación determinística — mismo user_id siempre → misma variante."""
        import hashlib
        hash_val = int(hashlib.md5(user_id.encode()).hexdigest(), 16)
        return 'A' if hash_val % 2 == 0 else 'B'

    @classmethod
    def get_strategy_for_user(cls, user_id: str) -> str:
        """Retorna la estrategia de ensemble asignada al usuario."""
        variant = cls.get_variant(user_id)
        return cls.VARIANTS[variant]['strategy']

    @classmethod
    def get_variant_stats(cls) -> Dict:
        """Estadísticas del A/B test basadas en interacciones recientes."""
        from lti_recommender_project.apps.interactions.models import UserInteraction
        from django.db.models import Avg, Count

        users = UserInteraction.objects.values('lti_user_id').distinct()
        stats = {'A': {'users': 0, 'avg_completion': 0}, 'B': {'users': 0, 'avg_completion': 0}}

        for user in users:
            uid = user['lti_user_id']
            variant = cls.get_variant(uid)
            stats[variant]['users'] += 1

        return {
            'total_users': sum(v['users'] for v in stats.values()),
            'variants': stats,
            'variant_descriptions': {k: v['description'] for k, v in cls.VARIANTS.items()},
        }
