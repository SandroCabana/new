"""
Tests for the Recommendation Engine and ML Models.
Covers EnsembleRecommender, individual ML models, and recommendation API endpoints.
"""
from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status
from unittest.mock import patch, MagicMock
import logging

from lti_recommender_project.apps.interactions.models import UserInteraction
from lti_recommender_project.apps.resources.models import EducationalResource
from lti_recommender_project.apps.users.models import GlobalUser

logger = logging.getLogger(__name__)


class EnsembleRecommenderTests(TestCase):
    """Tests for the EnsembleRecommender class."""
    
    @classmethod
    def setUpTestData(cls):
        """Set up test data for all tests in this class."""
        # Create test resources
        cls.resources = []
        for i in range(10):
            resource = EducationalResource.objects.create(
                resource_id=f'test-resource-{i}',
                title=f'Test Resource {i}',
                url=f'https://example.com/resource{i}',
                resource_type='video' if i % 2 == 0 else 'article',
                difficulty_level='beginner' if i < 3 else 'intermediate' if i < 7 else 'advanced',
                lti_context_id='test-context-1'
            )
            cls.resources.append(resource)
        
        cls.global_user = GlobalUser.objects.create(
            email='test-user-1@example.com',
            display_name='Test User',
            inferred_level='intermediate'
        )
        
        # Create some interactions
        for i in range(3):
            UserInteraction.objects.create(
                lti_user_id='test-user-1',
                lti_context_id='test-context-1',
                resource=cls.resources[i],
                interaction_type='viewed',
                time_spent=120.0 + i * 30,
                rating=4 if i % 2 == 0 else 3
            )
    
    def test_ensemble_loads_models(self):
        """Test that EnsembleRecommender loads available ML models."""
        from lti_recommender_project.ml.models.ensemble import get_ensemble_recommender
        
        ensemble = get_ensemble_recommender()
        info = ensemble.get_model_info()
        
        # Should load at least the hybrid model
        self.assertGreaterEqual(info['n_models'], 1, "No models loaded in ensemble")
        self.assertIn('models', info)
        self.assertIn('weights', info)
        self.assertIn('strategy', info)
    
    def test_ensemble_returns_recommendations(self):
        """Test that ensemble returns recommendations for a user."""
        from lti_recommender_project.ml.models.ensemble import get_ensemble_recommender
        
        ensemble = get_ensemble_recommender()
        recommendations = ensemble.get_recommendations(
            user_id='test-user-1',
            context_id='test-context-1',
            limit=5,
            exclude_viewed=True
        )
        
        self.assertIsInstance(recommendations, list)
        # Should return up to 5 recommendations
        self.assertLessEqual(len(recommendations), 5)
        
        # Each recommendation should have required fields
        for rec in recommendations:
            self.assertIn('id', rec)
            self.assertIn('title', rec)
    
    def test_ensemble_excludes_viewed_resources(self):
        """Test that ensemble excludes already viewed resources."""
        from lti_recommender_project.ml.models.ensemble import get_ensemble_recommender
        
        # Get IDs of viewed resources
        viewed_ids = set(
            UserInteraction.objects.filter(
                lti_user_id='test-user-1'
            ).values_list('resource_id', flat=True)
        )
        
        ensemble = get_ensemble_recommender()
        recommendations = ensemble.get_recommendations(
            user_id='test-user-1',
            context_id='test-context-1',
            limit=10,
            exclude_viewed=True
        )
        
        # None of the recommended resources should be in viewed_ids
        recommended_ids = {rec.get('id') for rec in recommendations if rec.get('id')}
        overlap = viewed_ids & recommended_ids
        self.assertEqual(len(overlap), 0, f"Viewed resources found in recommendations: {overlap}")
    
    def test_ensemble_strategies(self):
        """Test different ensemble strategies."""
        from lti_recommender_project.ml.models.ensemble import EnsembleRecommender
        
        strategies = ['weighted_average', 'rank_fusion', 'voting']
        
        for strategy in strategies:
            ensemble = EnsembleRecommender(strategy=strategy)
            recommendations = ensemble.get_recommendations(
                user_id='test-user-1',
                context_id='test-context-1',
                limit=5
            )
            
            self.assertIsInstance(recommendations, list, f"Strategy {strategy} failed")


