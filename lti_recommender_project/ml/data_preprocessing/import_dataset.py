"""
Dataset Importer for E-Learning Recommendation System.
Supports multiple dataset formats from Kaggle and other sources.

Usage:
    python import_dataset.py --source kaggle --dataset e-learning
    python import_dataset.py --source csv --file courses.csv --type resources
    python import_dataset.py --generate --n-users 100 --n-resources 500
"""

import os
import sys
import json
import csv
import random
import argparse
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional

# Django setup
# Script is at: lti_recommender_project/ml/data_preprocessing/import_dataset.py
# PROJECT_ROOT should be: lti_moodle_recomender (parent of lti_recommender_project)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lti_recommender_project.settings')

import django
django.setup()

from django.db import transaction
from lti_recommender_project.apps.resources.models import EducationalResource
from lti_recommender_project.apps.interactions.models import UserInteraction

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Sample educational topics for synthetic data
TOPICS = [
    'Python Programming', 'Machine Learning', 'Data Science', 'Web Development',
    'JavaScript', 'React', 'Django', 'Database Design', 'SQL', 'NoSQL',
    'Cloud Computing', 'AWS', 'Docker', 'Kubernetes', 'DevOps',
    'Artificial Intelligence', 'Deep Learning', 'Neural Networks', 'NLP',
    'Computer Vision', 'Statistics', 'Linear Algebra', 'Calculus',
    'Data Visualization', 'Tableau', 'Power BI', 'Excel',
    'Project Management', 'Agile', 'Scrum', 'Leadership',
    'Communication', 'Public Speaking', 'Writing', 'Research Methods',
]

RESOURCE_TYPES = ['video', 'article', 'course', 'quiz', 'exercise', 'ebook', 'tutorial']
DIFFICULTY_LEVELS = ['beginner', 'intermediate', 'advanced']


