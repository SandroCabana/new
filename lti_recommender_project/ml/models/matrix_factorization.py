"""
Matrix Factorization Model for Educational Resource Recommendations
Implements SVD-based collaborative filtering using the Surprise library.
"""

import logging
import pickle
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import numpy as np

logger = logging.getLogger(__name__)

# Model save path
MODEL_DIR = Path(__file__).parent.parent / 'saved_models'
MODEL_PATH = MODEL_DIR / 'svd_model.pkl'


class MatrixFactorizationModel:
    """
    Matrix Factorization model using SVD (Singular Value Decomposition).
    
    This model learns latent factors for users and resources to predict
    user-resource interaction scores.
    """
    
    def __init__(
        self,
        n_factors: int = 100,
        n_epochs: int = 20,
        lr_all: float = 0.005,
        reg_all: float = 0.02,
        random_state: int = 42
    ):
        """
        Initialize the SVD model.
        
        Args:
            n_factors: Number of latent factors
            n_epochs: Number of training epochs
            lr_all: Learning rate for all parameters
            reg_all: Regularization term for all parameters
            random_state: Random seed for reproducibility
        """
        self.n_factors = n_factors
        self.n_epochs = n_epochs
        self.lr_all = lr_all
        self.reg_all = reg_all
        self.random_state = random_state
        self.model = None
        self.trainset = None
        self._is_fitted = False
        
    def _prepare_data(self) -> 'Dataset':
        """
        Prepare data from Django models for Surprise library.
        
        Returns:
            Surprise Dataset object
        """
        from surprise import Dataset, Reader
        from lti_recommender_project.apps.interactions.models import UserInteraction
        
        # Collect interaction data
        interactions = UserInteraction.objects.all().values(
            'lti_user_id', 'resource_id', 'rating', 'completion_percentage'
        )
        
        # Build ratings list
        ratings_data = []
        for interaction in interactions:
            # Calculate implicit rating if explicit rating not available
            if interaction['rating']:
                rating = interaction['rating']
            elif interaction['completion_percentage']:
                # Convert completion to 1-5 scale
                rating = 1 + (interaction['completion_percentage'] / 100) * 4
            else:
                # Default implicit rating for viewed items
                rating = 3.0
            
            ratings_data.append((
                str(interaction['lti_user_id']),
                str(interaction['resource_id']),
                float(rating)
            ))
        
        if not ratings_data:
            raise ValueError("No interaction data available for training")
        
        # Create Surprise dataset
        reader = Reader(rating_scale=(1, 5))
        dataset = Dataset.load_from_df(
            __import__('pandas').DataFrame(
                ratings_data, 
                columns=['user', 'item', 'rating']
            ),
            reader
        )
        
        logger.info(f"Prepared {len(ratings_data)} interactions for training")
        return dataset
    
    def fit(self, save_model: bool = True) -> Dict[str, float]:
        """
        Train the SVD model on all available interaction data.
        
        Args:
            save_model: Whether to save the trained model to disk
            
        Returns:
            Dictionary with training metrics
        """
        from surprise import SVD
        from surprise.model_selection import cross_validate
        
        logger.info("Starting SVD model training...")
        
        # Prepare data
        dataset = self._prepare_data()
        
        # Initialize SVD model
        self.model = SVD(
            n_factors=self.n_factors,
            n_epochs=self.n_epochs,
            lr_all=self.lr_all,
            reg_all=self.reg_all,
            random_state=self.random_state
        )
        
        # Cross-validation for metrics
        cv_results = cross_validate(
            self.model, 
            dataset, 
            measures=['RMSE', 'MAE'], 
            cv=5, 
            verbose=False
        )
        
        # Train on full dataset
        self.trainset = dataset.build_full_trainset()
        self.model.fit(self.trainset)
        self._is_fitted = True
        
        # Save model
        if save_model:
            self.save()
        
        metrics = {
            'rmse_mean': float(np.mean(cv_results['test_rmse'])),
            'rmse_std': float(np.std(cv_results['test_rmse'])),
            'mae_mean': float(np.mean(cv_results['test_mae'])),
            'mae_std': float(np.std(cv_results['test_mae'])),
            'n_users': self.trainset.n_users,
            'n_items': self.trainset.n_items,
            'n_ratings': self.trainset.n_ratings,
        }
        
        logger.info(f"Training complete. RMSE: {metrics['rmse_mean']:.4f} (+/- {metrics['rmse_std']:.4f})")
        return metrics
    
    def predict(self, user_id: str, resource_id: int) -> float:
        """
        Predict the rating for a user-resource pair.
        
        Args:
            user_id: LTI user ID
            resource_id: Resource ID
            
        Returns:
            Predicted rating (1-5 scale)
        """
        if not self._is_fitted:
            self.load()
        
        if self.model is None:
            raise ValueError("Model not trained. Call fit() first.")
        
        prediction = self.model.predict(str(user_id), str(resource_id))
        return prediction.est
    
    def get_recommendations(
        self,
        user_id: str,
        context_id: str,
        limit: int = 10,
        exclude_viewed: bool = True
    ) -> List[Dict]:
        """
        Get top-N recommendations for a user.
        
        Args:
            user_id: LTI user ID
            context_id: LTI context ID (for filtering)
            limit: Number of recommendations to return
            exclude_viewed: Whether to exclude already viewed resources
            
        Returns:
            List of resource dictionaries with predicted scores
        """
        from django.db.models import Q
        from lti_recommender_project.apps.resources.models import EducationalResource
        from lti_recommender_project.apps.interactions.models import UserInteraction
        
        if not self._is_fitted:
            self.load()
        
        if self.model is None:
            logger.warning("SVD model not available, returning empty recommendations")
            return []
        
        # Get resources to score
        resources = EducationalResource.objects.filter(
            Q(lti_context_id=context_id) | Q(lti_context_id__isnull=True)
        )
        
        # Exclude viewed resources if requested
        if exclude_viewed:
            viewed_ids = set(
                UserInteraction.objects.filter(
                    lti_user_id=user_id
                ).values_list('resource_id', flat=True)
            )
            resources = resources.exclude(id__in=viewed_ids)
        
        # Score all candidate resources
        scored_resources = []
        for resource in resources:
            try:
                score = self.predict(user_id, resource.id)
                scored_resources.append({
                    'resource': resource,
                    'score': score,
                    'title': resource.title,
                    'url': resource.url,
                    'description': resource.description,
                    'type': resource.resource_type,
                    'difficulty': resource.difficulty_level,
                    'id': resource.id,
                    'source': 'svd'
                })
            except Exception as e:
                logger.debug(f"Could not predict for resource {resource.id}: {e}")
                continue
        
        # Sort by predicted score
        scored_resources.sort(key=lambda x: x['score'], reverse=True)
        
        return scored_resources[:limit]
    
    def save(self):
        """Save the trained model to disk."""
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        
        model_data = {
            'model': self.model,
            'trainset': self.trainset,
            'params': {
                'n_factors': self.n_factors,
                'n_epochs': self.n_epochs,
                'lr_all': self.lr_all,
                'reg_all': self.reg_all,
            }
        }
        
        with open(MODEL_PATH, 'wb') as f:
            pickle.dump(model_data, f)
        
        logger.info(f"Model saved to {MODEL_PATH}")
    
    def load(self) -> bool:
        """
        Load a trained model from disk.
        
        Returns:
            True if model loaded successfully, False otherwise
        """
        if not MODEL_PATH.exists():
            logger.warning(f"No saved model found at {MODEL_PATH}")
            return False
        
        try:
            with open(MODEL_PATH, 'rb') as f:
                model_data = pickle.load(f)
            
            self.model = model_data['model']
            self.trainset = model_data['trainset']
            self._is_fitted = True
            
            logger.info(f"Model loaded from {MODEL_PATH}")
            return True
            
        except Exception as e:
            logger.error(f"Error loading model: {e}")
            return False


# Singleton instance
_svd_model_instance: Optional[MatrixFactorizationModel] = None


def get_svd_model() -> MatrixFactorizationModel:
    """
    Get the singleton instance of the SVD model.
    
    Returns:
        MatrixFactorizationModel instance
    """
    global _svd_model_instance
    
    if _svd_model_instance is None:
        _svd_model_instance = MatrixFactorizationModel()
        # Try to load existing model
        _svd_model_instance.load()
    
    return _svd_model_instance