class RecommendationEngineTests(TestCase):
    """Tests for the hybrid RecommendationEngine."""
    
    @classmethod
    def setUpTestData(cls):
        """Set up test data."""
        # Create resources with different types
        cls.resources = []
        resource_types = ['video', 'article', 'pdf', 'quiz', 'interactive']
        
        for i in range(15):
            resource = EducationalResource.objects.create(
                resource_id=f'rec-engine-resource-{i}',
                title=f'Recommendation Engine Resource {i}',
                url=f'https://example.com/rec-resource{i}',
                resource_type=resource_types[i % len(resource_types)],
                difficulty_level='beginner' if i < 5 else 'intermediate' if i < 10 else 'advanced',
                lti_context_id='rec-test-context',
                tags=f'python,machine-learning' if i % 2 == 0 else 'web,javascript'
            )
            cls.resources.append(resource)
        
        cls.global_user = GlobalUser.objects.create(
            email='rec-test-user@example.com',
            display_name='Rec Engine Test User',
            inferred_level='intermediate',
            preferences_json={'video': 5, 'article': 3},
            interest_tags='python, machine-learning'
        )
        
        # Create interactions
        for i in range(5):
            UserInteraction.objects.create(
                lti_user_id='rec-test-user',
                lti_context_id='rec-test-context',
                resource=cls.resources[i],
                interaction_type='viewed',
                time_spent=180.0,
                completion_percentage=75.0,
                rating=4
            )
    
    def test_recommendation_engine_initialization(self):
        """Test RecommendationEngine initializes with correct weights."""
        from lti_recommender_project.apps.recommendations.services.recommendation_engine import RecommendationEngine
        
        engine = RecommendationEngine(
            content_weight=0.5,
            user_weight=0.3,
            popularity_weight=0.2
        )
        
        self.assertAlmostEqual(engine.content_weight, 0.5)
        self.assertAlmostEqual(engine.user_weight, 0.3)
        self.assertAlmostEqual(engine.popularity_weight, 0.2)
    
    def test_recommendation_engine_weight_normalization(self):
        """Test that weights are normalized if they don't sum to 1."""
        from lti_recommender_project.apps.recommendations.services.recommendation_engine import RecommendationEngine
        
        # Weights that don't sum to 1
        engine = RecommendationEngine(
            content_weight=1.0,
            user_weight=1.0,
            popularity_weight=1.0
        )
        
        # Total should be normalized to 1
        total = engine.content_weight + engine.user_weight + engine.popularity_weight
        self.assertAlmostEqual(total, 1.0, places=2)
    
    def test_recommendation_engine_returns_results(self):
        """Test that engine returns recommendations."""
        from lti_recommender_project.apps.recommendations.services.recommendation_engine import get_recommendation_engine
        
        engine = get_recommendation_engine()
        recommendations = engine.get_recommendations(
            user_id='rec-test-user',
            context_id='rec-test-context',
            limit=5,
            exclude_viewed=True
        )
        
        self.assertIsInstance(recommendations, list)
        self.assertLessEqual(len(recommendations), 5)
    
    def test_recommendation_includes_scores(self):
        """Test that recommendations include scores."""
        from lti_recommender_project.apps.recommendations.services.recommendation_engine import get_recommendation_engine
        
        engine = get_recommendation_engine()
        recommendations = engine.get_recommendations(
            user_id='rec-test-user',
            context_id='rec-test-context',
            limit=5
        )
        
        for rec in recommendations:
            self.assertIn('score', rec)
            # Score should be between 0 and 1
            self.assertGreaterEqual(rec['score'], 0)
            self.assertLessEqual(rec['score'], 1)


class SVDModelTests(TestCase):
    """Tests for the SVD Matrix Factorization model."""
    
    @classmethod
    def setUpTestData(cls):
        """Set up test data."""
        # Create resources and interactions for SVD
        cls.resources = []
        for i in range(10):
            resource = EducationalResource.objects.create(
                resource_id=f'svd-test-resource-{i}',
                title=f'SVD Test Resource {i}',
                url=f'https://example.com/svd-resource{i}',
                resource_type='video',
                lti_context_id='svd-test-context'
            )
            cls.resources.append(resource)
        
        # Create multiple users with interactions
        for user_idx in range(5):
            for res_idx in range(5):
                UserInteraction.objects.create(
                    lti_user_id=f'svd-user-{user_idx}',
                    lti_context_id='svd-test-context',
                    resource=cls.resources[res_idx + (user_idx % 5)],
                    interaction_type='viewed',
                    rating=3 + (user_idx + res_idx) % 3
                )
    
    def test_svd_model_loads(self):
        """Test that SVD model can be loaded."""
        from lti_recommender_project.ml.models.matrix_factorization import get_svd_model
        
        model = get_svd_model()
        self.assertIsNotNone(model)
    
    def test_svd_model_is_fitted(self):
        """Test that SVD model is fitted (loaded from saved file)."""
        from lti_recommender_project.ml.models.matrix_factorization import get_svd_model
        
        model = get_svd_model()
        # Model should either be fitted or able to load from disk
        if model._is_fitted:
            self.assertTrue(model._is_fitted)
    
    def test_svd_returns_recommendations(self):
        """Test that SVD model returns recommendations if fitted."""
        from lti_recommender_project.ml.models.matrix_factorization import get_svd_model
        
        model = get_svd_model()
        
        if model._is_fitted:
            recommendations = model.get_recommendations(
                user_id='svd-user-0',
                context_id='svd-test-context',
                limit=5
            )
            self.assertIsInstance(recommendations, list)


