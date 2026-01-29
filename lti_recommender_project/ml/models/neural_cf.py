"""
Neural Collaborative Filtering (NCF) Model for Educational Resource Recommendations.
Implements a hybrid of Generalized Matrix Factorization (GMF) and Multi-Layer Perceptron (MLP).

Reference: He et al., "Neural Collaborative Filtering", WWW 2017
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

# Model save path
MODEL_DIR = Path(__file__).parent.parent / 'saved_models'
NCF_MODEL_PATH = MODEL_DIR / 'ncf_model.pt'
NCF_MAPPINGS_PATH = MODEL_DIR / 'ncf_mappings.pkl'


class InteractionDataset(Dataset):
    """PyTorch Dataset for user-item interactions."""
    
    def __init__(self, user_ids: np.ndarray, item_ids: np.ndarray, ratings: np.ndarray):
        self.user_ids = torch.LongTensor(user_ids)
        self.item_ids = torch.LongTensor(item_ids)
        self.ratings = torch.FloatTensor(ratings)
    
    def __len__(self):
        return len(self.ratings)
    
    def __getitem__(self, idx):
        return self.user_ids[idx], self.item_ids[idx], self.ratings[idx]


class NCFModel(nn.Module):
    """
    Neural Collaborative Filtering model combining GMF and MLP.
    
    Architecture:
    - GMF: Element-wise product of user and item embeddings
    - MLP: Concatenated embeddings through multiple dense layers
    - NeuMF: Concatenation of GMF and MLP outputs
    """
    
    def __init__(
        self,
        n_users: int,
        n_items: int,
        embedding_dim: int = 32,
        mlp_layers: List[int] = [64, 32, 16],
        dropout: float = 0.2
    ):
        super(NCFModel, self).__init__()
        
        self.n_users = n_users
        self.n_items = n_items
        self.embedding_dim = embedding_dim
        
        # GMF embeddings
        self.gmf_user_embedding = nn.Embedding(n_users, embedding_dim)
        self.gmf_item_embedding = nn.Embedding(n_items, embedding_dim)
        
        # MLP embeddings (larger for richer representations)
        mlp_embedding_dim = mlp_layers[0] // 2
        self.mlp_user_embedding = nn.Embedding(n_users, mlp_embedding_dim)
        self.mlp_item_embedding = nn.Embedding(n_items, mlp_embedding_dim)
        
        # MLP layers
        mlp_modules = []
        input_size = mlp_layers[0]
        for layer_size in mlp_layers[1:]:
            mlp_modules.append(nn.Linear(input_size, layer_size))
            mlp_modules.append(nn.ReLU())
            mlp_modules.append(nn.Dropout(dropout))
            input_size = layer_size
        self.mlp = nn.Sequential(*mlp_modules)
        
        # Final prediction layer
        # GMF output (embedding_dim) + MLP output (last mlp layer size)
        final_input_size = embedding_dim + mlp_layers[-1]
        self.final_layer = nn.Linear(final_input_size, 1)
        
        # Initialize weights
        self._init_weights()
    
    def _init_weights(self):
        """Initialize embeddings and layers."""
        nn.init.normal_(self.gmf_user_embedding.weight, std=0.01)
        nn.init.normal_(self.gmf_item_embedding.weight, std=0.01)
        nn.init.normal_(self.mlp_user_embedding.weight, std=0.01)
        nn.init.normal_(self.mlp_item_embedding.weight, std=0.01)
        
        for m in self.mlp:
            if isinstance(m, nn.Linear):
                nn.init.xavier_uniform_(m.weight)
                nn.init.zeros_(m.bias)
        
        nn.init.xavier_uniform_(self.final_layer.weight)
        nn.init.zeros_(self.final_layer.bias)
    
    def forward(self, user_ids: torch.Tensor, item_ids: torch.Tensor) -> torch.Tensor:
        """
        Forward pass of NCF.
        
        Args:
            user_ids: Tensor of user indices
            item_ids: Tensor of item indices
            
        Returns:
            Predicted ratings (0-5 scale)
        """
        # GMF part
        gmf_user = self.gmf_user_embedding(user_ids)
        gmf_item = self.gmf_item_embedding(item_ids)
        gmf_output = gmf_user * gmf_item  # Element-wise product
        
        # MLP part
        mlp_user = self.mlp_user_embedding(user_ids)
        mlp_item = self.mlp_item_embedding(item_ids)
        mlp_input = torch.cat([mlp_user, mlp_item], dim=-1)
        mlp_output = self.mlp(mlp_input)
        
        # Combine GMF and MLP
        combined = torch.cat([gmf_output, mlp_output], dim=-1)
        prediction = self.final_layer(combined)
        
        # Scale to 1-5 rating range using sigmoid
        prediction = 1 + 4 * torch.sigmoid(prediction)
        
        return prediction.squeeze()


class NeuralCFModel:
    """
    Wrapper class for NCF model with training and inference methods.
    """
    
    def __init__(
        self,
        embedding_dim: int = 32,
        mlp_layers: List[int] = [64, 32, 16],
        dropout: float = 0.2,
        lr: float = 0.001,
        batch_size: int = 64,
        n_epochs: int = 20,
        device: str = 'auto'
    ):
        self.embedding_dim = embedding_dim
        self.mlp_layers = mlp_layers
        self.dropout = dropout
        self.lr = lr
        self.batch_size = batch_size
        self.n_epochs = n_epochs
        
        # Set device
        if device == 'auto':
            self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        else:
            self.device = torch.device(device)
        
        self.model = None
        self.user_id_map = {}
        self.item_id_map = {}
        self.reverse_user_map = {}
        self.reverse_item_map = {}
        self._is_fitted = False
    
    def _prepare_data(self) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Prepare data from Django models."""
        from lti_recommender_project.apps.interactions.models import UserInteraction
        
        interactions = list(UserInteraction.objects.all().values(
            'lti_user_id', 'resource_id', 'rating', 'completion_percentage'
        ))
        
        if not interactions:
            raise ValueError("No interaction data available")
        
        # Build ID mappings
        unique_users = sorted(set(i['lti_user_id'] for i in interactions))
        unique_items = sorted(set(i['resource_id'] for i in interactions))
        
        self.user_id_map = {uid: idx for idx, uid in enumerate(unique_users)}
        self.item_id_map = {iid: idx for idx, iid in enumerate(unique_items)}
        self.reverse_user_map = {idx: uid for uid, idx in self.user_id_map.items()}
        self.reverse_item_map = {idx: iid for iid, idx in self.item_id_map.items()}
        
        # Convert to arrays
        user_ids = []
        item_ids = []
        ratings = []
        
        for interaction in interactions:
            user_idx = self.user_id_map[interaction['lti_user_id']]
            item_idx = self.item_id_map[interaction['resource_id']]
            
            if interaction['rating']:
                rating = float(interaction['rating'])
            elif interaction['completion_percentage']:
                rating = 1.0 + (interaction['completion_percentage'] / 100.0) * 4.0
            else:
                rating = 3.0
            
            user_ids.append(user_idx)
            item_ids.append(item_idx)
            ratings.append(rating)
        
        logger.info(f"Prepared {len(ratings)} interactions, {len(self.user_id_map)} users, {len(self.item_id_map)} items")
        
        return np.array(user_ids), np.array(item_ids), np.array(ratings)
    
    def fit(self, save_model: bool = True) -> Dict:
        """
        Train the NCF model.
        
        Returns:
            Dictionary with training metrics
        """
        logger.info("Starting NCF model training...")
        
        # Prepare data
        user_ids, item_ids, ratings = self._prepare_data()
        
        n_users = len(self.user_id_map)
        n_items = len(self.item_id_map)
        
        # Create model
        self.model = NCFModel(
            n_users=n_users,
            n_items=n_items,
            embedding_dim=self.embedding_dim,
            mlp_layers=self.mlp_layers,
            dropout=self.dropout
        ).to(self.device)
        
        # Create dataset and dataloader
        dataset = InteractionDataset(user_ids, item_ids, ratings)
        dataloader = DataLoader(
            dataset, 
            batch_size=self.batch_size, 
            shuffle=True,
            num_workers=0
        )
        
        # Loss and optimizer
        criterion = nn.MSELoss()
        optimizer = optim.Adam(self.model.parameters(), lr=self.lr)
        
        # Training loop
        epoch_losses = []
        for epoch in range(self.n_epochs):
            self.model.train()
            total_loss = 0
            n_batches = 0
            
            for user_batch, item_batch, rating_batch in dataloader:
                user_batch = user_batch.to(self.device)
                item_batch = item_batch.to(self.device)
                rating_batch = rating_batch.to(self.device)
                
                optimizer.zero_grad()
                predictions = self.model(user_batch, item_batch)
                loss = criterion(predictions, rating_batch)
                loss.backward()
                optimizer.step()
                
                total_loss += loss.item()
                n_batches += 1
            
            avg_loss = total_loss / n_batches
            epoch_losses.append(avg_loss)
            
            if (epoch + 1) % 5 == 0:
                logger.info(f"Epoch {epoch + 1}/{self.n_epochs}, Loss: {avg_loss:.4f}")
        
        self._is_fitted = True
        
        # Calculate final RMSE
        self.model.eval()
        with torch.no_grad():
            all_users = torch.LongTensor(user_ids).to(self.device)
            all_items = torch.LongTensor(item_ids).to(self.device)
            all_ratings = torch.FloatTensor(ratings).to(self.device)
            
            predictions = self.model(all_users, all_items)
            mse = criterion(predictions, all_ratings)
            rmse = torch.sqrt(mse).item()
        
        # Save model
        if save_model:
            self.save()
        
        metrics = {
            'final_loss': epoch_losses[-1],
            'rmse': rmse,
            'n_users': n_users,
            'n_items': n_items,
            'n_interactions': len(ratings),
            'n_epochs': self.n_epochs,
            'device': str(self.device),
        }
        
        logger.info(f"Training complete. RMSE: {rmse:.4f}")
        return metrics
    
    def predict(self, user_id: str, resource_id: int) -> float:
        """Predict rating for a user-item pair."""
        if not self._is_fitted:
            self.load()
        
        if self.model is None:
            raise ValueError("Model not trained")
        
        # Handle unknown users/items
        if user_id not in self.user_id_map:
            return 3.0  # Default neutral rating
        if resource_id not in self.item_id_map:
            return 3.0
        
        user_idx = self.user_id_map[user_id]
        item_idx = self.item_id_map[resource_id]
        
        self.model.eval()
        with torch.no_grad():
            user_tensor = torch.LongTensor([user_idx]).to(self.device)
            item_tensor = torch.LongTensor([item_idx]).to(self.device)
            prediction = self.model(user_tensor, item_tensor)
        
        return prediction.item()
    
    def get_recommendations(
        self,
        user_id: str,
        context_id: str,
        limit: int = 10,
        exclude_viewed: bool = True
    ) -> List[Dict]:
        """Get top-N recommendations for a user."""
        from django.db.models import Q
        from lti_recommender_project.apps.resources.models import EducationalResource
        from lti_recommender_project.apps.interactions.models import UserInteraction
        
        if not self._is_fitted:
            self.load()
        
        if self.model is None:
            logger.warning("NCF model not available")
            return []
        
        # Get viewed items for exclusion
        viewed_ids = set()
        if exclude_viewed:
            viewed_ids = set(
                UserInteraction.objects.filter(
                    lti_user_id=user_id
                ).values_list('resource_id', flat=True)
            )
        
        # Handle unknown user - cold start
        if user_id not in self.user_id_map:
            resources = EducationalResource.objects.filter(
                Q(lti_context_id=context_id) | Q(lti_context_id__isnull=True)
            ).exclude(id__in=viewed_ids)[:limit]
            
            return [{
                'resource': resource,
                'score': 3.0,
                'title': resource.title,
                'url': resource.url,
                'description': resource.description,
                'type': resource.resource_type,
                'difficulty': resource.difficulty_level,
                'id': resource.id,
                'source': 'ncf_cold_start'
            } for resource in resources]
        
        user_idx = self.user_id_map[user_id]
        
        # Score all items in the model's vocabulary
        self.model.eval()
        scored_items = []
        
        with torch.no_grad():
            # Batch scoring for efficiency
            item_indices = list(self.item_id_map.values())
            item_ids = list(self.item_id_map.keys())
            
            for i, (item_id, item_idx) in enumerate(zip(item_ids, item_indices)):
                if item_id in viewed_ids:
                    continue
                
                user_tensor = torch.LongTensor([user_idx]).to(self.device)
                item_tensor = torch.LongTensor([item_idx]).to(self.device)
                score = self.model(user_tensor, item_tensor).item()
                
                scored_items.append((item_id, score))
        
        # Sort by score
        scored_items.sort(key=lambda x: x[1], reverse=True)
        
        # Get top resources
        recommendations = []
        for item_id, score in scored_items[:limit * 2]:  # Get extra in case some don't exist
            try:
                resource = EducationalResource.objects.get(id=item_id)
                # Check context match
                if context_id and resource.lti_context_id and resource.lti_context_id != context_id:
                    continue
                    
                recommendations.append({
                    'resource': resource,
                    'score': score,
                    'title': resource.title,
                    'url': resource.url,
                    'description': resource.description,
                    'type': resource.resource_type,
                    'difficulty': resource.difficulty_level,
                    'id': resource.id,
                    'source': 'ncf'
                })
                
                if len(recommendations) >= limit:
                    break
            except EducationalResource.DoesNotExist:
                continue
        
        return recommendations
    
    def save(self):
        """Save model and mappings to disk."""
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        
        # Save PyTorch model
        torch.save({
            'model_state_dict': self.model.state_dict(),
            'model_config': {
                'n_users': self.model.n_users,
                'n_items': self.model.n_items,
                'embedding_dim': self.model.embedding_dim,
            }
        }, NCF_MODEL_PATH)
        
        # Save mappings
        mappings = {
            'user_id_map': self.user_id_map,
            'item_id_map': self.item_id_map,
            'reverse_user_map': self.reverse_user_map,
            'reverse_item_map': self.reverse_item_map,
        }
        with open(NCF_MAPPINGS_PATH, 'wb') as f:
            pickle.dump(mappings, f)
        
        logger.info(f"NCF model saved to {NCF_MODEL_PATH}")
    
    def load(self) -> bool:
        """Load model from disk."""
        if not NCF_MODEL_PATH.exists() or not NCF_MAPPINGS_PATH.exists():
            logger.warning("No saved NCF model found")
            return False
        
        try:
            # Load mappings
            with open(NCF_MAPPINGS_PATH, 'rb') as f:
                mappings = pickle.load(f)
            
            self.user_id_map = mappings['user_id_map']
            self.item_id_map = mappings['item_id_map']
            self.reverse_user_map = mappings['reverse_user_map']
            self.reverse_item_map = mappings['reverse_item_map']
            
            # Load model
            checkpoint = torch.load(NCF_MODEL_PATH, map_location=self.device)
            config = checkpoint['model_config']
            
            self.model = NCFModel(
                n_users=config['n_users'],
                n_items=config['n_items'],
                embedding_dim=config['embedding_dim'],
                mlp_layers=self.mlp_layers,
                dropout=self.dropout
            ).to(self.device)
            
            self.model.load_state_dict(checkpoint['model_state_dict'])
            self.model.eval()
            self._is_fitted = True
            
            logger.info(f"NCF model loaded from {NCF_MODEL_PATH}")
            return True
            
        except Exception as e:
            logger.error(f"Error loading NCF model: {e}")
            return False


# Singleton instance
_ncf_model_instance: Optional[NeuralCFModel] = None


def get_ncf_model() -> NeuralCFModel:
    """Get singleton instance of NCF model."""
    global _ncf_model_instance
    
    if _ncf_model_instance is None:
        _ncf_model_instance = NeuralCFModel()
        _ncf_model_instance.load()
    
    return _ncf_model_instance
