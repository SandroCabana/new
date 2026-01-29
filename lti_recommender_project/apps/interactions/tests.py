"""
Tests for the interactions API endpoints.
"""
from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status
from lti_recommender_project.apps.interactions.models import UserInteraction
from lti_recommender_project.apps.resources.models import EducationalResource


class UserHistoryViewTests(TestCase):
    """Tests for GET /interactions/user-history/"""
    
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
        
        # Create test resource
        self.resource = EducationalResource.objects.create(
            resource_id='test-resource-1',
            title='Test Resource',
            url='https://example.com/resource1',
            resource_type='video',
            lti_context_id='test-context'
        )
        
        # Create test interactions
        UserInteraction.objects.create(
            lti_user_id=str(self.user.id),
            lti_context_id='test-context',
            resource=self.resource,
            interaction_type='viewed',
            time_spent=120.0
        )
    
    def test_user_history_authenticated(self):
        """Test that authenticated user can access history."""
        response = self.client.get('/interactions/user-history/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertEqual(response.data['total'], 1)
    
    def test_user_history_unauthenticated(self):
        """Test that unauthenticated request returns 401."""
        self.client.force_authenticate(user=None)
        response = self.client.get('/interactions/user-history/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_user_history_pagination(self):
        """Test pagination works correctly."""
        # Create more interactions
        for i in range(25):
            UserInteraction.objects.create(
                lti_user_id=str(self.user.id),
                lti_context_id='test-context',
                resource=self.resource,
                interaction_type='viewed',
                time_spent=float(i * 10)
            )
        
        response = self.client.get('/interactions/user-history/?page=1&page_size=10')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 10)
        self.assertEqual(response.data['total'], 26)  # 1 from setUp + 25 new


class UserStatsViewTests(TestCase):
    """Tests for GET /interactions/user-stats/"""
    
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
        
        # Create test resources
        self.resource1 = EducationalResource.objects.create(
            resource_id='test-resource-1',
            title='Video Resource',
            url='https://example.com/video',
            resource_type='video',
            lti_context_id='test-context'
        )
        self.resource2 = EducationalResource.objects.create(
            resource_id='test-resource-2',
            title='PDF Resource',
            url='https://example.com/pdf',
            resource_type='pdf',
            lti_context_id='test-context'
        )
        
        # Create interactions with different stats
        UserInteraction.objects.create(
            lti_user_id=str(self.user.id),
            lti_context_id='test-context',
            resource=self.resource1,
            interaction_type='viewed',
            time_spent=300.0,
            rating=5
        )
        UserInteraction.objects.create(
            lti_user_id=str(self.user.id),
            lti_context_id='test-context',
            resource=self.resource2,
            interaction_type='viewed',
            time_spent=150.0,
            rating=3
        )
    
    def test_user_stats_returns_correct_counts(self):
        """Test that stats are calculated correctly."""
        response = self.client.get('/interactions/user-stats/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_interactions'], 2)
        self.assertEqual(response.data['total_resources'], 2)
        self.assertEqual(response.data['total_time_spent'], 450.0)
        self.assertEqual(response.data['average_rating'], 4.0)
    
    def test_user_stats_unauthenticated(self):
        """Test that unauthenticated request returns 401."""
        self.client.force_authenticate(user=None)
        response = self.client.get('/interactions/user-stats/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class DataPreviewViewTests(TestCase):
    """Tests for POST /interactions/preview/"""
    
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
        
        # Create an existing resource for "update" scenario
        self.existing_resource = EducationalResource.objects.create(
            resource_id='existing-resource',
            title='Existing Resource',
            url='https://existing.com/resource',
            resource_type='article',
            lti_context_id='test-context'
        )
    
    def test_preview_returns_expected_format(self):
        """Test that preview returns correct structure."""
        data = {
            "userID": self.user.id,
            "associatedPLE": "test-context",
            "trackedDataList": [
                {
                    "activityType": "video",
                    "associatedURL": "https://new-resource.com/video",
                    "associatedDomains": ["education"],
                    "associatedKeywords": ["python", "tutorial"],
                    "startTime": "2026-01-20T10:00:00Z",
                    "endTime": "2026-01-20T10:05:00Z"
                }
            ]
        }
        
        response = self.client.post('/interactions/preview/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('resources_to_create', response.data)
        self.assertIn('interactions_to_create', response.data)
        self.assertIn('summary', response.data)
        self.assertEqual(response.data['summary']['total_items'], 1)
        self.assertEqual(response.data['summary']['new_resources'], 1)
    
    def test_preview_does_not_save(self):
        """Test that preview does NOT create any database records."""
        initial_resource_count = EducationalResource.objects.count()
        initial_interaction_count = UserInteraction.objects.count()
        
        data = {
            "userID": self.user.id,
            "associatedPLE": "test-context",
            "trackedDataList": [
                {
                    "activityType": "video",
                    "associatedURL": "https://brand-new.com/video",
                    "startTime": "2026-01-20T10:00:00Z",
                    "endTime": "2026-01-20T10:05:00Z"
                }
            ]
        }
        
        response = self.client.post('/interactions/preview/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify no new records were created
        self.assertEqual(EducationalResource.objects.count(), initial_resource_count)
        self.assertEqual(UserInteraction.objects.count(), initial_interaction_count)
    
    def test_preview_identifies_existing_resources(self):
        """Test that preview correctly identifies existing resources."""
        data = {
            "userID": self.user.id,
            "associatedPLE": "test-context",
            "trackedDataList": [
                {
                    "activityType": "article",
                    "associatedURL": "https://existing.com/resource",
                    "startTime": "2026-01-20T10:00:00Z",
                    "endTime": "2026-01-20T10:05:00Z"
                }
            ]
        }
        
        response = self.client.post('/interactions/preview/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['summary']['existing_resources'], 1)
        self.assertEqual(response.data['summary']['new_resources'], 0)
    
    def test_preview_unauthenticated(self):
        """Test that unauthenticated request returns 401."""
        self.client.force_authenticate(user=None)
        data = {"userID": 1, "associatedPLE": "test", "trackedDataList": []}
        response = self.client.post('/interactions/preview/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
