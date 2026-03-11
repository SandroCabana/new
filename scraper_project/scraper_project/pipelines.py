# Scrapy Pipelines — v2
# Mejoras: deduplicación por SHA-256 fingerprint, upsert con update_or_create,
# trigger async de embedding update tras nuevo recurso.

import os
import hashlib
import django
import logging
from itemadapter import ItemAdapter

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lti_recommender_project.settings")
django.setup()

from lti_recommender_project.apps.resources.models import EducationalResource
from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)


class DeduplicationPipeline:
    """
    Deduplication a dos niveles:
    1. In-process: Set de fingerprints visto en esta sesión (evita DB roundtrip)
    2. DB-level: update_or_create evita duplicados permanentes

    Fingerprint = SHA-256(url.strip().lower()) — invariante a parámetros de query menores.
    """

    def __init__(self):
        self._seen_fingerprints: set = set()

    def _fingerprint(self, url: str) -> str:
        """SHA-256 del URL normalizado."""
        normalized = url.strip().lower().split('?')[0]  # Remove query params
        return hashlib.sha256(normalized.encode('utf-8')).hexdigest()

    async def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        url = adapter.get('url', '')

        if not url:
            raise Exception("Item sin URL — descartado")

        fp = self._fingerprint(url)

        if fp in self._seen_fingerprints:
            logger.debug(f"⊘ In-process duplicate: {adapter.get('title', url)[:50]}")
            return None  # Drop item (Scrapy ignores None return silently)

        self._seen_fingerprints.add(fp)
        return item

    def close_spider(self, spider):
        logger.info(f"DeduplicationPipeline: {len(self._seen_fingerprints)} unique URLs seen")


class DatabasePipeline:
    """
    Persiste recursos mediante upsert (update_or_create).
    Tras crear un NUEVO recurso, dispara embedding update.
    """

    def __init__(self):
        self.resources_created = 0
        self.resources_updated = 0
        self.resources_failed = 0

    async def process_item(self, item, spider):
        if item is None:
            return item

        adapter = ItemAdapter(item)
        url = adapter.get('url', '')

        if not url:
            self.resources_failed += 1
            return item

        resource_id = adapter.get('resource_id') or url

        try:
            @sync_to_async
            def upsert_resource():
                return EducationalResource.objects.update_or_create(
                    resource_id=resource_id,
                    defaults={
                        'title': (adapter.get('title') or 'Sin título')[:255],
                        'description': (adapter.get('description') or '')[:1000],
                        'url': url[:500],
                        'author': (adapter.get('author') or '')[:255],
                        'resource_type': adapter.get('resource_type', 'other'),
                        'tags': (adapter.get('tags') or '')[:500],
                        'difficulty_level': adapter.get('difficulty_level'),
                        'lti_context_id': adapter.get('lti_context_id'),
                    },
                )

            resource, created = await upsert_resource()

            if created:
                self.resources_created += 1
                logger.info(f"✓ Creado: {resource.title[:60]}")
                # Trigger incremental embedding update for this resource
                await self._trigger_embedding_update(resource.id)
            else:
                self.resources_updated += 1
                logger.debug(f"↻ Actualizado: {resource.title[:60]}")

        except Exception as e:
            self.resources_failed += 1
            logger.error(f"✗ Error guardando '{adapter.get('title', url)[:50]}': {e}")

        return item

    @staticmethod
    async def _trigger_embedding_update(resource_id: int):
        """Dispara embedding update de forma async vía Celery."""
        try:
            @sync_to_async
            def _send_task():
                from lti_recommender_project.apps.recommendations.tasks import (
                    update_embeddings_incremental
                )
                update_embeddings_incremental.apply_async(countdown=60)  # after 60s delay

            await _send_task()
            logger.debug(f"Embedding update triggered for resource {resource_id}")
        except Exception as e:
            logger.warning(f"Could not trigger embedding update: {e}")

    def close_spider(self, spider):
        total = self.resources_created + self.resources_updated + self.resources_failed
        logger.info(
            f"\n=== Scraper Summary ===\n"
            f"  Created: {self.resources_created}\n"
            f"  Updated: {self.resources_updated}\n"
            f"  Failed:  {self.resources_failed}\n"
            f"  Total:   {total}"
        )


# Keep backwards compat alias
ScraperProjectPipeline = DatabasePipeline
