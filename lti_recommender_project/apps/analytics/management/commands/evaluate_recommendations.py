"""
Management command: evaluate_recommendations
Ejecuta evaluación offline del sistema de recomendaciones.

Uso:
  python manage.py evaluate_recommendations
  python manage.py evaluate_recommendations --k 5 10 20
  python manage.py evaluate_recommendations --model svd
  python manage.py evaluate_recommendations --ab-stats
"""
from django.core.management.base import BaseCommand
from django.db import connection
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Evaluación offline del sistema de recomendaciones (Precision@K, NDCG@K, MRR)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--k',
            nargs='+',
            type=int,
            default=[5, 10],
            help='Valores de K para Precision@K y NDCG@K (default: 5 10)',
        )
        parser.add_argument(
            '--model',
            type=str,
            default='ensemble',
            choices=['ensemble', 'svd', 'hybrid'],
            help='Modelo a evaluar (default: ensemble)',
        )
        parser.add_argument(
            '--test-ratio',
            type=float,
            default=0.2,
            help='Fracción de datos para test (default: 0.2)',
        )
        parser.add_argument(
            '--ab-stats',
            action='store_true',
            help='Muestra estadísticas del A/B test',
        )

    def handle(self, *args, **options):
        from lti_recommender_project.apps.analytics.evaluation import OfflineEvaluator, ABTestManager

        k_values = options['k']
        model_name = options['model']
        test_ratio = options['test_ratio']

        self.stdout.write(self.style.MIGRATE_HEADING(
            f"\n{'='*60}\n  Evaluación Offline — {model_name.upper()}\n{'='*60}"
        ))

        # A/B stats
        if options['ab_stats']:
            stats = ABTestManager.get_variant_stats()
            self.stdout.write(f"\n📊 A/B Test Stats:")
            self.stdout.write(f"  Total users: {stats['total_users']}")
            for variant, data in stats['variants'].items():
                desc = stats['variant_descriptions'][variant]
                self.stdout.write(f"  Variant {variant} ({desc}): {data['users']} users")
            self.stdout.write("")

        # Load model
        model = self._load_model(model_name)
        if model is None:
            self.stdout.write(self.style.ERROR(f"❌ Could not load model: {model_name}"))
            return

        # Run evaluation
        self.stdout.write(f"📈 Evaluating with K={k_values}, test_ratio={test_ratio}...")
        evaluator = OfflineEvaluator()
        results = evaluator.evaluate_model(model, test_ratio=test_ratio, k_values=k_values)

        if 'error' in results:
            self.stdout.write(self.style.ERROR(f"❌ Evaluation error: {results}"))
            return

        # Print results table
        self.stdout.write(f"\n✅ Resultados ({results['users_evaluated']} usuarios evaluados):\n")
        self.stdout.write(f"  {'Métrica':<20} {'Valor':>10}")
        self.stdout.write(f"  {'-'*32}")

        for k in k_values:
            self.stdout.write(
                f"  {'Precision@' + str(k):<20} {results.get(f'precision@{k}', 0):.4f}"
            )
        for k in k_values:
            self.stdout.write(
                f"  {'Recall@' + str(k):<20} {results.get(f'recall@{k}', 0):.4f}"
            )
        for k in k_values:
            self.stdout.write(
                f"  {'NDCG@' + str(k):<20} {results.get(f'ndcg@{k}', 0):.4f}"
            )
        for k in k_values:
            self.stdout.write(
                f"  {'Hit@' + str(k):<20} {results.get(f'hit@{k}', 0):.4f}"
            )
        self.stdout.write(f"  {'MRR':<20} {results.get('mrr', 0):.4f}")
        self.stdout.write(f"\n  Split: {results['test_interactions']} test interactions")
        self.stdout.write(f"  {'='*32}\n")

        # Interpretation
        ndcg5 = results.get('ndcg@5', 0)
        if ndcg5 >= 0.5:
            quality = "🟢 Excelente"
        elif ndcg5 >= 0.3:
            quality = "🟡 Bueno"
        elif ndcg5 >= 0.15:
            quality = "🟠 Regular"
        else:
            quality = "🔴 Requiere mejora"

        self.stdout.write(f"  Calidad del sistema (NDCG@5={ndcg5:.3f}): {quality}")

    def _load_model(self, model_name: str):
        """Carga el modelo especificado."""
        try:
            if model_name == 'ensemble':
                from lti_recommender_project.ml.models.ensemble import get_ensemble_recommender
                return get_ensemble_recommender()
            elif model_name == 'svd':
                from lti_recommender_project.ml.models.matrix_factorization import get_svd_model
                return get_svd_model()
            elif model_name == 'hybrid':
                from lti_recommender_project.apps.recommendations.services.recommendation_engine import (
                    get_recommendation_engine
                )
                return get_recommendation_engine()
        except Exception as e:
            logger.error(f"Error loading model {model_name}: {e}")
            return None