class DatasetImporter:
    """Import datasets into the Django models."""
    
    def __init__(self):
        self.stats = {
            'resources_created': 0,
            'interactions_created': 0,
            'users_created': set(),
        }
    
    def import_from_csv(
        self,
        resources_file: Optional[str] = None,
        interactions_file: Optional[str] = None,
        context_id: str = 'imported_course'
    ):
        """
        Import data from CSV files.
        
        Expected formats:
        
        resources.csv:
            id,title,description,url,type,difficulty,tags
        
        interactions.csv:
            user_id,resource_id,rating,completion,timestamp
        """
        if resources_file:
            self._import_resources_csv(resources_file, context_id)
        
        if interactions_file:
            self._import_interactions_csv(interactions_file)
    
    def _import_resources_csv(self, filepath: str, context_id: str):
        """Import resources from CSV."""
        logger.info(f"Importing resources from {filepath}...")
        
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                resource_id = row.get('id', row.get('resource_id', str(hash(row.get('title', '')))))
                resource, created = EducationalResource.objects.update_or_create(
                    resource_id=f"imported_{resource_id}",
                    defaults={
                        'title': row.get('title', row.get('name', 'Untitled')),
                        'description': row.get('description', ''),
                        'url': row.get('url', row.get('link', f'https://example.com/{resource_id}')),
                        'resource_type': row.get('type', row.get('resource_type', 'article')),
                        'difficulty_level': row.get('difficulty', row.get('level', 'intermediate')),
                        'lti_context_id': context_id,
                        'tags': row.get('tags', row.get('category', '')),
                    }
                )
                
                if created:
                    self.stats['resources_created'] += 1
        
        logger.info(f"Created {self.stats['resources_created']} resources")
    
    def _import_interactions_csv(self, filepath: str):
        """Import interactions from CSV."""
        logger.info(f"Importing interactions from {filepath}...")
        
        # Build resource mapping
        resources = {str(r.id): r for r in EducationalResource.objects.all()}
        
        # Also map by resource_id
        for r in EducationalResource.objects.all():
            if r.resource_id:
                resources[r.resource_id] = r
                # Remove prefix for matching
                if r.resource_id.startswith('imported_'):
                    resources[r.resource_id.replace('imported_', '')] = r
        
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                user_id = row.get('user_id', row.get('userId', row.get('user')))
                resource_id = row.get('resource_id', row.get('item_id', row.get('course_id')))
                
                if not user_id or resource_id not in resources:
                    continue
                
                resource = resources[resource_id]
                
                # Parse rating
                rating = None
                if row.get('rating'):
                    try:
                        rating = float(row['rating'])
                        # Normalize to 1-5 scale if needed
                        if rating <= 1:
                            rating = rating * 5
                    except ValueError:
                        pass
                
                # Parse completion
                completion = None
                if row.get('completion', row.get('progress')):
                    try:
                        completion = float(row.get('completion', row.get('progress', 0)))
                        if completion > 1:
                            completion = min(completion, 100)
                        else:
                            completion = completion * 100
                    except ValueError:
                        pass
                
                # Parse timestamp
                timestamp = datetime.now()
                if row.get('timestamp'):
                    try:
                        timestamp = datetime.fromisoformat(row['timestamp'])
                    except ValueError:
                        try:
                            timestamp = datetime.fromtimestamp(float(row['timestamp']))
                        except ValueError:
                            pass
                
                interaction, created = UserInteraction.objects.update_or_create(
                    lti_user_id=f"user_{user_id}",
                    resource=resource,
                    defaults={
                        'lti_context_id': resource.lti_context_id or 'imported_course',
                        'interaction_type': 'view',
                        'rating': rating,
                        'completion_percentage': completion,
                        'timestamp': timestamp,
                    }
                )
                
                if created:
                    self.stats['interactions_created'] += 1
                    self.stats['users_created'].add(user_id)
        
        logger.info(f"Created {self.stats['interactions_created']} interactions")
        logger.info(f"Unique users: {len(self.stats['users_created'])}")
    
    def generate_synthetic_data(
        self,
        n_users: int = 100,
        n_resources: int = 500,
        n_interactions: int = 5000,
        context_id: str = 'synthetic_course'
    ):
        """
        Generate synthetic but realistic training data.
        
        Creates:
        - Users with different skill levels and preferences
        - Resources with various topics and difficulties
        - Interactions following realistic patterns
        """
        logger.info(f"Generating synthetic data: {n_users} users, {n_resources} resources, {n_interactions} interactions")
        
        # Generate resources
        resources = self._generate_resources(n_resources, context_id)
        
        # Generate user profiles (internal)
        user_profiles = self._generate_user_profiles(n_users)
        
        # Generate interactions
        self._generate_interactions(user_profiles, resources, n_interactions, context_id)
        
        logger.info("Synthetic data generation complete!")
        self._print_stats()
    
    def _generate_resources(self, n_resources: int, context_id: str) -> List[EducationalResource]:
        """Generate synthetic educational resources."""
        resources = []
        
        # Use timestamp-based offset to generate unique IDs for new runs
        import time
        offset = int(time.time()) % 100000 * 1000
        
        with transaction.atomic():
            for i in range(n_resources):
                topic = random.choice(TOPICS)
                resource_type = random.choice(RESOURCE_TYPES)
                difficulty = random.choices(
                    DIFFICULTY_LEVELS,
                    weights=[0.4, 0.4, 0.2]  # More beginner/intermediate content
                )[0]
                
                # Generate realistic title
                title_templates = [
                    f"Introduction to {topic}",
                    f"{topic} Fundamentals",
                    f"Advanced {topic} Techniques",
                    f"{topic} for {random.choice(['Beginners', 'Professionals', 'Everyone'])}",
                    f"Master {topic}",
                    f"{topic}: {random.choice(['Complete Guide', 'Quick Start', 'Deep Dive'])}",
                    f"Learn {topic} in {random.randint(7, 30)} Days",
                    f"{topic} {random.choice(['Workshop', 'Bootcamp', 'Masterclass'])}",
                ]
                
                title = random.choice(title_templates)
                
                description = f"A comprehensive {resource_type} covering {topic}. "
                description += f"Difficulty: {difficulty}. "
                description += f"Perfect for anyone interested in {topic.lower()}."
                
                resource_id = f"synthetic_{offset + i:08d}"
                
                resource, created = EducationalResource.objects.update_or_create(
                    resource_id=resource_id,
                    defaults={
                        'title': title,
                        'description': description,
                        'url': f"https://learn.example.com/{topic.lower().replace(' ', '-')}/{offset + i}",
                        'resource_type': resource_type,
                        'difficulty_level': difficulty,
                        'lti_context_id': context_id,
                        'tags': topic,
                    }
                )
                
                resources.append(resource)
                if created:
                    self.stats['resources_created'] += 1
        
        logger.info(f"Created/updated {len(resources)} resources ({self.stats['resources_created']} new)")
        return resources

    
    def _generate_user_profiles(self, n_users: int) -> List[Dict]:
        """Generate internal user profiles for realistic interactions."""
        profiles = []
        
        for i in range(n_users):
            # Each user has skill level and topic preferences
            skill_level = random.choices(
                ['beginner', 'intermediate', 'advanced'],
                weights=[0.5, 0.35, 0.15]
            )[0]
            
            # User prefers 2-5 topics
            n_preferred_topics = random.randint(2, 5)
            preferred_topics = random.sample(TOPICS, n_preferred_topics)
            
            # Engagement level affects number of interactions
            engagement = random.choices(
                ['low', 'medium', 'high'],
                weights=[0.3, 0.5, 0.2]
            )[0]
            
            profiles.append({
                'user_id': f"user_{i+1:04d}",
                'skill_level': skill_level,
                'preferred_topics': preferred_topics,
                'engagement': engagement,
                'rating_tendency': random.uniform(3.0, 4.5),  # Average rating given
            })
        
        return profiles
    
    def _generate_interactions(
        self,
        user_profiles: List[Dict],
        resources: List[EducationalResource],
        n_interactions: int,
        context_id: str
    ):
        """Generate realistic user-resource interactions."""
        
        # Build resource index by topic
        resources_by_topic = {}
        for r in resources:
            topic = r.tags if r.tags else None
            if topic:
                if topic not in resources_by_topic:
                    resources_by_topic[topic] = []
                resources_by_topic[topic].append(r)
        
        interactions_per_user = {p['user_id']: 0 for p in user_profiles}
        base_date = datetime.now() - timedelta(days=90)
        
        created = 0
        attempts = 0
        max_attempts = n_interactions * 3
        
        with transaction.atomic():
            while created < n_interactions and attempts < max_attempts:
                attempts += 1
                
                # Select user (weighted by engagement)
                user = random.choice(user_profiles)
                
                # Check if user can have more interactions
                max_interactions = {'low': 20, 'medium': 50, 'high': 100}[user['engagement']]
                if interactions_per_user[user['user_id']] >= max_interactions:
                    continue
                
                # Select resource (prefer user's topics)
                if random.random() < 0.7 and user['preferred_topics']:
                    # Choose from preferred topics
                    topic = random.choice(user['preferred_topics'])
                    if topic in resources_by_topic and resources_by_topic[topic]:
                        resource = random.choice(resources_by_topic[topic])
                    else:
                        resource = random.choice(resources)
                else:
                    # Random exploration
                    resource = random.choice(resources)
                
                # Check for duplicate
                if UserInteraction.objects.filter(
                    lti_user_id=user['user_id'],
                    resource=resource
                ).exists():
                    continue
                
                # Generate interaction details
                # Skill match affects completion and rating
                skill_match = self._skill_match(user['skill_level'], resource.difficulty_level)
                
                # Completion percentage
                base_completion = random.gauss(70, 20)
                completion = min(100, max(0, base_completion + skill_match * 10))
                
                # Rating (influenced by skill match and user tendency)
                base_rating = user['rating_tendency'] + skill_match * 0.5
                rating = min(5.0, max(1.0, random.gauss(base_rating, 0.5)))
                
                # Only some interactions have explicit ratings
                if random.random() > 0.3:
                    rating = None
                
                # Timestamp
                days_ago = random.randint(0, 90)
                timestamp = base_date + timedelta(
                    days=days_ago,
                    hours=random.randint(8, 22),
                    minutes=random.randint(0, 59)
                )
                
                # Time spent (correlated with completion)
                time_spent = int(completion * 0.6 * random.uniform(0.5, 1.5))
                
                UserInteraction.objects.create(
                    lti_user_id=user['user_id'],
                    resource=resource,
                    lti_context_id=context_id,
                    interaction_type=random.choice(['view', 'complete', 'study']),
                    rating=round(rating, 1) if rating else None,
                    completion_percentage=round(completion, 1),
                    time_spent=time_spent,
                    timestamp=timestamp,
                )
                
                created += 1
                interactions_per_user[user['user_id']] += 1
                self.stats['users_created'].add(user['user_id'])
        
        self.stats['interactions_created'] = created
        logger.info(f"Created {created} interactions")
    
    def _skill_match(self, user_skill: str, resource_difficulty: str) -> float:
        """Calculate skill match score (-1 to 1)."""
        levels = {'beginner': 0, 'intermediate': 1, 'advanced': 2}
        user_level = levels.get(user_skill, 1)
        resource_level = levels.get(resource_difficulty, 1)
        
        diff = user_level - resource_level
        if diff == 0:
            return 0.5  # Perfect match
        elif diff > 0:
            return 0.2 * diff  # User more advanced
        else:
            return -0.3 * abs(diff)  # Resource too difficult
    
    def _print_stats(self):
        """Print import statistics."""
        print("\n" + "=" * 50)
        print("           IMPORT STATISTICS")
        print("=" * 50)
        print(f"Resources created: {self.stats['resources_created']}")
        print(f"Interactions created: {self.stats['interactions_created']}")
        print(f"Unique users: {len(self.stats['users_created'])}")
        print("=" * 50)


