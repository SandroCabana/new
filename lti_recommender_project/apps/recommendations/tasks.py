"""
Celery Tasks para el motor de recomendaciones.

Tareas programadas:
  - retrain_all_models   → nightly 2am
  - update_embeddings    → hourly
  - precompute_active_users → every 30min
  - run_scraper_task     → nightly 3am
"""
import logging
from celery import shared_task
from django.conf import settings

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=120,
    name='lti_recommender_project.apps.recommendations.tasks.retrain_all_models',
    queue='ml_training',
)
def retrain_all_models(self):
    """
    Reentrenar todos los modelos ML con los datos más recientes.
    Ejecutado nightly a las 2am UTC via Celery Beat.
    """
    results = {}

    # SVD
    try:
        from lti_recommender_project.ml.models.matrix_factorization import MatrixFactorizationModel
        svd = MatrixFactorizationModel()
        metrics = svd.fit(save_model=True)
        results['svd'] = {'status': 'ok', 'metrics': metrics}
        logger.info(f"SVD retrained: RMSE={metrics.get('rmse_mean', 'N/A'):.4f}")
    except Exception as e:
        logger.error(f"SVD retrain failed: {e}")
        results['svd'] = {'status': 'error', 'error': str(e)}

    # NCF
    try:
        from lti_recommender_project.ml.models.neural_cf import NeuralCFModel
        ncf = NeuralCFModel()
        metrics = ncf.fit(save_model=True)
        results['ncf'] = {'status': 'ok', 'metrics': metrics}
        logger.info(f"NCF retrained")
    except Exception as e:
        logger.error(f"NCF retrain failed: {e}")
        results['ncf'] = {'status': 'error', 'error': str(e)}

    # Sequential
    try:
        from lti_recommender_project.ml.models.sequential_rec import SequentialRecommender
        seq = SequentialRecommender()
        metrics = seq.fit(save_model=True)
        results['sequential'] = {'status': 'ok', 'metrics': metrics}
        logger.info(f"Sequential model retrained")
    except Exception as e:
        logger.error(f"Sequential retrain failed: {e}")
        results['sequential'] = {'status': 'error', 'error': str(e)}

    # Auto-adjust ensemble weights based on training results
    try:
        from lti_recommender_project.ml.models.ensemble import get_ensemble_recommender
        ensemble = get_ensemble_recommender()
        new_weights = ensemble.auto_adjust_weights(results)
        results['ensemble_weights'] = new_weights
        logger.info(f"Ensemble weights auto-adjusted: {new_weights}")
    except Exception as e:
        logger.error(f"Ensemble weight adjustment failed: {e}")

    # ---- Persist training metrics to DB ----
    try:
        from lti_recommender_project.apps.analytics.models import ModelEvaluationResult
        from django.utils import timezone

        now = timezone.now()
        ensemble_weights = results.get('ensemble_weights', {})

        for model_name in ['svd', 'ncf', 'sequential']:
            model_result = results.get(model_name, {})
            if model_result.get('status') != 'ok':
                continue

            m = model_result.get('metrics', {})
            ModelEvaluationResult.objects.create(
                model_name=model_name,
                evaluated_at=now,
                train_loss=m.get('train_loss') or m.get('final_loss'),
                train_rmse=m.get('rmse_mean'),
                test_rmse=m.get('test_rmse'),
                test_hit_rate_at_10=m.get('test_hit_rate_at_10'),
                n_users=m.get('n_users'),
                n_items=m.get('n_items'),
                n_interactions=m.get('n_interactions') or m.get('n_ratings') or m.get('n_sequences'),
                ensemble_weight=ensemble_weights.get(model_name),
                raw_metrics=m,
            )
            logger.info(f"Saved training metrics for {model_name}")

        logger.info("Training metrics persisted to DB")
    except Exception as e:
        logger.error(f"Failed to persist training metrics: {e}", exc_info=True)

    # ---- Run offline evaluation and persist ----
    try:
        from lti_recommender_project.ml.training.evaluate_models import ModelEvaluator
        from lti_recommender_project.apps.analytics.models import ModelEvaluationResult
        from django.utils import timezone

        evaluator = ModelEvaluator(k=5, test_ratio=0.2, min_interactions=3, max_users=50)
        eval_time = timezone.now()
        ensemble_weights = results.get('ensemble_weights', {})

        eval_targets = []

        # SVD
        try:
            from lti_recommender_project.ml.models.matrix_factorization import get_svd_model
            svd_m = get_svd_model()
            if svd_m._is_fitted:
                eval_targets.append(('svd', svd_m.get_recommendations))
        except Exception:
            pass

        # NCF
        try:
            from lti_recommender_project.ml.models.neural_cf import get_ncf_model
            ncf_m = get_ncf_model()
            if ncf_m._is_fitted:
                eval_targets.append(('ncf', ncf_m.get_recommendations))
        except Exception:
            pass

        # Sequential
        try:
            from lti_recommender_project.ml.models.sequential_rec import get_sequential_model
            seq_m = get_sequential_model()
            if seq_m._is_fitted:
                eval_targets.append(('sequential', seq_m.get_recommendations))
        except Exception:
            pass

        # Ensemble
        try:
            from lti_recommender_project.ml.models.ensemble import get_ensemble_recommender
            ens = get_ensemble_recommender()
            eval_targets.append(('ensemble', ens.get_recommendations))
        except Exception:
            pass

        for model_name, get_recs_fn in eval_targets:
            try:
                eval_result = evaluator.evaluate_model(get_recs_fn, model_name)
                if 'error' not in eval_result:
                    ModelEvaluationResult.objects.create(
                        model_name=model_name,
                        evaluated_at=eval_time,
                        precision_at_5=eval_result.get('precision_at_k'),
                        recall_at_5=eval_result.get('recall_at_k'),
                        ndcg_at_5=eval_result.get('ndcg_at_k'),
                        mrr=eval_result.get('mrr'),
                        hit_at_5=eval_result.get('hit_rate'),
                        map_at_k=eval_result.get('map_at_k'),
                        f1_score=eval_result.get('f1_score'),
                        coverage=eval_result.get('coverage'),
                        n_users_evaluated=eval_result.get('n_users_evaluated'),
                        ensemble_weight=ensemble_weights.get(model_name),
                        raw_metrics=eval_result,
                    )
                    logger.info(f"Offline eval saved for {model_name}: P@5={eval_result.get('precision_at_k', 0):.4f}")
                    results[f'{model_name}_eval'] = eval_result
            except Exception as e:
                logger.error(f"Offline eval failed for {model_name}: {e}")

        logger.info("Offline evaluation complete and persisted")
    except Exception as e:
        logger.error(f"Offline evaluation phase failed: {e}", exc_info=True)

    # Invalidate singleton so next request loads fresh model
    try:
        from lti_recommender_project.ml.models import ensemble as ens_mod
        ens_mod._ensemble_instance = None
    except Exception:
        pass

    logger.info(f"Retraining complete: {results}")
    return results


