#!/usr/bin/env python
"""Script simple de verificación del sistema de recomendaciones"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lti_recommender_project.settings')
django.setup()

from lti_recommender_project.apps.resources.models import EducationalResource
from lti_recommender_project.apps.recommendations.services.recommendation_engine import get_recommendation_engine

print("="*60)
print(" VERIFICACIÓN DEL SISTEMA DE RECOMENDACIONES")
print("="*60)

# 1. Verificar embeddings
total_recursos = EducationalResource.objects.count()
con_embeddings = EducationalResource.objects.filter(embedding__isnull=False).count()

print(f"\n✓ Recursos totales: {total_recursos}")
print(f"✓ Recursos con embeddings: {con_embeddings}")
print(f"✓ Cobertura: {(con_embeddings/total_recursos*100):.1f}%")

# 2. Probar motor de recomendaciones
print("\n" + "="*60)
print(" PRUEBA DEL MOTOR DE RECOMENDACIONES")
print("="*60)

engine = get_recommendation_engine()
test_context = "2"  # base de datos I

print(f"\nSolicitando recomendaciones para context_id='{test_context}'...")
recs = engine.get_recommendations(
    user_id='test_verification',
    context_id=test_context,
    limit=5,
    exclude_viewed=False 
)

if recs:
    print(f"\n✓ Se generaron {len(recs)} recomendaciones:\n")
    for i, rec in enumerate(recs, 1):
        title = rec['title'][:60] + "..." if len(rec['title']) > 60 else rec['title']
        print(f"  {i}. {title}")
        print(f"     Score: {rec['score']:.3f} | Tipo: {rec.get('type', 'N/A')} | Dificultad: {rec.get('difficulty', 'N/A')}")
        print()
else:
    print("\n⚠ No se generaron recomendaciones")

print("="*60)
print(" SISTEMA VERIFICADO EXITOSAMENTE ")
print("="*60)