def main():
    parser = argparse.ArgumentParser(description='Import datasets for recommendation training')
    
    # Source options
    parser.add_argument('--resources', type=str, help='Path to resources CSV file')
    parser.add_argument('--interactions', type=str, help='Path to interactions CSV file')
    parser.add_argument('--context', type=str, default='imported_course', help='Context ID for imported data')
    
    # Synthetic data options
    parser.add_argument('--generate', action='store_true', help='Generate synthetic data')
    parser.add_argument('--n-users', type=int, default=100, help='Number of users for synthetic data')
    parser.add_argument('--n-resources', type=int, default=500, help='Number of resources for synthetic data')
    parser.add_argument('--n-interactions', type=int, default=5000, help='Number of interactions for synthetic data')
    
    args = parser.parse_args()
    
    importer = DatasetImporter()
    
    if args.generate:
        importer.generate_synthetic_data(
            n_users=args.n_users,
            n_resources=args.n_resources,
            n_interactions=args.n_interactions,
            context_id=args.context
        )
    elif args.resources or args.interactions:
        importer.import_from_csv(
            resources_file=args.resources,
            interactions_file=args.interactions,
            context_id=args.context
        )
    else:
        print("Usage:")
        print("  Generate synthetic data:")
        print("    python import_dataset.py --generate --n-users 100 --n-resources 500 --n-interactions 5000")
        print("")
        print("  Import from CSV:")
        print("    python import_dataset.py --resources courses.csv --interactions ratings.csv")


if __name__ == '__main__':
    main()
