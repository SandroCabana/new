"""
Training script for recommendation models.
Usage: python train_models.py --model svd
"""

import os
import sys
import argparse
import logging
from datetime import datetime
from pathlib import Path

# Add parent of lti_recommender_project to path (allows `import lti_recommender_project.apps.*`)
# This script is at: lti_recommender_project/ml/training/train_models.py
# PROJECT_ROOT should be: lti_moodle_recomender (contains lti_recommender_project/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lti_recommender_project.settings')

import django
django.setup()

from lti_recommender_project.ml.models.matrix_factorization import MatrixFactorizationModel
from lti_recommender_project.ml.data_preprocessing.preprocessor import get_preprocessor

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def train_svd(save: bool = True) -> dict:
    """
    Train the SVD Matrix Factorization model.
    
    Args:
        save: Whether to save the trained model
        
    Returns:
        Dictionary with training metrics
    """
    logger.info("=" * 50)
    logger.info("Training SVD Matrix Factorization Model")
    logger.info("=" * 50)
    
    # Get data statistics first
    preprocessor = get_preprocessor()
    interactions = preprocessor.get_interaction_data()
    stats = preprocessor.get_statistics(interactions)
    
    logger.info("\nDataset Statistics:")
    logger.info(f"  - Total interactions: {stats['n_interactions']}")
    logger.info(f"  - Unique users: {stats['n_users']}")
    logger.info(f"  - Unique items: {stats['n_items']}")
    logger.info(f"  - Sparsity: {stats['sparsity']:.2%}")
    logger.info(f"  - Avg rating: {stats['avg_rating']:.2f}")
    
    if stats['n_interactions'] < 10:
        logger.warning("Not enough interactions for training (minimum 10 required)")
        return {'error': 'Insufficient data'}
    
    # Train model
    model = MatrixFactorizationModel(
        n_factors=50,  # Reduced for smaller datasets
        n_epochs=20,
        lr_all=0.005,
        reg_all=0.02
    )
    
    metrics = model.fit(save_model=save)
    
    logger.info("\nTraining Results:")
    logger.info(f"  - RMSE: {metrics['rmse_mean']:.4f} (+/- {metrics['rmse_std']:.4f})")
    logger.info(f"  - MAE: {metrics['mae_mean']:.4f} (+/- {metrics['mae_std']:.4f})")
    logger.info(f"  - Users in model: {metrics['n_users']}")
    logger.info(f"  - Items in model: {metrics['n_items']}")
    logger.info(f"  - Ratings used: {metrics['n_ratings']}")
    
    return metrics


def train_ncf(save: bool = True) -> dict:
    """
    Train the Neural Collaborative Filtering model.
    
    Args:
        save: Whether to save the trained model
        
    Returns:
        Dictionary with training metrics
    """
    from lti_recommender_project.ml.models.neural_cf import NeuralCFModel
    
    logger.info("=" * 50)
    logger.info("Training Neural Collaborative Filtering Model")
    logger.info("=" * 50)
    
    # Get data statistics first
    preprocessor = get_preprocessor()
    interactions = preprocessor.get_interaction_data()
    stats = preprocessor.get_statistics(interactions)
    
    logger.info("\nDataset Statistics:")
    logger.info(f"  - Total interactions: {stats['n_interactions']}")
    logger.info(f"  - Unique users: {stats['n_users']}")
    logger.info(f"  - Unique items: {stats['n_items']}")
    logger.info(f"  - Sparsity: {stats['sparsity']:.2%}")
    
    if stats['n_interactions'] < 10:
        logger.warning("Not enough interactions for training (minimum 10 required)")
        return {'error': 'Insufficient data'}
    
    # Train model
    model = NeuralCFModel(
        embedding_dim=32,
        mlp_layers=[64, 32, 16],
        dropout=0.2,
        lr=0.001,
        batch_size=min(32, stats['n_interactions']),
        n_epochs=30
    )
    
    metrics = model.fit(save_model=save)
    
    logger.info("\nTraining Results:")
    logger.info(f"  - Final Loss: {metrics['final_loss']:.4f}")
    logger.info(f"  - RMSE: {metrics['rmse']:.4f}")
    logger.info(f"  - Users: {metrics['n_users']}")
    logger.info(f"  - Items: {metrics['n_items']}")
    logger.info(f"  - Device: {metrics['device']}")
    
    return metrics


