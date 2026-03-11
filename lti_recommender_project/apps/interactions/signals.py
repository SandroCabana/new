"""
Django signal: invalida la caché de recomendaciones cuando se registra una nueva interacción.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender='interactions.UserInteraction')
def invalidate_recommendation_cache(sender, instance, created, **kwargs):
    """
    Signal: cuando se guarda una nueva interacción, invalida la cache
    de recomendaciones del usuario en ese contexto.
    """
    if not created:
        return  # Only on new interactions, not updates

    try:
        from django.core.cache import cache
        cache_key = f"recs:v2:{instance.lti_user_id}:{instance.lti_context_id}"
        cache.delete(cache_key)
        logger.debug(
            f"Cache invalidated for user={instance.lti_user_id[:8]}... "
            f"context={instance.lti_context_id[:8]}..."
        )
    except Exception as e:
        logger.warning(f"Unable to invalidate cache: {e}")
