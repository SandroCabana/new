"""
Sequential Recommender Model (GRU4Rec)
Session-based recommendations using GRU neural networks.

Reference: Hidasi et al., "Session-based Recommendations with Recurrent Neural Networks", ICLR 2016
"""

import logging
import pickle
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from collections import defaultdict
import numpy as np

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from torch.nn.utils.rnn import pad_sequence, pack_padded_sequence, pad_packed_sequence

logger = logging.getLogger(__name__)

# Model save path
MODEL_DIR = Path(__file__).parent.parent / 'saved_models'
SEQ_MODEL_PATH = MODEL_DIR / 'sequential_model.pt'
SEQ_MAPPINGS_PATH = MODEL_DIR / 'sequential_mappings.pkl'


class SequenceDataset(Dataset):
    """Dataset for sequential recommendation training."""
    
    def __init__(self, sequences: List[List[int]], targets: List[int]):
        self.sequences = sequences
        self.targets = torch.LongTensor(targets)
    
    def __len__(self):
        return len(self.targets)
    
    def __getitem__(self, idx):
        return torch.LongTensor(self.sequences[idx]), self.targets[idx]


def collate_sequences(batch):
    """Custom collate function for variable-length sequences."""
    sequences, targets = zip(*batch)
    lengths = torch.LongTensor([len(seq) for seq in sequences])
    padded_seqs = pad_sequence(sequences, batch_first=True, padding_value=0)
    targets = torch.LongTensor(targets)
    return padded_seqs, lengths, targets


class GRU4Rec(nn.Module):
    """
    GRU-based Session Recommender.
    
    Takes a sequence of item IDs and predicts the next item.
    """
    
    def __init__(
        self,
        n_items: int,
        embedding_dim: int = 64,
        hidden_dim: int = 128,
        n_layers: int = 1,
        dropout: float = 0.2
    ):
        super(GRU4Rec, self).__init__()
        
        self.n_items = n_items
        self.embedding_dim = embedding_dim
        self.hidden_dim = hidden_dim
        
        # Item embedding (index 0 reserved for padding)
        self.item_embedding = nn.Embedding(n_items + 1, embedding_dim, padding_idx=0)
        
        # GRU layer
        self.gru = nn.GRU(
            input_size=embedding_dim,
            hidden_size=hidden_dim,
            num_layers=n_layers,
            batch_first=True,
            dropout=dropout if n_layers > 1 else 0
        )
        
        # Output layer
        self.dropout = nn.Dropout(dropout)
        self.output = nn.Linear(hidden_dim, n_items)
        
        self._init_weights()
    
    def _init_weights(self):
        nn.init.xavier_uniform_(self.item_embedding.weight.data[1:])
        nn.init.xavier_uniform_(self.output.weight)
        nn.init.zeros_(self.output.bias)
    
    def forward(
        self, 
        sequence: torch.Tensor, 
        lengths: torch.Tensor
    ) -> torch.Tensor:
        """
        Forward pass.
        
        Args:
            sequence: Batch of item sequences [batch_size, max_seq_len]
            lengths: Actual lengths of each sequence
            
        Returns:
            Logits for next item prediction [batch_size, n_items]
        """
        # Embed items
        embedded = self.item_embedding(sequence)  # [batch, seq_len, embed_dim]
        
        # Pack for efficient RNN processing
        packed = pack_padded_sequence(
            embedded, 
            lengths.cpu(), 
            batch_first=True, 
            enforce_sorted=False
        )
        
        # GRU forward
        packed_output, hidden = self.gru(packed)
        
        # Get the last hidden state
        # hidden shape: [n_layers, batch, hidden_dim]
        last_hidden = hidden[-1]  # [batch, hidden_dim]
        
        # Predict next item
        output = self.dropout(last_hidden)
        logits = self.output(output)  # [batch, n_items]
        
        return logits


