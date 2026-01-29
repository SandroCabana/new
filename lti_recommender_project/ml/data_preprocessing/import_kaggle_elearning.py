"""
Import E-Learning Recommender Dataset from Kaggle.
https://www.kaggle.com/datasets/nhondangcode/e-learning-recommender-system-dataset
"""

import os
import sys
import csv
from pathlib import Path

# Django setup
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lti_recommender_project.settings')

import django
django.setup()

from django.db import transaction
from lti_recommender_project.apps.resources.models import EducationalResource
from lti_recommender_project.apps.interactions.models import UserInteraction
from datetime import datetime

DATASETS_DIR = Path(__file__).parent.parent / 'datasets'


def import_kaggle_elearning():
    """Import the Kaggle E-Learning Recommender dataset."""
    
    # Process train and test files
    files = [
        DATASETS_DIR / 'train_e_learning_recommender.csv',
        DATASETS_DIR / 'test_e_learning_recommender.csv',
    ]
    
    resources_created = 0
    interactions_created = 0
    users = set()
    
    for filepath in files:
        if not filepath.exists():
            print(f"File not found: {filepath}")
            continue
        
        print(f"\nProcessing: {filepath.name}")
        
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            with transaction.atomic():
                for row in reader:
                    # Extract data
                    user_id = row.get('user_id', '')
                    item_id = row.get('item_id', '')
                    name = row.get('name', 'Untitled')
                    description = row.get('description', '')[:2000]  # Limit size
                    duration = row.get('duration', '0')
                    difficulty = row.get('Difficulty', 'unknown')
                    software = row.get('Software', '')
                    watch_percentage = row.get('watch_percentage', '0')
                    rating = row.get('rating', '')
                    
                    if not user_id or not item_id:
                        continue
                    
                    # Map difficulty
                    difficulty_map = {
                        'Beginner': 'beginner',
                        'Intermediate': 'intermediate', 
                        'Advanced': 'advanced',
                        'unknown': 'intermediate',
                    }
                    difficulty_level = difficulty_map.get(difficulty, 'intermediate')
                    
                    # Create or update resource
                    resource, created = EducationalResource.objects.update_or_create(
                        resource_id=f"kaggle_{item_id}",
                        defaults={
                            'title': name[:255],
                            'description': description,
                            'url': f"https://elearning.example.com/course/{item_id}",
                            'resource_type': 'video',  # Most are tutorials
                            'difficulty_level': difficulty_level,
                            'lti_context_id': 'kaggle_elearning',
                            'tags': software.replace('[', '').replace(']', '').replace("'", ""),
                        }
                    )
                    
                    if created:
                        resources_created += 1
                    
                    # Create interaction
                    try:
                        watch_pct = float(watch_percentage) * 100 if float(watch_percentage) <= 1 else float(watch_percentage)
                        watch_pct = min(100, max(0, watch_pct))
                    except:
                        watch_pct = None
                    
                    try:
                        rating_val = int(float(rating)) if rating else None
                        rating_val = min(5, max(1, rating_val)) if rating_val else None
                    except:
                        rating_val = None
                    
                    # Skip if interaction already exists
                    if UserInteraction.objects.filter(
                        lti_user_id=f"kaggle_user_{user_id}",
                        resource=resource
                    ).exists():
                        continue
                    
                    UserInteraction.objects.create(
                        lti_user_id=f"kaggle_user_{user_id}",
                        resource=resource,
                        lti_context_id='kaggle_elearning',
                        interaction_type='view',
                        completion_percentage=watch_pct,
                        rating=rating_val,
                    )
                    
                    interactions_created += 1
                    users.add(user_id)
    
    print("\n" + "=" * 50)
    print("       KAGGLE IMPORT COMPLETE")
    print("=" * 50)
    print(f"Resources created: {resources_created}")
    print(f"Interactions created: {interactions_created}")
    print(f"Unique users: {len(users)}")
    print("=" * 50)
    
    # Show totals in DB
    print(f"\nTotal resources in DB: {EducationalResource.objects.count()}")
    print(f"Total interactions in DB: {UserInteraction.objects.count()}")


if __name__ == '__main__':
    import_kaggle_elearning()
