"""
Motor de Recomendaciones Híbrido — v2
Combina filtrado colaborativo, similitud de contenido semántico y popularidad.
Pesos DINÁMICOS según estado del StudentProfile (cold-start vs activo).

Mejoras vs v1:
- Pesos dinámicos por perfil de usuario (no hardcoded)
- Content-based usa embeddings semánticos (pgvector) no tags__icontains
- Cold-start inteligente con keywords del curso
- Fallback aleatorio reemplazado por popularidad real
"""
import logging
from typing import List, Dict, Any, Optional
from collections import defaultdict, Counter
from django.db.models import Count, Q

logger = logging.getLogger(__name__)


class RecommendationEngine:
    """
    Motor de recomendaciones híbrido.
    Los pesos se aplican desde StudentProfile.get_hybrid_weights().
    """

    def __init__(self, content_weight=0.5, user_weight=0.3, popularity_weight=0.2):
        # Normalize weights so they sum to 1
        total = content_weight + user_weight + popularity_weight
        if total > 0:
            self.content_weight = content_weight / total
            self.user_weight = user_weight / total
            self.popularity_weight = popularity_weight / total
        else:
            self.content_weight = 0.5
            self.user_weight = 0.3
            self.popularity_weight = 0.2

    def get_recommendations(
        self,
        user_id: str,
        context_id: str,
        limit: int = 5,
        exclude_viewed: bool = True,
        student_profile=None,
    ) -> List[Dict[str, Any]]:
        """
        Obtiene recomendaciones personalizadas usando pesos dinámicos del StudentProfile.
        """
        from lti_recommender_project.apps.resources.models import EducationalResource
        from lti_recommender_project.apps.interactions.models import UserInteraction

        try:
            # Get or build student profile
            if student_profile is None:
                from lti_recommender_project.apps.users.student_profile import StudentProfile
                student_profile = StudentProfile.from_ids(user_id, context_id)

            # Get dynamic weights
            weights = student_profile.get_hybrid_weights()

            # Get viewed resources
            viewed_ids = set()
            if exclude_viewed:
                viewed_ids = set(
                    UserInteraction.objects.filter(
                        lti_user_id=user_id
                    ).values_list('resource_id', flat=True)
                )

            # Handle cold-start immediately
            if student_profile.is_new_user:
                return self._handle_cold_start(student_profile, context_id, viewed_ids, limit)

            # --- Strategy 1: Collaborative Filtering ---
            collaborative_recs = self._collaborative_filtering(
                user_id, context_id, viewed_ids, limit * 2
            )

            # --- Strategy 2: Content-Based (Semantic Embeddings) ---
            content_recs = self._content_based_semantic(
                user_id, context_id, viewed_ids, limit * 2
            )

            # --- Strategy 3: Popular in Context ---
            popular_recs = self._popular_in_context(context_id, viewed_ids, limit * 2)

            # Combine with dynamic weights
            combined = self._combine_recommendations(
                collaborative=collaborative_recs,
                content=content_recs,
                popular=popular_recs,
                weights=weights,
                limit=limit,
            )

            # Fill to limit if needed
            if len(combined) < limit:
                generic = self._get_generic_resources(viewed_ids, limit - len(combined))
                combined.extend(generic)

            return self._format_recommendations(combined[:limit])

        except Exception as e:
            logger.error(f"Error generating recommendations for {user_id}: {e}", exc_info=True)
            return self._get_fallback_recommendations(context_id, limit)

    def _handle_cold_start(
        self,
        profile,
        context_id: str,
        viewed_ids: set,
        limit: int,
    ) -> List[Dict[str, Any]]:
        """
        Cold-start: usuario nuevo sin historial.
        Estrategia: populares en contexto + recursos relacionados con keywords del curso.
        Referente: Khan Academy (topic inference del nombre del curso).
        """
        from lti_recommender_project.apps.resources.models import EducationalResource

        combined = []
        seen_ids = set()

        # 1. Recursos relacionados con el tema del curso (por keywords)
        keywords = profile.get_course_keywords()
        if keywords:
            keyword_q = Q()
            for kw in keywords[:3]:
                keyword_q |= Q(tags__icontains=kw) | Q(title__icontains=kw)

            topic_resources = list(
                EducationalResource.objects.filter(keyword_q)
                .exclude(id__in=viewed_ids)
                .order_by('difficulty_level')[:int(limit * 0.6)]
            )
            for r in topic_resources:
                if r.id not in seen_ids:
                    combined.append((r, 'cold_start_topic', 0.70))
                    seen_ids.add(r.id)

        # 2. Populares en el contexto (fillup)
        popular = self._popular_in_context(context_id, viewed_ids | seen_ids, limit)
        for r, src, score in popular:
            if len(combined) >= limit:
                break
            if r.id not in seen_ids:
                combined.append((r, 'cold_start_popular', 0.60))
                seen_ids.add(r.id)

        return self._format_recommendations(combined[:limit])

    def _collaborative_filtering(
        self,
        user_id: str,
        context_id: str,
        exclude_ids: set,
        limit: int,
    ) -> List[tuple]:
        """Filtrado colaborativo: recursos que usuarios similares interactuaron."""
        from lti_recommender_project.apps.resources.models import EducationalResource
        from lti_recommender_project.apps.interactions.models import UserInteraction

        user_resources = list(
            UserInteraction.objects.filter(
                lti_user_id=user_id
            ).values_list('resource_id', flat=True)
        )

        if not user_resources:
            return []

        similar_user_ids = list(
            UserInteraction.objects.filter(
                resource_id__in=user_resources
            ).exclude(
                lti_user_id=user_id
            ).values_list('lti_user_id', flat=True).distinct()[:100]
        )

        if not similar_user_ids:
            return []

        resources = list(
            EducationalResource.objects.filter(
                interactions__lti_user_id__in=similar_user_ids
            ).exclude(
                id__in=exclude_ids
            ).annotate(
                interaction_count=Count('interactions')
            ).order_by('-interaction_count')[:limit]
        )

        return [(r, 'collaborative', 0.80) for r in resources]

    def _content_based_semantic(
        self,
        user_id: str,
        context_id: str,
        exclude_ids: set,
        limit: int,
    ) -> List[tuple]:
        """
        Content-based usando embeddings semánticos.
        Construye un 'user embedding' como promedio ponderado de los vistos.
        Luego busca recursos similares con pgvector.
        """
        from lti_recommender_project.apps.interactions.models import UserInteraction
        from lti_recommender_project.apps.resources.models import EducationalResource
        import numpy as np

        interactions = list(
            UserInteraction.objects.filter(
                lti_user_id=user_id
            ).select_related('resource').order_by('-resource__updated_at')[:20]
        )

        if not interactions:
            return []

        # Build user embedding as weighted average
        embeddings = []
        weights = []
        for interaction in interactions:
            resource = interaction.resource
            # Fix: explicitly check 'is not None' because numpy arrays raise ValueError on truth checks
            if resource and getattr(resource, 'embedding', None) is not None:
                emb = resource.embedding
                if isinstance(emb, list):
                    emb = np.array(emb)
                # Weight by completion (or 0.5 default)
                w = (interaction.completion_percentage or 50) / 100
                embeddings.append(emb)
                weights.append(w)

        if not embeddings:
            # Fallback: tag/type based (old method)
            return self._content_based_tags(user_id, context_id, exclude_ids, limit)

        # Weighted average embedding
        weights_arr = np.array(weights)
        weighted_sum = sum(w * e for w, e in zip(weights_arr, embeddings))
        user_embedding = weighted_sum / weights_arr.sum()
        # Normalize
        norm = np.linalg.norm(user_embedding)
        if norm > 0:
            user_embedding = user_embedding / norm

        try:
            from lti_recommender_project.apps.recommendations.services.embedding_service import (
                get_embedding_service
            )
            service = get_embedding_service()
            similar = service.get_similar_resources_pgvector(
                query_embedding=user_embedding.tolist(),
                limit=limit,
                context_id=context_id,
                exclude_ids=exclude_ids,
                min_similarity=0.25,
            )
            return [(r, 'content_semantic', r.get('score', 0.5)) for r in similar]
        except Exception as e:
            logger.warning(f"pgvector search failed, using tag fallback: {e}")
            return self._content_based_tags(user_id, context_id, exclude_ids, limit)

    def _content_based_tags(
        self,
        user_id: str,
        context_id: str,
        exclude_ids: set,
        limit: int,
    ) -> List[tuple]:
        """Fallback content-based usando tags (método original)."""
        from lti_recommender_project.apps.interactions.models import UserInteraction
        from lti_recommender_project.apps.resources.models import EducationalResource

        user_interactions = UserInteraction.objects.filter(
            lti_user_id=user_id
        ).select_related('resource')

        if not user_interactions.exists():
            return []

        resource_types, tags_list = [], []
        for interaction in user_interactions:
            resource = interaction.resource
            if resource.resource_type:
                resource_types.append(resource.resource_type)
            if resource.tags:
                tags_list.extend(t.strip() for t in resource.tags.split(','))

        most_common_type = Counter(resource_types).most_common(1)
        most_common_tags = [tag for tag, _ in Counter(tags_list).most_common(3)]

        query = Q()
        if most_common_type:
            query |= Q(resource_type=most_common_type[0][0])
        for tag in most_common_tags:
            query |= Q(tags__icontains=tag)

        resources = list(
            EducationalResource.objects.filter(query)
            .exclude(id__in=exclude_ids)
            .distinct()[:limit]
        )
        return [(r, 'content_tags', 0.65) for r in resources]

    def _popular_in_context(
        self,
        context_id: str,
        exclude_ids: set,
        limit: int,
    ) -> List[tuple]:
        """Recursos populares por views únicas en el contexto."""
        from lti_recommender_project.apps.resources.models import EducationalResource

        resources = list(
            EducationalResource.objects.filter(
                Q(lti_context_id=context_id) | Q(lti_context_id__isnull=True)
            ).exclude(
                id__in=exclude_ids
            ).annotate(
                view_count=Count(
                    'interactions',
                    filter=Q(interactions__interaction_type='viewed'),
                    distinct=True,
                )
            ).order_by('-view_count')[:limit]
        )
        return [(r, 'popular', 0.55) for r in resources]

    def _get_generic_resources(self, exclude_ids: set, limit: int) -> List[tuple]:
        """Recursos genéricos para llenar cuando no hay suficientes."""
        from lti_recommender_project.apps.resources.models import EducationalResource

        resources = list(
            EducationalResource.objects.filter(
                lti_context_id__isnull=True
            ).exclude(
                id__in=exclude_ids
            ).order_by('-created_at')[:limit]  # Más recientes (no random)
        )
        return [(r, 'generic', 0.40) for r in resources]

    def _combine_recommendations(
        self,
        collaborative: List[tuple],
        content: List[tuple],
        popular: List[tuple],
        weights: Dict[str, float],
        limit: int,
    ) -> List[tuple]:
        """
        Combina resultados usando pesos dinámicos del StudentProfile.
        Interleaves para garantizar diversidad.
        """
        combined = []
        seen_ids = set()

        sources_and_weights = [
            (collaborative, weights.get('collaborative', 0.30)),
            (content, weights.get('content', 0.35)),
            (popular, weights.get('popular', 0.15)),
        ]

        counts = {
            'collaborative': max(1, int(limit * weights.get('collaborative', 0.30))),
            'content': max(1, int(limit * weights.get('content', 0.35))),
            'popular': max(1, int(limit * weights.get('popular', 0.15))),
        }

        for recs, weight in sources_and_weights:
            for item in recs:
                if len(combined) >= limit:
                    break
                if isinstance(item, dict):
                    # Direct dict result
                    rid = item.get('id')
                    if rid and rid not in seen_ids:
                        combined.append(item)
                        seen_ids.add(rid)
                else:
                    r, src, score = item
                    rid = r.get('id') if isinstance(r, dict) else r.id
                    if rid and rid not in seen_ids:
                        combined.append((r, src, score))
                        seen_ids.add(rid)

    def _format_recommendations(self, resources: List[tuple]) -> List[Dict[str, Any]]:
        """Formatea recursos al formato de respuesta estándar y normaliza scores de 0 a 1."""
        result = []
        
        # Encontrar el score máximo para normalizar si alguno supera 1.0
        max_score = 1.0
        for item in resources:
            if isinstance(item, dict):
                score = float(item.get('score', 0))
            else:
                score = float(item[2])
            if score > max_score:
                max_score = score
                
        for item in resources:
            if isinstance(item, dict):
                # Es un diccionario que ya vino directo
                raw_score = float(item.get('score', 0))
                normalized_score = raw_score / max_score if max_score > 0 else 0
                item['score'] = round(normalized_score, 4)
                result.append(item)
                continue
            
            resource, source, score = item
            raw_score = float(score)
            normalized_score = raw_score / max_score if max_score > 0 else 0
            
            if isinstance(resource, dict):
                # Es un diccionario de pgvector
                result.append({
                    'id': resource.get('id'),
                    'title': resource.get('title', 'Recurso'),
                    'url': resource.get('url', '#'),
                    'description': resource.get('description', 'Recurso educativo recomendado'),
                    'type': resource.get('resource_type', ''),
                    'author': resource.get('author', 'Desconocido'),
                    'tags': resource.get('tags', ''),
                    'difficulty': resource.get('difficulty_level', 'N/A'),
                    'score': round(normalized_score, 4),
                    'source': source,
                })
            else:
                # Es un objeto modelo de Django
                result.append({
                    'id': resource.id,
                    'title': resource.title,
                    'url': resource.url,
                    'description': resource.description or 'Recurso educativo recomendado',
                    'type': resource.resource_type,
                    'author': resource.author or 'Desconocido',
                    'tags': resource.tags or '',
                    'difficulty': resource.difficulty_level or 'N/A',
                    'score': round(normalized_score, 4),
                    'source': source,
                })
        return result

    def _get_fallback_recommendations(self, context_id: str, limit: int) -> List[Dict[str, Any]]:
        """Recomendaciones de respaldo en caso de error general."""
        try:
            from lti_recommender_project.apps.resources.models import EducationalResource
            resources = list(
                EducationalResource.objects.filter(
                    Q(lti_context_id=context_id) | Q(lti_context_id__isnull=True)
                ).order_by('-created_at')[:limit]
            )
            return self._format_recommendations([(r, 'fallback', 0.30) for r in resources])
        except Exception as e:
            logger.error(f"Fallback also failed: {e}")
            return [{'title': 'No hay recomendaciones disponibles', 'url': '#'}]


# Singleton
_engine_instance: Optional[RecommendationEngine] = None


def get_recommendation_engine() -> RecommendationEngine:
    """Singleton del motor de recomendaciones."""
    global _engine_instance
    if _engine_instance is None:
        from django.conf import settings
        config = getattr(settings, 'RECOMMENDATION_CONFIG', {})
        _engine_instance = RecommendationEngine(
            content_weight=config.get('CONTENT_WEIGHT', 0.5),
            user_weight=config.get('USER_WEIGHT', 0.3),
            popularity_weight=config.get('POPULARITY_WEIGHT', 0.2),
        )
    return _engine_instance