def train_sequential(save: bool = True) -> dict:
    """
    Train the Sequential Recommender (GRU4Rec) model.
    """
    from lti_recommender_project.ml.models.sequential_rec import SequentialRecommender
    
    logger.info("=" * 50)
    logger.info("Training Sequential Recommender (GRU4Rec)")
    logger.info("=" * 50)
    
    model = SequentialRecommender(
        embedding_dim=64,
        hidden_dim=128,
        n_layers=1,
        dropout=0.2,
        lr=0.001,
        batch_size=32,
        n_epochs=50,
        min_seq_length=2
    )
    
    metrics = model.fit(save_model=save)
    
    if 'error' not in metrics:
        logger.info("\nTraining Results:")
        logger.info(f"  - Final Loss: {metrics['final_loss']:.4f}")
        logger.info(f"  - Hit Rate@10: {metrics['hit_rate_at_10']:.4f}")
        logger.info(f"  - Items: {metrics['n_items']}")
        logger.info(f"  - Sequences: {metrics['n_sequences']}")
    
    return metrics


def train_fm(save: bool = True) -> dict:
    """
    Train the Factorization Machine model with context.
    """
    from lti_recommender_project.ml.models.factorization_machine import ContextualFM
    
    logger.info("=" * 50)
    logger.info("Training Factorization Machine (with context)")
    logger.info("=" * 50)
    
    model = ContextualFM(
        k=8,
        lr=0.01,
        reg=0.001,
        batch_size=32,
        n_epochs=50
    )
    
    metrics = model.fit(save_model=save)
    
    if 'error' not in metrics:
        logger.info("\nTraining Results:")
        logger.info(f"  - Final Loss: {metrics['final_loss']:.4f}")
        logger.info(f"  - RMSE: {metrics['rmse']:.4f}")
        logger.info(f"  - Features: {metrics['n_features']}")
    
    return metrics


def main():
    parser = argparse.ArgumentParser(description='Train recommendation models')
    parser.add_argument(
        '--model', 
        choices=['svd', 'ncf', 'sequential', 'fm', 'all'], 
        default='svd',
        help='Model to train'
    )
    parser.add_argument(
        '--no-save',
        action='store_true',
        help='Do not save the trained model'
    )
    
    args = parser.parse_args()
    
    start_time = datetime.now()
    
    if args.model in ['svd', 'all']:
        metrics = train_svd(save=not args.no_save)
        print(f"\nSVD Training Complete!")
        if 'error' not in metrics:
            print(f"  RMSE: {metrics['rmse_mean']:.4f}")
            print(f"  MAE: {metrics['mae_mean']:.4f}")
    
    if args.model in ['ncf', 'all']:
        metrics = train_ncf(save=not args.no_save)
        print(f"\nNCF Training Complete!")
        if 'error' not in metrics:
            print(f"  RMSE: {metrics['rmse']:.4f}")
            print(f"  Final Loss: {metrics['final_loss']:.4f}")
    
    if args.model in ['sequential', 'all']:
        metrics = train_sequential(save=not args.no_save)
        print(f"\nSequential Recommender Training Complete!")
        if 'error' not in metrics:
            print(f"  Hit Rate@10: {metrics['hit_rate_at_10']:.4f}")
            print(f"  Final Loss: {metrics['final_loss']:.4f}")
    
    if args.model in ['fm', 'all']:
        metrics = train_fm(save=not args.no_save)
        print(f"\nFactorization Machine Training Complete!")
        if 'error' not in metrics:
            print(f"  RMSE: {metrics['rmse']:.4f}")
            print(f"  Features: {metrics['n_features']}")
    
    elapsed = datetime.now() - start_time
    print(f"\nTotal training time: {elapsed}")


if __name__ == '__main__':
    main()
