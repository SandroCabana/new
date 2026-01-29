"""
Factorization Machines with Context for Educational Recommendations.
Incorporates user, item, and contextual features for predictions.

Reference: Rendle, "Factorization Machines", IEEE ICDM 2010
"""

import logging
import pickle
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import numpy as np

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader

logger = logging.getLogger(__name__)

# Model paths
MODEL_DIR = Path(__file__).parent.parent / 'saved_models'
FM_MODEL_PATH = MODEL_DIR / 'fm_model.pt'
FM_MAPPINGS_PATH = MODEL_DIR / 'fm_mappings.pkl'


class FMDataset(Dataset):
    """Dataset for Factorization Machines with contextual features."""
    
    def __init__(self, features: np.ndarray, targets: np.ndarray):
        self.features = torch.FloatTensor(features)
        self.targets = torch.FloatTensor(targets)
    
    def __len__(self):
        return len(self.targets)
    
    def __getitem__(self, idx):
        return self.features[idx], self.targets[idx]


class FactorizationMachine(nn.Module):
    """
    Factorization Machine model.
    
    Captures feature interactions using factorized parameters.
    y = w0 + sum(wi*xi) + sum(sum(<vi, vj>*xi*xj))
    """
    
    def __init__(self, n_features: int, k: int = 8):
        super(FactorizationMachine, self).__init__()
        
        self.n_features = n_features
        self.k = k  # Latent factor dimension
        
        # Global bias
        self.w0 = nn.Parameter(torch.zeros(1))
        
        # First-order weights
        self.w = nn.Parameter(torch.zeros(n_features))
        
        # Second-order factorized weights (V matrix)
        self.V = nn.Parameter(torch.randn(n_features, k) * 0.01)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass.
        
        Args:
            x: Feature tensor [batch_size, n_features]
            
        Returns:
            Predictions [batch_size]
        """
        # First-order: w0 + sum(wi*xi)
        linear = self.w0 + torch.sum(x * self.w, dim=1)
        
        # Second-order interaction: 0.5 * sum((sum(vi*xi))^2 - sum(vi^2*xi^2))
        # Efficient computation using: sum_pairs <vi,vj>*xi*xj = 0.5 * (||sum(vi*xi)||^2 - sum(||vi*xi||^2))
        
        # [batch, n_features, k]
        vx = x.unsqueeze(-1) * self.V.unsqueeze(0)
        
        # sum(vi*xi) for each factor k: [batch, k]
        sum_vx = torch.sum(vx, dim=1)
        
        # sum(vi^2 * xi^2) for each factor k: [batch, k]
        sum_vx_sq = torch.sum(vx ** 2, dim=1)
        
        # 0.5 * sum_k[(sum_vx_k)^2 - sum_vx_sq_k]
        interaction = 0.5 * torch.sum(sum_vx ** 2 - sum_vx_sq, dim=1)
        
        # Scale output to rating range [1, 5]
        output = linear + interaction
        return 1 + 4 * torch.sigmoid(output)


class ContextualFM:
    """
    Wrapper for Factorization Machine with contextual features.
    
    Features include:
    - User ID (one-hot)
    - Item ID (one-hot)
    - Resource type (one-hot)
    - Difficulty level (one-hot)
    - Time of day (categorical)
    - Day of week (categorical)
    """
    
    def __init__(
        self,
        k: int = 8,
        lr: float = 0.01,
        reg: float = 0.001,
        batch_size: int = 32,
        n_epochs: int = 50,
        device: str = 'auto'
    ):
        self.k = k
        self.lr = lr
        self.reg = reg
        self.batch_size = batch_size
        self.n_epochs = n_epochs
        
        if device == 'auto':
            self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        else:
            self.device = torch.device(device)
        
        self.model = None
        
        # Feature mappings
        self.user_id_map = {}
        self.item_id_map = {}
        self.resource_type_map = {}
        self.difficulty_map = {'beginner': 0, 'intermediate': 1, 'advanced': 2}
        
        self.n_users = 0
        self.n_items = 0
        self.n_resource_types = 0
        self.n_features = 0
        
        self._is_fitted = False
    
    def _build_feature_vector(
        self,
        user_idx: int,
        item_idx: int,
        resource_type_idx: int,
        difficulty_idx: int,
        hour: int = 12,
        day_of_week: int = 1
    ) -> np.ndarray:
        """Build sparse feature vector for FM input."""
        # Feature dimensions
        # [user_one_hot | item_one_hot | type_one_hot | difficulty_one_hot | hour_bucket | day_of_week]
        
        features = np.zeros(self.n_features, dtype=np.float32)
        offset = 0
        
        # User one-hot
        if 0 <= user_idx < self.n_users:
            features[offset + user_idx] = 1.0
        offset += self.n_users
        
        # Item one-hot
        if 0 <= item_idx < self.n_items:
            features[offset + item_idx] = 1.0
        offset += self.n_items
        
        # Resource type one-hot
        if 0 <= resource_type_idx < self.n_resource_types:
            features[offset + resource_type_idx] = 1.0
        offset += self.n_resource_types
        
        # Difficulty one-hot (3 levels)
        if 0 <= difficulty_idx < 3:
            features[offset + difficulty_idx] = 1.0
        offset += 3
        
        # Hour bucket (4 buckets: night, morning, afternoon, evening)
        hour_bucket = hour // 6
        features[offset + hour_bucket] = 1.0
        offset += 4
        
        # Day of week one-hot
        features[offset + day_of_week] = 1.0
        
        return features
    
    def _prepare_data(self) -> Tuple[np.ndarray, np.ndarray]:
        """Prepare training data with contextual features."""
        from lti_recommender_project.apps.interactions.models import UserInteraction
        from lti_recommender_project.apps.resources.models import EducationalResource
        
        interactions = list(UserInteraction.objects.select_related('resource').all())
        
        if not interactions:
            raise ValueError("No interaction data available")
        
        # Build mappings
        unique_users = sorted(set(i.lti_user_id for i in interactions))
        unique_items = sorted(set(i.resource_id for i in interactions))
        unique_types = sorted(set(i.resource.resource_type for i in interactions if i.resource))
        
        self.user_id_map = {uid: idx for idx, uid in enumerate(unique_users)}
        self.item_id_map = {iid: idx for idx, iid in enumerate(unique_items)}
        self.resource_type_map = {rt: idx for idx, rt in enumerate(unique_types)}
        
        self.n_users = len(self.user_id_map)
        self.n_items = len(self.item_id_map)
        self.n_resource_types = len(self.resource_type_map)
        
        # Calculate total feature dimensions
        self.n_features = (
            self.n_users +      # User one-hot
            self.n_items +      # Item one-hot
            self.n_resource_types +  # Type one-hot
            3 +                 # Difficulty (3 levels)
            4 +                 # Hour bucket (4 buckets)
            7                   # Day of week
        )
        
        features_list = []
        targets_list = []
        
        for interaction in interactions:
            user_idx = self.user_id_map.get(interaction.lti_user_id, -1)
            item_idx = self.item_id_map.get(interaction.resource_id, -1)
            
            resource_type = interaction.resource.resource_type if interaction.resource else 'unknown'
            resource_type_idx = self.resource_type_map.get(resource_type, 0)
            
            difficulty = interaction.resource.difficulty_level if interaction.resource else 'intermediate'
            difficulty_idx = self.difficulty_map.get(difficulty, 1)
            
            hour = interaction.timestamp.hour if interaction.timestamp else 12
            day_of_week = interaction.timestamp.weekday() if interaction.timestamp else 1
            
            # Build feature vector
            feature_vec = self._build_feature_vector(
                user_idx, item_idx, resource_type_idx, difficulty_idx, hour, day_of_week
            )
            
            # Target rating
            if interaction.rating:
                rating = float(interaction.rating)
            elif interaction.completion_percentage:
                rating = 1.0 + (interaction.completion_percentage / 100.0) * 4.0
            else:
                rating = 3.0
            
            features_list.append(feature_vec)
            targets_list.append(rating)
        
        logger.info(f"Prepared {len(features_list)} samples with {self.n_features} features")
        return np.array(features_list), np.array(targets_list)
    
    def fit(self, save_model: bool = True) -> Dict:
        """Train the Factorization Machine model."""
        logger.info("Starting Factorization Machine training...")
        
        features, targets = self._prepare_data()
        
        if len(features) < 10:
            return {'error': 'Insufficient data'}
        
        # Create model
        self.model = FactorizationMachine(
            n_features=self.n_features,
            k=self.k
        ).to(self.device)
        
        # Dataset and DataLoader
        dataset = FMDataset(features, targets)
        dataloader = DataLoader(
            dataset,
            batch_size=min(self.batch_size, len(features)),
            shuffle=True,
            num_workers=0
        )
        
        # Loss and optimizer with L2 regularization
        criterion = nn.MSELoss()
        optimizer = optim.Adam(self.model.parameters(), lr=self.lr, weight_decay=self.reg)
        
        # Training loop
        epoch_losses = []
        for epoch in range(self.n_epochs):
            self.model.train()
            total_loss = 0
            n_batches = 0
            
            for feat_batch, target_batch in dataloader:
                feat_batch = feat_batch.to(self.device)
                target_batch = target_batch.to(self.device)
                
                optimizer.zero_grad()
                predictions = self.model(feat_batch)
                loss = criterion(predictions, target_batch)
                loss.backward()
                optimizer.step()
                
                total_loss += loss.item()
                n_batches += 1
            
            avg_loss = total_loss / n_batches
            epoch_losses.append(avg_loss)
            
            if (epoch + 1) % 10 == 0:
                logger.info(f"Epoch {epoch + 1}/{self.n_epochs}, Loss: {avg_loss:.4f}")
        
        self._is_fitted = True
        
        # Calculate final RMSE
        self.model.eval()
        with torch.no_grad():
            feat_tensor = torch.FloatTensor(features).to(self.device)
            target_tensor = torch.FloatTensor(targets).to(self.device)
            predictions = self.model(feat_tensor)
            mse = criterion(predictions, target_tensor)
            rmse = torch.sqrt(mse).item()
        
        if save_model:
            self.save()
        
        metrics = {
            'final_loss': epoch_losses[-1],
            'rmse': rmse,
            'n_features': self.n_features,
            'n_users': self.n_users,
            'n_items': self.n_items,
            'n_samples': len(features),
            'device': str(self.device),
        }
        
        logger.info(f"Training complete. RMSE: {rmse:.4f}")
        return metrics
    
    def predict(self, user_id: str, resource_id: int, context: Optional[Dict] = None) -> float:
        """Predict rating for user-item pair with context."""
        if not self._is_fitted:
            self.load()
        
        if self.model is None:
            return 3.0
        
        from lti_recommender_project.apps.resources.models import EducationalResource
        
        user_idx = self.user_id_map.get(user_id, -1)
        item_idx = self.item_id_map.get(resource_id, -1)
        
        try:
            resource = EducationalResource.objects.get(id=resource_id)
            resource_type_idx = self.resource_type_map.get(resource.resource_type, 0)
            difficulty_idx = self.difficulty_map.get(resource.difficulty_level, 1)
        except EducationalResource.DoesNotExist:
            resource_type_idx = 0
            difficulty_idx = 1
        
        hour = context.get('hour', 12) if context else 12
        day_of_week = context.get('day_of_week', 1) if context else 1
        
        feature_vec = self._build_feature_vector(
            user_idx, item_idx, resource_type_idx, difficulty_idx, hour, day_of_week
        )
        
        self.model.eval()
        with torch.no_grad():
            feat_tensor = torch.FloatTensor(feature_vec).unsqueeze(0).to(self.device)
            prediction = self.model(feat_tensor)
        
        return prediction.item()
    
    def get_recommendations(
        self,
        user_id: str,
        context_id: str,
        limit: int = 10,
        exclude_viewed: bool = True
    ) -> List[Dict]:
        """Get recommendations with contextual scoring."""
        from django.db.models import Q
        from datetime import datetime
        from lti_recommender_project.apps.resources.models import EducationalResource
        from lti_recommender_project.apps.interactions.models import UserInteraction
        
        if not self._is_fitted:
            self.load()
        
        if self.model is None:
            return []
        
        # Current context
        now = datetime.now()
        context = {
            'hour': now.hour,
            'day_of_week': now.weekday()
        }
        
        # Get viewed items
        viewed_ids = set()
        if exclude_viewed:
            viewed_ids = set(
                UserInteraction.objects.filter(
                    lti_user_id=user_id
                ).values_list('resource_id', flat=True)
            )
        
        # Score items in model vocabulary
        user_idx = self.user_id_map.get(user_id, -1)
        
        scored_items = []
        
        self.model.eval()
        with torch.no_grad():
            for item_id, item_idx in self.item_id_map.items():
                if item_id in viewed_ids:
                    continue
                
                try:
                    resource = EducationalResource.objects.get(id=item_id)
                except EducationalResource.DoesNotExist:
                    continue
                
                resource_type_idx = self.resource_type_map.get(resource.resource_type, 0)
                difficulty_idx = self.difficulty_map.get(resource.difficulty_level, 1)
                
                feature_vec = self._build_feature_vector(
                    user_idx, item_idx, resource_type_idx, difficulty_idx,
                    context['hour'], context['day_of_week']
                )
                
                feat_tensor = torch.FloatTensor(feature_vec).unsqueeze(0).to(self.device)
                score = self.model(feat_tensor).item()
                
                scored_items.append((resource, score))
        
        # Sort by score
        scored_items.sort(key=lambda x: x[1], reverse=True)
        
        # Build recommendations
        recommendations = []
        for resource, score in scored_items[:limit]:
            recommendations.append({
                'resource': resource,
                'score': score,
                'title': resource.title,
                'url': resource.url,
                'description': resource.description,
                'type': resource.resource_type,
                'difficulty': resource.difficulty_level,
                'id': resource.id,
                'source': 'fm_contextual'
            })
        
        return recommendations
    
    def save(self):
        """Save model and mappings."""
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        
        torch.save({
            'model_state_dict': self.model.state_dict(),
            'n_features': self.n_features,
            'k': self.k,
        }, FM_MODEL_PATH)
        
        mappings = {
            'user_id_map': self.user_id_map,
            'item_id_map': self.item_id_map,
            'resource_type_map': self.resource_type_map,
            'difficulty_map': self.difficulty_map,
            'n_users': self.n_users,
            'n_items': self.n_items,
            'n_resource_types': self.n_resource_types,
            'n_features': self.n_features,
        }
        with open(FM_MAPPINGS_PATH, 'wb') as f:
            pickle.dump(mappings, f)
        
        logger.info(f"FM model saved to {FM_MODEL_PATH}")
    
    def load(self) -> bool:
        """Load model from disk."""
        if not FM_MODEL_PATH.exists() or not FM_MAPPINGS_PATH.exists():
            logger.warning("No saved FM model found")
            return False
        
        try:
            with open(FM_MAPPINGS_PATH, 'rb') as f:
                mappings = pickle.load(f)
            
            self.user_id_map = mappings['user_id_map']
            self.item_id_map = mappings['item_id_map']
            self.resource_type_map = mappings['resource_type_map']
            self.difficulty_map = mappings['difficulty_map']
            self.n_users = mappings['n_users']
            self.n_items = mappings['n_items']
            self.n_resource_types = mappings['n_resource_types']
            self.n_features = mappings['n_features']
            
            checkpoint = torch.load(FM_MODEL_PATH, map_location=self.device)
            
            self.model = FactorizationMachine(
                n_features=checkpoint['n_features'],
                k=checkpoint['k']
            ).to(self.device)
            
            self.model.load_state_dict(checkpoint['model_state_dict'])
            self.model.eval()
            self._is_fitted = True
            
            logger.info(f"FM model loaded from {FM_MODEL_PATH}")
            return True
            
        except Exception as e:
            logger.error(f"Error loading FM model: {e}")
            return False


# Singleton
_fm_model_instance: Optional[ContextualFM] = None


def get_fm_model() -> ContextualFM:
    """Get singleton FM model instance."""
    global _fm_model_instance
    
    if _fm_model_instance is None:
        _fm_model_instance = ContextualFM()
        _fm_model_instance.load()
    
    return _fm_model_instance
