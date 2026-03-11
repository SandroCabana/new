"""
StudentProfile — Perfil de estudiante enriquecido
Construido desde LTI claims + historial de interacciones.

Implementa:
- Cold-start detection (is_new_user)
- Pesos dinámicos por estado del usuario
- Cold-start handler usando contexto del curso
Referente: Coursera (skills x historial), Khan Academy (topic inference)
"""
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from collections import Counter

logger = logging.getLogger(__name__)


@dataclass
class StudentProfile:
    """
    Perfil de estudiante enriquecido construido desde:
    1. LTI claims (roles, contexto, locale, custom)
    2. Historial de interacciones (tags, tipos, completion rate)
    """
    lti_user_id: str
    context_id: str

    # Desde LTI claims
    roles: List[str] = field(default_factory=list)
    is_instructor: bool = False
    course_title: str = ""
    locale: str = "es"
    custom_subject: Optional[str] = None
    custom_level: Optional[str] = None

    # Derivados del historial
    preferred_types: List[str] = field(default_factory=list)
    preferred_difficulty: Optional[str] = None
    top_tags: List[str] = field(default_factory=list)
    completion_rate: float = 0.0       # 0.0 - 1.0
    avg_time_spent: float = 0.0        # segundos
    total_interactions: int = 0
    is_new_user: bool = True

    @classmethod
    def from_lti_launch(cls, launch_data: dict) -> 'StudentProfile':
        """Construye StudentProfile completo desde LTI launch data."""
        from lti_recommender_project.apps.lti_integration.lti_claims_extractor import (
            LTIClaimsExtractor
        )
        claims = LTIClaimsExtractor.extract_all(launch_data)

        profile = cls(
            lti_user_id=claims['user_id'],
            context_id=claims['context_id'],
            roles=claims['roles'],
            is_instructor=claims['is_instructor'],
            course_title=claims['context_title'],
            locale=claims['locale'],
            custom_subject=claims['custom_subject'],
            custom_level=claims['custom_level'],
        )
        profile._enrich_from_history()
        return profile

    @classmethod
    def from_ids(cls, user_id: str, context_id: str) -> 'StudentProfile':
        """Construye perfil solo desde IDs (útil para tareas async sin LTI context)."""
        profile = cls(lti_user_id=user_id, context_id=context_id)
        profile._enrich_from_history()
        return profile

    def _enrich_from_history(self):
        """Construye perfil derivado de interacciones previas en la DB."""
        try:
            from lti_recommender_project.apps.interactions.models import UserInteraction
            from django.db.models import Avg, Count

            interactions = list(
                UserInteraction.objects.filter(
                    lti_user_id=self.lti_user_id
                ).select_related('resource')
            )

            self.total_interactions = len(interactions)

            if not interactions:
                self.is_new_user = True
                return

            self.is_new_user = False

            # Tipos de recursos preferidos
            types = [
                i.resource.resource_type
                for i in interactions
                if i.resource and i.resource.resource_type
            ]
            self.preferred_types = [t for t, _ in Counter(types).most_common(3)]

            # Tags frecuentes
            all_tags = []
            for i in interactions:
                if i.resource and i.resource.tags:
                    all_tags.extend(t.strip() for t in i.resource.tags.split(',') if t.strip())
            self.top_tags = [t for t, _ in Counter(all_tags).most_common(5)]

            # Dificultad preferida = la más completada (>70%)
            completed = [
                i for i in interactions
                if (i.completion_percentage or 0) >= 70 and i.resource
            ]
            if completed:
                difficulties = [
                    i.resource.difficulty_level
                    for i in completed
                    if i.resource.difficulty_level
                ]
                if difficulties:
                    self.preferred_difficulty = Counter(difficulties).most_common(1)[0][0]

            # Métricas de engagement
            completions = [i.completion_percentage for i in interactions if i.completion_percentage]
            times = [i.time_spent for i in interactions if i.time_spent]

            self.completion_rate = (
                sum(completions) / len(completions) / 100
                if completions else 0.0
            )
            self.avg_time_spent = sum(times) / len(times) if times else 0.0

        except Exception as e:
            logger.warning(f"Error enriqueciendo perfil de {self.lti_user_id}: {e}")
            self.is_new_user = True

    def get_hybrid_weights(self) -> Dict[str, float]:
        """
        Pesos dinámicos para el engine híbrido según estado del usuario.
        
        Cold-start → más popularidad y contenido del curso.
        Usuario activo y comprometido → más CF y secuencial.
        Usuario promedio → balance.
        
        Referente: LinkedIn Learning ajusta pesos por nivel de actividad.
        """
        if self.is_new_user:
            return {
                'content': 0.50,
                'popular': 0.40,
                'collaborative': 0.00,
                'sequential': 0.10,
            }
        elif self.completion_rate >= 0.70 and self.total_interactions >= 10:
            # Usuario muy activo y comprometido
            return {
                'collaborative': 0.40,
                'sequential': 0.30,
                'content': 0.20,
                'popular': 0.10,
            }
        elif self.total_interactions >= 3:
            # Usuario promedio con algo de historial
            return {
                'collaborative': 0.30,
                'content': 0.35,
                'sequential': 0.20,
                'popular': 0.15,
            }
        else:
            # Usuario nuevo con pocas interacciones
            return {
                'content': 0.45,
                'popular': 0.35,
                'collaborative': 0.10,
                'sequential': 0.10,
            }

    def get_course_keywords(self) -> List[str]:
        """Extrae keywords del título del curso para cold-start."""
        if not self.course_title or self.course_title == 'N/A':
            return []
        stopwords = {
            'de', 'del', 'la', 'el', 'en', 'y', 'a', 'para', 'con', 'los',
            'las', 'un', 'una', 'al', 'por', 'es', 'su', 'se', 'que', 'no',
        }
        # Include custom subject if available
        text = f"{self.course_title} {self.custom_subject or ''}"
        words = text.lower().split()
        return [w for w in words if w not in stopwords and len(w) > 3][:5]

    def __repr__(self) -> str:
        return (
            f"StudentProfile(user={self.lti_user_id[:8]}..., "
            f"new={self.is_new_user}, "
            f"completion={self.completion_rate:.0%}, "
            f"interactions={self.total_interactions})"
        )