@shared_task(
    name='lti_recommender_project.apps.recommendations.tasks.update_embeddings_incremental',
    queue='embeddings',
)
def update_embeddings_incremental():
    """
    Actualización INCREMENTAL de embeddings de recursos.
    Solo procesa recursos nuevos o modificados desde el último update.
    Ejecutado cada hora via Celery Beat.
    """
    try:
        from lti_recommender_project.apps.recommendations.services.embedding_service import (
            get_embedding_service
        )
        service = get_embedding_service()
        updated, failed = service.update_embeddings_incremental(batch_size=32)
        logger.info(f"Embeddings: {updated} updated, {failed} failed")
        return {'updated': updated, 'failed': failed}
    except Exception as e:
        logger.error(f"Embedding update failed: {e}", exc_info=True)
        return {'updated': 0, 'failed': -1, 'error': str(e)}


@shared_task(
    name='lti_recommender_project.apps.recommendations.tasks.precompute_active_users',
    queue='recommendations',
)
def precompute_active_users():
    """
    Pre-calcula y cachea recomendaciones para usuarios activos recientes.
    
    Beneficio: LTI launch devuelve recomendaciones en <50ms (cache HIT)
    en lugar de 1-5s (modelo en memoria).
    
    Ejecutado cada 30 minutos via Celery Beat.
    """
    from django.utils import timezone
    from datetime import timedelta
    from django.core.cache import cache
    from lti_recommender_project.apps.interactions.models import UserInteraction
    from lti_recommender_project.ml.models.ensemble import get_ensemble_recommender
    from lti_recommender_project.apps.users.student_profile import StudentProfile

    config = getattr(settings, 'RECOMMENDATION_CONFIG', {})
    active_days = config.get('ACTIVE_USER_DAYS', 7)
    cache_ttl = config.get('RECOMMENDATION_CACHE_TTL', 1800)

    cutoff = timezone.now() - timedelta(days=active_days)
    active_pairs = list(
        UserInteraction.objects.filter(
            timestamp__gte=cutoff
        ).values('lti_user_id', 'lti_context_id').distinct()[:500]  # Max 500 users
    )

    engine = get_ensemble_recommender()
    precomputed, skipped, errors = 0, 0, 0

    for pair in active_pairs:
        user_id = pair['lti_user_id']
        context_id = pair['lti_context_id']
        cache_key = f"recs:v2:{user_id}:{context_id}"

        # Only recompute if cache expired (reduce unnecessary work)
        if cache.get(cache_key) is not None:
            skipped += 1
            continue

        try:
            recs = engine.get_recommendations(user_id, context_id, limit=10)
            cache.set(cache_key, recs, timeout=cache_ttl)
            precomputed += 1
        except Exception as e:
            logger.error(f"Precompute failed for {user_id[:8]}...: {e}")
            errors += 1

    logger.info(
        f"Precompute done: {precomputed} computed, {skipped} skipped (cached), {errors} errors"
    )
    return {'precomputed': precomputed, 'skipped': skipped, 'errors': errors}


@shared_task(
    name='lti_recommender_project.apps.recommendations.tasks.run_scraper_task',
    queue='scraping',
)
def run_scraper_task():
    """
    Ejecuta el scraper de Scrapy programáticamente.
    Tras completar, dispara update_embeddings_incremental.
    Ejecutado nightly a las 3am UTC via Celery Beat.
    """
    import subprocess
    import os

    scraper_dir = os.path.join(
        settings.BASE_DIR,
        'lti_recommender_project', 'scraper'
    )

    try:
        result = subprocess.run(
            ['scrapy', 'crawl', 'oer'],
            cwd=scraper_dir,
            capture_output=True,
            text=True,
            timeout=1800,  # 30 min max
        )

        if result.returncode == 0:
            logger.info("Scraper completed successfully")
            # Update embeddings for newly scraped resources
            update_embeddings_incremental.apply_async(countdown=30, queue='embeddings')
            return {'status': 'ok', 'output': result.stdout[-500:]}
        else:
            logger.error(f"Scraper failed: {result.stderr[-500:]}")
            return {'status': 'error', 'stderr': result.stderr[-500:]}

    except subprocess.TimeoutExpired:
        logger.error("Scraper timed out after 30 minutes")
        return {'status': 'timeout'}
    except Exception as e:
        logger.error(f"Scraper task error: {e}", exc_info=True)
        return {'status': 'error', 'error': str(e)}