class SequentialRecommender:
    """
    Wrapper class for GRU4Rec with training and inference.
    """
    
    def __init__(
        self,
        embedding_dim: int = 64,
        hidden_dim: int = 128,
        n_layers: int = 1,
        dropout: float = 0.2,
        lr: float = 0.001,
        batch_size: int = 32,
        n_epochs: int = 30,
        min_seq_length: int = 2,
        max_seq_length: int = 20,
        device: str = 'auto'
    ):
        self.embedding_dim = embedding_dim
        self.hidden_dim = hidden_dim
        self.n_layers = n_layers
        self.dropout = dropout
        self.lr = lr
        self.batch_size = batch_size
        self.n_epochs = n_epochs
        self.min_seq_length = min_seq_length
        self.max_seq_length = max_seq_length
        
        if device == 'auto':
            self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        else:
            self.device = torch.device(device)
        
        self.model = None
        self.item_id_map = {}
        self.reverse_item_map = {}
        self._is_fitted = False
    
    def _build_sequences(self) -> Tuple[List[List[int]], List[int]]:
        """
        Build training sequences from user interaction history.
        
        For each user, create sequences where the target is the next item.
        """
        from lti_recommender_project.apps.interactions.models import UserInteraction
        
        # Get all interactions ordered by user and timestamp
        interactions = list(UserInteraction.objects.all().values(
            'lti_user_id', 'resource_id', 'timestamp'
        ).order_by('lti_user_id', 'timestamp'))
        
        if not interactions:
            raise ValueError("No interaction data available")
        
        # Build item ID mapping
        unique_items = sorted(set(i['resource_id'] for i in interactions))
        # Reserve 0 for padding, start from 1
        self.item_id_map = {iid: idx + 1 for idx, iid in enumerate(unique_items)}
        self.reverse_item_map = {idx: iid for iid, idx in self.item_id_map.items()}
        
        # Group interactions by user
        user_sequences = defaultdict(list)
        for interaction in interactions:
            user_sequences[interaction['lti_user_id']].append(
                self.item_id_map[interaction['resource_id']]
            )
        
        # Create training samples: (sequence, next_item)
        sequences = []
        targets = []
        
        for user_id, items in user_sequences.items():
            if len(items) < self.min_seq_length:
                continue
            
            # Create sliding window sequences
            for i in range(1, len(items)):
                # Sequence is all items up to i (max length)
                start_idx = max(0, i - self.max_seq_length)
                seq = items[start_idx:i]
                target = items[i] - 1  # Convert to 0-indexed for output
                
                sequences.append(seq)
                targets.append(target)
        
        logger.info(f"Built {len(sequences)} training sequences from {len(user_sequences)} users")
        return sequences, targets
    
    def fit(self, save_model: bool = True) -> Dict:
        """
        Train the sequential recommender.
        """
        logger.info("Starting Sequential Recommender training...")
        
        # Build sequences
        sequences, targets = self._build_sequences()
        
        if len(sequences) < 5:
            logger.warning("Not enough sequences for training")
            return {'error': 'Insufficient sequences'}
        
        n_items = len(self.item_id_map)
        
        # Create model
        self.model = GRU4Rec(
            n_items=n_items,
            embedding_dim=self.embedding_dim,
            hidden_dim=self.hidden_dim,
            n_layers=self.n_layers,
            dropout=self.dropout
        ).to(self.device)
        
        # Create dataset
        dataset = SequenceDataset(sequences, targets)
        dataloader = DataLoader(
            dataset,
            batch_size=min(self.batch_size, len(sequences)),
            shuffle=True,
            collate_fn=collate_sequences,
            num_workers=0
        )
        
        # Loss and optimizer
        criterion = nn.CrossEntropyLoss()
        optimizer = optim.Adam(self.model.parameters(), lr=self.lr)
        
        # Training
        epoch_losses = []
        for epoch in range(self.n_epochs):
            self.model.train()
            total_loss = 0
            n_batches = 0
            
            for seqs, lengths, targets_batch in dataloader:
                seqs = seqs.to(self.device)
                lengths = lengths.to(self.device)
                targets_batch = targets_batch.to(self.device)
                
                optimizer.zero_grad()
                logits = self.model(seqs, lengths)
                loss = criterion(logits, targets_batch)
                loss.backward()
                optimizer.step()
                
                total_loss += loss.item()
                n_batches += 1
            
            avg_loss = total_loss / n_batches
            epoch_losses.append(avg_loss)
            
            if (epoch + 1) % 10 == 0:
                logger.info(f"Epoch {epoch + 1}/{self.n_epochs}, Loss: {avg_loss:.4f}")
        
        self._is_fitted = True
        
        # Calculate hit rate on training data
        self.model.eval()
        hits = 0
        total = 0
        
        with torch.no_grad():
            for seqs, lengths, targets_batch in dataloader:
                seqs = seqs.to(self.device)
                lengths = lengths.to(self.device)
                
                logits = self.model(seqs, lengths)
                _, predicted = torch.topk(logits, k=10, dim=1)
                
                for pred, target in zip(predicted, targets_batch):
                    if target.item() in pred.tolist():
                        hits += 1
                    total += 1
        
        hit_rate = hits / total if total > 0 else 0
        
        # Save model
        if save_model:
            self.save()
        
        metrics = {
            'final_loss': epoch_losses[-1],
            'hit_rate_at_10': hit_rate,
            'n_items': n_items,
            'n_sequences': len(sequences),
            'n_epochs': self.n_epochs,
            'device': str(self.device),
        }
        
        logger.info(f"Training complete. Hit Rate@10: {hit_rate:.4f}")
        return metrics
    
    def get_recommendations(
        self,
        user_id: str,
        context_id: str,
        limit: int = 10,
        exclude_viewed: bool = True
    ) -> List[Dict]:
        """Get recommendations based on user's recent sequence."""
        from django.db.models import Q
        from lti_recommender_project.apps.resources.models import EducationalResource
        from lti_recommender_project.apps.interactions.models import UserInteraction
        
        if not self._is_fitted:
            self.load()
        
        if self.model is None:
            logger.warning("Sequential model not available")
            return []
        
        # Get user's recent interactions
        recent_interactions = list(UserInteraction.objects.filter(
            lti_user_id=user_id
        ).order_by('-timestamp').values_list('resource_id', flat=True)[:self.max_seq_length])
        
        if not recent_interactions:
            return []
        
        # Reverse to get chronological order
        recent_interactions = list(reversed(recent_interactions))
        
        # Convert to indices
        sequence = []
        for rid in recent_interactions:
            if rid in self.item_id_map:
                sequence.append(self.item_id_map[rid])
        
        if not sequence:
            return []
        
        # Predict next items
        self.model.eval()
        with torch.no_grad():
            seq_tensor = torch.LongTensor([sequence]).to(self.device)
            lengths = torch.LongTensor([len(sequence)])
            
            logits = self.model(seq_tensor, lengths)
            probabilities = torch.softmax(logits, dim=1)[0]
            
            # Get top scored items (cap k to avoid index out of range)
            k = min(limit * 2, probabilities.size(0))
            scores, indices = torch.topk(probabilities, k=k)
        
        # Convert to resource recommendations
        viewed_ids = set(recent_interactions) if exclude_viewed else set()
        recommendations = []
        
        for score, idx in zip(scores.tolist(), indices.tolist()):
            item_idx = idx + 1  # Convert back from 0-indexed
            if item_idx not in self.reverse_item_map:
                continue
            
            resource_id = self.reverse_item_map[item_idx]
            if resource_id in viewed_ids:
                continue
            
            try:
                resource = EducationalResource.objects.get(id=resource_id)
                recommendations.append({
                    'resource': resource,
                    'score': score,
                    'title': resource.title,
                    'url': resource.url,
                    'description': resource.description,
                    'type': resource.resource_type,
                    'difficulty': resource.difficulty_level,
                    'id': resource.id,
                    'source': 'sequential'
                })
            except EducationalResource.DoesNotExist:
                continue
            
            if len(recommendations) >= limit:
                break
        
        return recommendations
    
    def save(self):
        """Save model to disk."""
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        
        torch.save({
            'model_state_dict': self.model.state_dict(),
            'model_config': {
                'n_items': self.model.n_items,
                'embedding_dim': self.model.embedding_dim,
                'hidden_dim': self.model.hidden_dim,
            }
        }, SEQ_MODEL_PATH)
        
        mappings = {
            'item_id_map': self.item_id_map,
            'reverse_item_map': self.reverse_item_map,
        }
        with open(SEQ_MAPPINGS_PATH, 'wb') as f:
            pickle.dump(mappings, f)
        
        logger.info(f"Sequential model saved to {SEQ_MODEL_PATH}")
    
    def load(self) -> bool:
        """Load model from disk."""
        if not SEQ_MODEL_PATH.exists() or not SEQ_MAPPINGS_PATH.exists():
            logger.warning("No saved sequential model found")
            return False
        
        try:
            with open(SEQ_MAPPINGS_PATH, 'rb') as f:
                mappings = pickle.load(f)
            
            self.item_id_map = mappings['item_id_map']
            self.reverse_item_map = mappings['reverse_item_map']
            
            checkpoint = torch.load(SEQ_MODEL_PATH, map_location=self.device)
            config = checkpoint['model_config']
            
            self.model = GRU4Rec(
                n_items=config['n_items'],
                embedding_dim=config['embedding_dim'],
                hidden_dim=config['hidden_dim'],
                n_layers=self.n_layers,
                dropout=self.dropout
            ).to(self.device)
            
            self.model.load_state_dict(checkpoint['model_state_dict'])
            self.model.eval()
            self._is_fitted = True
            
            logger.info(f"Sequential model loaded from {SEQ_MODEL_PATH}")
            return True
            
        except Exception as e:
            logger.error(f"Error loading sequential model: {e}")
            return False


# Singleton
_sequential_model_instance: Optional[SequentialRecommender] = None


def get_sequential_model() -> SequentialRecommender:
    """Get singleton instance."""
    global _sequential_model_instance
    
    if _sequential_model_instance is None:
        _sequential_model_instance = SequentialRecommender()
        _sequential_model_instance.load()
    
    return _sequential_model_instance
