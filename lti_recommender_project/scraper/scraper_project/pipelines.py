# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


# useful for handling different item types with a single interface
import os
import django
from itemadapter import ItemAdapter
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lti_recommender_project.settings_docker")
django.setup()
from lti_recommender_project.apps.resources.models import EducationalResource
class ScraperProjectPipeline:
    def process_item(self, item, spider):
        adapter = ItemAdapter(item)

        # Generamos un resource_id único (ejemplo: hash del URL)
        resource_id = adapter.get("resource_id") or adapter["url"]

        EducationalResource.objects.update_or_create(
            resource_id=resource_id,
            lti_context_id=None,  # si quieres asociarlo a un curso en específico, cámbialo aquí
            defaults={
                "title": adapter.get("title", "Sin título"),
                "description": adapter.get("description", ""),
                "url": adapter.get("url"),
                "author": adapter.get("author", ""),
                "resource_type": adapter.get("resource_type", "other"),
                "tags": adapter.get("tags", ""),
                "difficulty_level": adapter.get("difficulty_level"),
            },
        )
        return item
