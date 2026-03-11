"""
Explainability — Explicaciones legibles para recomendaciones.
Diferencia vista estudiante (motivadora) vs docente (técnica).
Referente: Spotify ("Porque escuchaste X"), Netflix SHAP explanations.
"""
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class RecommendationExplainer:
    """
    Genera explicaciones legibles para recomendaciones.
    
    Estudiante: explicaciones simples, motivadoras, en primera persona.
    Docente: información técnica (fuente del algoritmo, score, evidencia).
    """

    # Templates para estudiantes — simples y positivos
    STUDENT_TEMPLATES = {
        'collaborative': "👥 Otros estudiantes con intereses similares a los tuyos también consultaron este recurso.",
        'content_semantic': "🎯 Este recurso está muy relacionado con los temas que has explorado:{tags_hint}",
        'content_tags': "📚 Encontramos este recurso sobre los temas que más te interesan:{tags_hint}",
        'popular': "⭐ Es uno de los recursos más consultados en tu curso.",
        'sequential': "📈 Basado en tu progreso actual, este es el siguiente paso recomendado.",
        'cold_start_topic': "🚀 Recurso seleccionado especialmente para los temas de tu curso.",
        'cold_start_popular': "🔥 Un recurso muy popular entre los estudiantes de este curso.",
        'ensemble': "✨ Recomendado especialmente para ti según tu historial de aprendizaje.",
        'ensemble_rrf': "✨ Altamente recomendado según múltiples criterios de personalización.",
        'ensemble_voting': "✨ Recomendado por múltiples modelos de personalización.",
        'svd': "🤝 Usuarios con perfiles similares al tuyo valoraron positivamente este recurso.",
        'ncf': "🧠 Nuestro modelo de inteligencia artificial predice que te gustará este recurso.",
        'fallback': "📖 Recurso disponible en tu curso.",
        'generic': "📖 Recurso educativo disponible en la plataforma.",
    }

    # Templates para docentes — técnicos y con evidencia
    INSTRUCTOR_TEMPLATES = {
        'collaborative': "Filtrado colaborativo: basado en usuarios con historial de interacción similar.",
        'content_semantic': "Similitud semántica (pgvector HNSW): score={score:.3f}. Modelo: paraphrase-multilingual-mpnet-base-v2.",
        'content_tags': "Similitud por tags: coincidencia en categorías de contenido.",
        'popular': "Popularidad contextual: mayor número de interacciones únicas en este contexto.",
        'sequential': "Modelo secuencial (GRU4Rec): predicción de siguiente ítem en la secuencia de aprendizaje.",
        'cold_start_topic': "Cold-start por tema: usuario nuevo, recursos seleccionados por keywords del título del curso.",
        'cold_start_popular': "Cold-start popular: usuario nuevo, recursos más vistos en el contexto.",
        'ensemble': "Ensemble (weighted_average): combinación ponderada de SVD + NCF + Sequential + Híbrido.",
        'ensemble_rrf': "Ensemble (Reciprocal Rank Fusion): combinación por rango de múltiples modelos.",
        'svd': "SVD (Matrix Factorization): factorización de la matriz usuario-recurso con Surprise library.",
        'ncf': "NCF (Neural Collaborative Filtering): red neuronal con embeddings de usuario e ítem.",
        'fallback': "Fallback: recomendación de respaldo (engine principal no disponible).",
        'generic': "Genérico: recurso disponible sin personalización.",
    }

    @classmethod
    def explain_for_student(cls, rec: Dict, profile) -> str:
        """Explicación simple y motivadora para el estudiante."""
        source = rec.get('source', 'ensemble')
        # Strip variant suffix if present
        source_base = source.split('_')[0] if '_' in source else source

        template = cls.STUDENT_TEMPLATES.get(source, cls.STUDENT_TEMPLATES.get(source_base, ''))

        if not template:
            template = cls.STUDENT_TEMPLATES['ensemble']

        # Personalize with user's top tags
        tags_hint = ''
        if hasattr(profile, 'top_tags') and profile.top_tags:
            tags_hint = f" {', '.join(profile.top_tags[:3])}."

        return template.format(tags_hint=tags_hint, score=rec.get('score', 0))

    @classmethod
    def explain_for_instructor(cls, rec: Dict, profile) -> Dict:
        """Explicación técnica detallada para el docente."""
        source = rec.get('source', 'ensemble')
        source_base = source.split('_')[0] if '_' in source else source

        template = cls.INSTRUCTOR_TEMPLATES.get(
            source, cls.INSTRUCTOR_TEMPLATES.get(source_base, f"Fuente: {source}")
        )

        explanation = template.format(score=rec.get('score', 0))

        return {
            'source': source,
            'algorithm': explanation,
            'score': rec.get('score', 0),
            'score_pct': f"{rec.get('score', 0) * 100:.1f}%",
            'user_profile': {
                'is_new_user': getattr(profile, 'is_new_user', True),
                'preferred_types': getattr(profile, 'preferred_types', []),
                'top_tags': getattr(profile, 'top_tags', []),
                'completion_rate': f"{getattr(profile, 'completion_rate', 0):.0%}",
                'total_interactions': getattr(profile, 'total_interactions', 0),
            },
        }

    @classmethod
    def enrich_recommendations(
        cls,
        recs: List[Dict],
        profile,
        is_instructor: bool = False,
    ) -> List[Dict]:
        """
        Agrega explicaciones a la lista de recomendaciones.
        
        Para estudiantes: agrega 'explanation_text' (string simple).
        Para docentes: agrega 'explanation' (dict técnico) + 'explanation_text'.
        """
        for rec in recs:
            try:
                # Always add student explanation
                rec['explanation_text'] = cls.explain_for_student(rec, profile)

                if is_instructor:
                    rec['explanation'] = cls.explain_for_instructor(rec, profile)

            except Exception as e:
                logger.warning(f"Error generating explanation for rec {rec.get('id')}: {e}")
                rec['explanation_text'] = ''

        return recs
