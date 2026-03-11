"""
Models for storing ML model evaluation metrics over time.
Allows tracking model performance across retraining cycles.
"""
from django.db import models
from django.utils import timezone


class ModelEvaluationResult(models.Model):
    """
    Stores evaluation metrics for each model after every training run.
    This creates a historical record of model performance over time.
    """
    MODEL_CHOICES = [
        ('svd', 'SVD Matrix Factorization'),
        ('ncf', 'Neural Collaborative Filtering'),
        ('sequential', 'Sequential (GRU4Rec)'),
        ('hybrid', 'Hybrid Content+Collaborative'),
        ('fm', 'Factorization Machine'),
        ('ensemble', 'Ensemble'),
    ]

    model_name = models.CharField(max_length=50, choices=MODEL_CHOICES, db_index=True)
    evaluated_at = models.DateTimeField(default=timezone.now, db_index=True)

    # Training metrics (from fit())
    train_loss = models.FloatField(null=True, blank=True)
    train_rmse = models.FloatField(null=True, blank=True, help_text="RMSE on training or CV data")

    # Held-out evaluation metrics (from fit() with split)
    test_rmse = models.FloatField(null=True, blank=True, help_text="RMSE on held-out test set")
    test_hit_rate_at_10 = models.FloatField(null=True, blank=True)

    # Offline evaluator metrics (from OfflineEvaluator / ModelEvaluator)
    precision_at_5 = models.FloatField(null=True, blank=True)
    precision_at_10 = models.FloatField(null=True, blank=True)
    recall_at_5 = models.FloatField(null=True, blank=True)
    recall_at_10 = models.FloatField(null=True, blank=True)
    ndcg_at_5 = models.FloatField(null=True, blank=True)
    ndcg_at_10 = models.FloatField(null=True, blank=True)
    hit_at_5 = models.FloatField(null=True, blank=True)
    hit_at_10 = models.FloatField(null=True, blank=True)
    mrr = models.FloatField(null=True, blank=True, help_text="Mean Reciprocal Rank")
    map_at_k = models.FloatField(null=True, blank=True, help_text="Mean Average Precision@K")
    f1_score = models.FloatField(null=True, blank=True)
    coverage = models.FloatField(null=True, blank=True, help_text="Catalog coverage (0-1)")

    # Context
    n_users = models.IntegerField(null=True, blank=True)
    n_items = models.IntegerField(null=True, blank=True)
    n_interactions = models.IntegerField(null=True, blank=True)
    n_users_evaluated = models.IntegerField(null=True, blank=True)
    ensemble_weight = models.FloatField(null=True, blank=True, help_text="Weight assigned in ensemble")

    # Raw JSON for any extra metrics
    raw_metrics = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ['-evaluated_at']
        indexes = [
            models.Index(fields=['model_name', '-evaluated_at']),
        ]

    def __str__(self):
        return f"{self.get_model_name_display()} @ {self.evaluated_at.strftime('%Y-%m-%d %H:%M')}"
