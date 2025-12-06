# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


# useful for handling different item types with a single interface
import os
import django
import logging
from itemadapter import ItemAdapter

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lti_recommender_project.settings")
django.setup()

from lti_recommender_project.apps.resources.models import EducationalResource
from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)


class ScraperProjectPipeline:
    def __init__(self):
        self.resources_saved = 0
        self.resources_updated = 0
        self.resources_failed = 0

    async def process_item(self, item, spider):
        adapter = ItemAdapter(item)

        # Validate required fields
        if not adapter.get("url"):
            logger.error(f"Item missing URL, skipping: {adapter.get('title', 'Unknown')}")
            self.resources_failed += 1
            return item

        # Generate resource_id if not present
        resource_id = adapter.get("resource_id") or adapter["url"]
        
        # Check for duplicates by URL to skip unnecessary processing
        @sync_to_async
        def check_duplicate():
            return EducationalResource.objects.filter(url=adapter.get("url")).exists()
        
        if await check_duplicate():
            logger.debug(f"⊘ Skipping duplicate: {adapter.get('title', 'Unknown')[:50]}")
            return item

        try:
            # Wrap Django ORM call in sync_to_async
            @sync_to_async
            def save_resource():
                return EducationalResource.objects.update_or_create(
                    resource_id=resource_id,
                    defaults={
                        "title": adapter.get("title", "Sin título")[:255],
                        "description": adapter.get("description", "")[:1000],
                        "url": adapter.get("url")[:500],
                        "author": adapter.get("author", "")[:255],
                        "resource_type": adapter.get("resource_type", "other"),
                        "tags": adapter.get("tags", "")[:500],
                        "difficulty_level": adapter.get("difficulty_level"),
                        "lti_context_id": adapter.get("lti_context_id"),
                    },
                )
            
            resource, created = await save_resource()
            
            if created:
                self.resources_saved += 1
                logger.info(f"✓ Created: {resource.title}")
            else:
                self.resources_updated += 1
                logger.info(f"↻ Updated: {resource.title}")
                
        except Exception as e:
            self.resources_failed += 1
            logger.error(f"✗ Error saving resource '{adapter.get('title', 'Unknown')}': {e}")

        return item

    def close_spider(self, spider):
        logger.info(f"\n=== Scraping Summary ===")
        logger.info(f"Resources created: {self.resources_saved}")
        logger.info(f"Resources updated: {self.resources_updated}")
        logger.info(f"Resources failed: {self.resources_failed}")
        logger.info(f"Total processed: {self.resources_saved + self.resources_updated + self.resources_failed}")