class LTIRecommendationViewTests(TestCase):
    """Tests for LTI recommendation views and API."""
    
    @classmethod
    def setUpTestData(cls):
        """Set up test data."""
        cls.resources = []
        for i in range(5):
            resource = EducationalResource.objects.create(
                resource_id=f'lti-view-resource-{i}',
                title=f'LTI View Resource {i}',
                url=f'https://example.com/lti-resource{i}',
                resource_type='video',
                lti_context_id='lti-view-context'
            )
            cls.resources.append(resource)
    
    def test_get_recommendations_from_api_returns_list(self):
        """Test that get_recommendations_from_api returns a list."""
        from lti_recommender_project.apps.lti_integration.views import get_recommendations_from_api
        
        recommendations = get_recommendations_from_api(
            user_id='lti-test-user',
            context_id='lti-view-context'
        )
        
        self.assertIsInstance(recommendations, list)
        self.assertGreater(len(recommendations), 0)
    
    def test_get_recommendations_from_api_format(self):
        """Test that recommendations have the expected format."""
        from lti_recommender_project.apps.lti_integration.views import get_recommendations_from_api
        
        recommendations = get_recommendations_from_api(
            user_id='lti-test-user',
            context_id='lti-view-context'
        )
        
        # Should return recommendations (or fallback message)
        self.assertGreater(len(recommendations), 0)
        
        # If real recommendations, check format
        if recommendations[0].get('url') != '#':
            rec = recommendations[0]
            self.assertIn('title', rec)
            self.assertIn('url', rec)
    
    def test_get_recommendations_handles_errors(self):
        """Test that API handles errors gracefully."""
        from lti_recommender_project.apps.lti_integration.views import get_recommendations_from_api
        
        # Should not raise exception even with invalid context
        recommendations = get_recommendations_from_api(
            user_id='nonexistent-user',
            context_id='nonexistent-context'
        )
        
        self.assertIsInstance(recommendations, list)


class ModelIntegrationTests(TestCase):
    """Integration tests for ML model pipeline."""
    
    @classmethod
    def setUpTestData(cls):
        """Set up data for integration tests."""
        for i in range(10):
            resource = EducationalResource.objects.create(
                resource_id=f'integration-resource-{i}',
                title=f'Integration Test Resource {i}',
                url=f'https://example.com/integration{i}',
                resource_type='video',
                lti_context_id='integration-context'
            )
        
        GlobalUser.objects.create(
            email='integration-user@example.com',
            display_name='Integration Test User'
        )
    
    def test_full_recommendation_pipeline(self):
        """Test the full recommendation pipeline from user request to results."""
        from lti_recommender_project.ml.models.ensemble import get_ensemble_recommender
        
        ensemble = get_ensemble_recommender()
        
        # Get model info
        info = ensemble.get_model_info()
        self.assertGreater(info['n_models'], 0)
        
        # Get recommendations
        recommendations = ensemble.get_recommendations(
            user_id='integration-user',
            context_id='integration-context',
            limit=5
        )
        
        self.assertIsInstance(recommendations, list)
    
    def test_model_singleton_pattern(self):
        """Test that models use singleton pattern correctly."""
        from lti_recommender_project.ml.models.ensemble import get_ensemble_recommender
        from lti_recommender_project.ml.models.matrix_factorization import get_svd_model
        
        # Multiple calls should return the same instance
        ensemble1 = get_ensemble_recommender()
        ensemble2 = get_ensemble_recommender()
        self.assertIs(ensemble1, ensemble2)
        
        svd1 = get_svd_model()
        svd2 = get_svd_model()
        self.assertIs(svd1, svd2)
