#!/usr/bin/env python
"""Script para probar la visualización de scores en las recomendaciones"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lti_recommender_project.settings')
django.setup()

from lti_recommender_project.apps.recommendations.services.recommendation_engine import get_recommendation_engine

print("="*70)
print(" PRUEBA DE SCORES DE CONFIANZA EN RECOMENDACIONES")
print("="*70)

engine = get_recommendation_engine()
recommendations = engine.get_recommendations(
    user_id='test_score_display',
    context_id='2',
    limit=5,
    exclude_viewed=False
)

if recommendations:
    print(f"\n✓ Se generaron {len(recommendations)} recomendaciones:\n")
    print(f"{'#':<3} {'Score':<8} {'Nivel':<12} {'Título':<50}")
    print("-" * 70)
    
    for i, rec in enumerate(recommendations, 1):
        score = rec['score'] * 100  # Convertir a porcentaje
        
        # Determinar nivel de confianza
        if score >= 70:
            nivel = "🟢 Alta"
        elif score >= 40:
            nivel = "🟡 Media"
        else:
            nivel = "🔴 Baja"
        
        title = rec['title'][:47] + "..." if len(rec['title']) > 50 else rec['title']
        print(f"{i:<3} {score:>5.1f}%  {nivel:<12} {title}")
    
    print("\n" + "="*70)
    print(" CATEGORIZACIÓN DE NIVELES DE CONFIANZA")
    print("="*70)
    print(" 🟢 Alta (≥70%):   Muy recomendado para ti")
    print(" 🟡 Media (40-70%): Podría interesarte")
    print(" 🔴 Baja (<40%):    Explorar")
    print("="*70)
else:
    print("\n⚠ No se generaron recomendaciones")
