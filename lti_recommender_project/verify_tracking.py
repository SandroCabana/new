
import os
import django
import json
import requests
import sys

# Setup Django environment
sys.path.append('/home/sandrocabana/lti_moodle_recomender')
sys.path.append('/home/sandrocabana/lti_moodle_recomender/lti_recommender_project') # Add project root too just in case
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lti_recommender_project.settings')
django.setup()

from django.conf import settings
if 'testserver' not in settings.ALLOWED_HOSTS:
    settings.ALLOWED_HOSTS.append('testserver')

from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient
from lti_recommender_project.apps.resources.models import EducationalResource
from lti_recommender_project.apps.interactions.models import UserInteraction

def run_verification():
    print("Starting verification...")
    
    # Setup user and token
    user, created = User.objects.get_or_create(username='test_verification_user')
    token, _ = Token.objects.get_or_create(user=user)
    
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION='Token ' + token.key)
    
    # Test Data
    payload = {
        "userID": 12345,
        "associatedPLE": "course_101",
        "trackedDataList": [
            {
                "activityType": "video",
                "associatedURL": "https://example.com/video/1",
                "associatedDomains": ["example.com", "youtube.com"],
                "associatedKeywords": ["math", "algebra"],
                "startTime": "2023-10-27T10:00:00Z",
                "endTime": "2023-10-27T10:05:00Z",
                "feedback": {
                    "score": 5,
                    "comments": "Great video!"
                }
            },
            {
                "activityType": "article",
                "associatedURL": "https://example.com/article/2",
                "startTime": "2023-10-27T11:00:00Z",
                "endTime": "2023-10-27T11:02:00Z"
            }
        ]
    }
    
    print("\n1. Testing Valid Batch Request...")
    response = client.post('/interactions/tracked-data-batch/', payload, format='json')
    
    if response.status_code == 201:
        print("✅ Success: Status 201 Created")
        print(f"Response: {response.data}")
    else:
        print(f"❌ Failed: Status {response.status_code}")
        print(response.data)
        return

    # Verify Database
    print("\n2. Verifying Database Entries...")
    
    # Check Resources
    r1 = EducationalResource.objects.filter(url="https://example.com/video/1").first()
    if r1:
        print(f"✅ Resource 1 created: {r1.title}")
    else:
        print("❌ Resource 1 not found")

    r2 = EducationalResource.objects.filter(url="https://example.com/article/2").first()
    if r2:
        print(f"✅ Resource 2 created: {r2.title}")
    else:
        print("❌ Resource 2 not found")

    # Check Interactions
    interactions = UserInteraction.objects.filter(lti_user_id="12345")
    if interactions.count() >= 2:
        print(f"✅ Interactions created: {interactions.count()} found")
        for i in interactions:
            print(f"   - {i.interaction_type} on {i.resource.url} (Time: {i.time_spent}s, Rating: {i.rating})")
    else:
         print(f"❌ Interactions count incorrect: {interactions.count()}")

    # Test Duplicate Resource
    print("\n3. Testing Duplicate Resource (Sending same payload again)...")
    response_dup = client.post('/interactions/tracked-data-batch/', payload, format='json')
    if response_dup.status_code == 201:
         print("✅ Success: Duplicate batch accepted")
         # Check resource count should not double for these URLs
         count1 = EducationalResource.objects.filter(url="https://example.com/video/1").count()
         if count1 == 1:
             print("✅ Resource uniqueness preserved")
         else:
             print(f"❌ Duplicate resources created? Count: {count1}")
    else:
        print(f"❌ Duplicate batch failed: {response_dup.status_code}")

    # Test Invalid Token
    print("\n4. Testing Invalid Token...")
    client.credentials(HTTP_AUTHORIZATION='Token invalidtoken123')
    response_inv = client.post('/interactions/tracked-data-batch/', payload, format='json')
    if response_inv.status_code in [401, 403]:
        print("✅ Success: Access denied as expected")
    else:
        print(f"❌ Unexpected status for invalid token: {response_inv.status_code}")

if __name__ == "__main__":
    run_verification()
