
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lti_recommender_project.settings")
django.setup()

from lti_recommender_project.apps.resources.models import EducationalResource

count = EducationalResource.objects.count()
print(f"Current number of EducationalResource objects: {count}")
