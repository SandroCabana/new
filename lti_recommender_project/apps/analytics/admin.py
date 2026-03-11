from django.contrib import admin
from .models import ModelEvaluationResult


@admin.register(ModelEvaluationResult)
class ModelEvaluationResultAdmin(admin.ModelAdmin):
    list_display = [
        'model_name', 'evaluated_at',
        'test_rmse', 'test_hit_rate_at_10',
        'precision_at_5', 'ndcg_at_5', 'mrr', 'coverage',
        'ensemble_weight',
    ]
    list_filter = ['model_name', 'evaluated_at']
    readonly_fields = ['raw_metrics']
    ordering = ['-evaluated_at']
