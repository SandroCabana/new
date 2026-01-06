"""
Motor de Recomendaciones Híbrido
Combina filtrado basado en contenido, preferencias de usuario y popularidad.
"""

import logging
from typing import List, Dict, Optional
from collections import Counter, defaultdict
from django.db.models import Count, Avg, Q

logger = logging.getLogger(__name__)


class RecommendationEngine:
    """
    Motor de recomendaciones híbrido que combina:
    - 50% Similitud de contenido (embeddings semánticos)
    - 30% Preferencias de usuario (perfil y historial)
    - 20% Popularidad (interacciones y ratings)
    """
    
    def __init__(
        self, 
        content_weight: float = 0.5,
        user_weight: float = 0.3,
        popularity_weight: float = 0.2
    ):
        """
        Inicializa el motor de recomendaciones.
        
        Args:
            content_weight: Peso del filtrado basado en contenido
            user_weight: Peso de las preferencias de usuario
            popularity_weight: Peso de la popularidad
        """
        self.content_weight = content_weight
        self.user_weight = user_weight
        self.popularity_weight = popularity_weight
        
        # Validar que los pesos sumen 1.0
        total_weight = content_weight + user_weight + popularity_weight
        if abs(total_weight - 1.0) > 0.01:
            logger.warning(f"Los pesos no suman 1.0 (suman {total_weight}), normalizando...")
            self.content_weight /= total_weight
            self.user_weight /= total_weight
            self.popularity_weight /= total_weight
    
    def get_recommendations(
        self,
        user_id: str,
        context_id: str,
        limit: int = 5,
        exclude_viewed: bool = True
    ) -> List[Dict]:
        """
        Obtiene recomendaciones personalizadas para un usuario.
        
        Args:
            user_id: ID del usuario LTI
            context_id: ID del contexto/curso LTI
            limit: Número de recomendaciones a retornar
            exclude_viewed: Si es True, excluye recursos ya vistos
            
        Returns:
            Lista de recursos recomendados con scores
        """
        from lti_recommender_project.apps.resources.models import EducationalResource
        from lti_recommender_project.apps.interactions.models import UserInteraction
        from lti_recommender_project.apps.users.models import UserProfile
        
        try:
            # Obtener o crear perfil de usuario
            user_profile, _ = UserProfile.objects.get_or_create(
                lti_user_id=user_id,
                defaults={'display_name': user_id}
            )
            
            # Obtener recursos del contexto actual
            resources = EducationalResource.objects.filter(
                Q(lti_context_id=context_id) | Q(lti_context_id__isnull=True)
            )
            
            # Excluir recursos ya vistos si se solicita
            if exclude_viewed:
                viewed_ids = UserInteraction.objects.filter(
                    lti_user_id=user_id,
                    lti_context_id=context_id
                ).values_list('resource_id', flat=True)
                resources = resources.exclude(id__in=viewed_ids)
            
            if not resources.exists():
                logger.info(f"No hay recursos disponibles para recomendar en contexto {context_id}")
                return []
            
            # Calcular scores para cada recurso
            scored_resources = []
            
            for resource in resources:
                score = self._calculate_resource_score(
                    resource, 
                    user_profile, 
                    user_id,
                    context_id
                )
                scored_resources.append({
                    'resource': resource,
                    'score': score,
                    'title': resource.title,
                    'url': resource.url,
                    'description': resource.description,
                    'type': resource.resource_type,
                    'difficulty': resource.difficulty_level,
                    'id': resource.id,
                })
            
            # Ordenar por score descendente
            scored_resources.sort(key=lambda x: x['score'], reverse=True)
            
            # Retornar top N
            return scored_resources[:limit]
            
        except Exception as e:
            logger.error(f"Error en get_recommendations: {e}")
            return self._fallback_recommendations(context_id, limit)
    
    def _calculate_resource_score(
        self,
        resource,
        user_profile,
        user_id: str,
        context_id: str
    ) -> float:
        """
        Calcula el score total de un recurso combinando las tres estrategias.
        
        Returns:
            Score total del recurso (0-1)
        """
        # 1. Score de contenido (similitud semántica)
        content_score = self._content_based_score(resource, user_id, context_id)
        
        # 2. Score de usuario (preferencias y nivel)
        user_score = self._user_based_score(resource, user_profile)
        
        # 3. Score de popularidad
        popularity_score = self._popularity_score(resource, context_id)
        
        # Combinar scores con pesos
        total_score = (
            self.content_weight * content_score +
            self.user_weight * user_score +
            self.popularity_weight * popularity_score
        )
        
        return total_score
    
    def _content_based_score(
        self, 
        resource, 
        user_id: str,
        context_id: str
    ) -> float:
        """
        Calcula score basado en similitud de contenido.
        Usa embeddings semánticos de recursos previamente interactuados.
        """
        from lti_recommender_project.apps.interactions.models import UserInteraction
        from lti_recommender_project.apps.recommendations.services.embedding_service import get_embedding_service
        
        try:
            # Si el recurso no tiene embedding, retornar score neutro
            if not resource.embedding:
                return 0.5
            
            # Obtener recursos con los que el usuario ha interactuado positivamente
            positive_interactions = UserInteraction.objects.filter(
                lti_user_id=user_id,
                lti_context_id=context_id
            ).filter(
                Q(completion_percentage__gte=50) |  # Completó más del 50%
                Q(rating__gte=3) |  # Rating >= 3
                Q(interaction_type='completed')
            ).select_related('resource').order_by('-timestamp')[:10]
            
            if not positive_interactions.exists():
                return 0.5  # Sin historial, score neutro
            
            # Calcular similitud promedio con recursos previos
            embedding_service = get_embedding_service()
            similarities = []
            
            for interaction in positive_interactions:
                similar_resources = embedding_service.get_similar_resources(
                    interaction.resource.id,
                    limit=100,  # Buscar en un pool grande
                    min_similarity=0.0
                )
                
                for similar in similar_resources:
                    if similar['resource'].id == resource.id:
                        similarities.append(similar['similarity'])
                        break
            
            if similarities:
                return sum(similarities) / len(similarities)
            else:
                return 0.5
                
        except Exception as e:
            logger.error(f"Error en _content_based_score: {e}")
            return 0.5
    
    def _user_based_score(self, resource, user_profile) -> float:
        """
        Calcula score basado en las preferencias del usuario.
        """
        score = 0.5  # Base neutra
        
        try:
            # 1. Ajustar por nivel del usuario vs dificultad del recurso
            if resource.difficulty_level:
                level_mapping = {
                    'beginner': {'beginner': 1.0, 'intermediate': 0.6, 'advanced': 0.3},
                    'intermediate': {'beginner': 0.5, 'intermediate': 1.0, 'advanced': 0.7},
                    'advanced': {'beginner': 0.3, 'intermediate': 0.7, 'advanced': 1.0},
                }
                
                if user_profile.inferred_level in level_mapping:
                    level_score = level_mapping[user_profile.inferred_level].get(
                        resource.difficulty_level, 
                        0.5
                    )
                    score = score * 0.4 + level_score * 0.6
            
            # 2. Ajustar por tipos de recursos preferidos
            if user_profile.preferred_resource_types and resource.resource_type:
                total_interactions = sum(user_profile.preferred_resource_types.values())
                if total_interactions > 0:
                    type_frequency = user_profile.preferred_resource_types.get(
                        resource.resource_type, 
                        0
                    )
                    type_score = type_frequency / total_interactions
                    score = score * 0.6 + type_score * 0.4
            
            # 3. Boost para recursos con tags de interés del usuario
            if user_profile.interest_tags and resource.tags:
                user_tags = set(tag.strip().lower() for tag in user_profile.interest_tags.split(','))
                resource_tags = set(tag.strip().lower() for tag in resource.tags.split(','))
                
                if user_tags and resource_tags:
                    overlap = len(user_tags & resource_tags)
                    if overlap > 0:
                        tag_score = min(overlap / len(user_tags), 1.0)
                        score = score * 0.7 + tag_score * 0.3
            
            return min(max(score, 0.0), 1.0)  # Clamp entre 0 y 1
            
        except Exception as e:
            logger.error(f"Error en _user_based_score: {e}")
            return 0.5
    
    def _popularity_score(self, resource, context_id: str) -> float:
        """
        Calcula score basado en popularidad del recurso.
        """
        from lti_recommender_project.apps.interactions.models import UserInteraction
        
        try:
            # Obtener estadísticas del recurso en el contexto
            stats = UserInteraction.objects.filter(
                resource=resource,
                lti_context_id=context_id
            ).aggregate(
                total_views=Count('id'),
                avg_rating=Avg('rating'),
                avg_completion=Avg('completion_percentage')
            )
            
            total_views = stats['total_views'] or 0
            avg_rating = stats['avg_rating'] or 0
            avg_completion = stats['avg_completion'] or 0
            
            # Normalizar métricas
            # View score (log scale para suavizar)
            import math
            view_score = min(math.log(total_views + 1) / math.log(50), 1.0)  # 50 vistas = máximo
            
            # Rating score (normalizar 1-5 a 0-1)
            rating_score = (avg_rating - 1) / 4 if avg_rating > 0 else 0.5
            
            # Completion score (ya está en 0-100, normalizar a 0-1)
            completion_score = avg_completion / 100 if avg_completion > 0 else 0.5
            
            # Combinar métricas de popularidad
            popularity = (
                0.4 * view_score +
                0.4 * rating_score +
                0.2 * completion_score
            )
            
            return popularity
            
        except Exception as e:
            logger.error(f"Error en _popularity_score: {e}")
            return 0.5
    
    def _fallback_recommendations(self, context_id: str, limit: int) -> List[Dict]:
        """
        Recomendaciones de fallback en caso de error.
        Retorna los recursos más populares del contexto.
        """
        from lti_recommender_project.apps.resources.models import EducationalResource
        from lti_recommender_project.apps.interactions.models import UserInteraction
        
        try:
            # Obtener recursos ordenados por número de interacciones
            popular_resources = EducationalResource.objects.filter(
                Q(lti_context_id=context_id) | Q(lti_context_id__isnull=True)
            ).annotate(
                interaction_count=Count('interactions')
            ).order_by('-interaction_count')[:limit]
            
            return [
                {
                    'resource': res,
                    'score': 0.5,
                    'title': res.title,
                    'url': res.url,
                    'description': res.description,
                    'type': res.resource_type,
                }
                for res in popular_resources
            ]
            
        except Exception as e:
            logger.error(f"Error en _fallback_recommendations: {e}")
            return []


# Instancia global singleton
_recommendation_engine_instance = None


def get_recommendation_engine() -> RecommendationEngine:
    """
    Obtiene la instancia singleton del motor de recomendaciones.
    
    Returns:
        Instancia de RecommendationEngine
    """
    global _recommendation_engine_instance
    
    if _recommendation_engine_instance is None:
        _recommendation_engine_instance = RecommendationEngine()
    
    return _recommendation_engine_instance
