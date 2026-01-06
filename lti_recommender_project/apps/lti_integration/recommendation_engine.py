"""
Motor de Recomendaciones Inteligente
Combina filtrado colaborativo y similitud de contenido
"""
import logging
from typing import List, Dict, Any
from collections import defaultdict, Counter
from django.db.models import Count, Q
from lti_recommender_project.apps.resources.models import EducationalResource
from lti_recommender_project.apps.interactions.models import UserInteraction

logger = logging.getLogger(__name__)


class RecommendationEngine:
    """
    Motor de recomendaciones híbrido que combina:
    1. Filtrado colaborativo (basado en usuarios similares)
    2. Similitud de contenido (basado en tags y tipo de recurso)
    3. Popularidad (recursos más vistos en el contexto)
    """
    
    def __init__(self):
        self.min_interactions = 1  # Mínimo de interacciones para considerar un usuario
        
    def get_recommendations(
        self, 
        user_id: str, 
        context_id: str, 
        limit: int = 5,
        exclude_viewed: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Obtiene recomendaciones personalizadas para un usuario
        
        Args:
            user_id: ID del usuario LTI
            context_id: ID del contexto LTI (curso)
            limit: Número máximo de recomendaciones
            exclude_viewed: Si True, excluye recursos ya vistos por el usuario
            
        Returns:
            Lista de diccionarios con información de recursos recomendados
        """
        try:
            # Obtener recursos ya vistos por el usuario
            viewed_resources = set()
            if exclude_viewed:
                viewed_resources = set(
                    UserInteraction.objects.filter(
                        lti_user_id=user_id
                    ).values_list('resource_id', flat=True)
                )
            
            # Estrategia 1: Recomendaciones basadas en interacciones (Collaborative Filtering)
            collaborative_recs = self._collaborative_filtering(
                user_id, context_id, viewed_resources, limit * 2
            )
            
            # Estrategia 2: Recomendaciones basadas en contenido
            content_recs = self._content_based_filtering(
                user_id, context_id, viewed_resources, limit * 2
            )
            
            # Estrategia 3: Recursos populares en el contexto
            popular_recs = self._popular_in_context(
                context_id, viewed_resources, limit * 2
            )
            
            # Combinar y diversificar recomendaciones
            combined_recs = self._combine_recommendations(
                collaborative_recs,
                content_recs,
                popular_recs,
                limit
            )
            
            # Si no hay suficientes recomendaciones, agregar recursos genéricos
            if len(combined_recs) < limit:
                generic_recs = self._get_generic_resources(
                    viewed_resources, 
                    limit - len(combined_recs)
                )
                combined_recs.extend(generic_recs)
            
            # Formatear para la vista
            return self._format_recommendations(combined_recs[:limit])
            
        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")
            return self._get_fallback_recommendations(context_id, limit)
    
    def _collaborative_filtering(
        self, 
        user_id: str, 
        context_id: str, 
        exclude_ids: set, 
        limit: int
    ) -> List[EducationalResource]:
        """
        Filtrado colaborativo: recomienda recursos que usuarios similares han visto
        """
        # Obtener recursos que el usuario ha visto
        user_resources = UserInteraction.objects.filter(
            lti_user_id=user_id
        ).values_list('resource_id', flat=True)
        
        if not user_resources:
            return []
        
        # Encontrar usuarios que han visto recursos similares
        similar_users = UserInteraction.objects.filter(
            resource_id__in=user_resources
        ).exclude(
            lti_user_id=user_id
        ).values_list('lti_user_id', flat=True).distinct()
        
        if not similar_users:
            return []
        
        # Obtener recursos que esos usuarios han visto
        recommended_resources = EducationalResource.objects.filter(
            interactions__lti_user_id__in=similar_users
        ).exclude(
            id__in=exclude_ids
        ).annotate(
            interaction_count=Count('interactions')
        ).order_by('-interaction_count')[:limit]
        
        return list(recommended_resources)
    
    def _content_based_filtering(
        self, 
        user_id: str, 
        context_id: str, 
        exclude_ids: set, 
        limit: int
    ) -> List[EducationalResource]:
        """
        Filtrado basado en contenido: recomienda recursos similares a los que el usuario ha visto
        """
        # Obtener recursos que el usuario ha interactuado
        user_interactions = UserInteraction.objects.filter(
            lti_user_id=user_id
        ).select_related('resource')
        
        if not user_interactions.exists():
            return []
        
        # Extraer características de los recursos vistos
        resource_types = []
        tags_list = []
        
        for interaction in user_interactions:
            resource = interaction.resource
            if resource.resource_type:
                resource_types.append(resource.resource_type)
            if resource.tags:
                tags_list.extend([tag.strip() for tag in resource.tags.split(',')])
        
        # Encontrar los tipos y tags más comunes
        most_common_type = Counter(resource_types).most_common(1)
        most_common_tags = [tag for tag, _ in Counter(tags_list).most_common(3)]
        
        # Buscar recursos similares
        query = Q()
        if most_common_type:
            query |= Q(resource_type=most_common_type[0][0])
        
        for tag in most_common_tags:
            query |= Q(tags__icontains=tag)
        
        similar_resources = EducationalResource.objects.filter(query).exclude(
            id__in=exclude_ids
        ).distinct()[:limit]
        
        return list(similar_resources)
    
    def _popular_in_context(
        self, 
        context_id: str, 
        exclude_ids: set, 
        limit: int
    ) -> List[EducationalResource]:
        """
        Recursos populares en el contexto actual
        """
        popular = EducationalResource.objects.filter(
            Q(lti_context_id=context_id) | Q(lti_context_id__isnull=True)
        ).exclude(
            id__in=exclude_ids
        ).annotate(
            view_count=Count('interactions', filter=Q(interactions__interaction_type='viewed'))
        ).order_by('-view_count')[:limit]
        
        return list(popular)
    
    def _get_generic_resources(
        self, 
        exclude_ids: set, 
        limit: int
    ) -> List[tuple]:
        """
        Recursos genéricos cuando no hay suficientes recomendaciones personalizadas
        Retorna: List[tuple(resource, source, score)]
        """
        generic = EducationalResource.objects.filter(
            lti_context_id__isnull=True
        ).exclude(
            id__in=exclude_ids
        ).order_by('?')[:limit]
        
        # Retornar como tuplas con score genérico de 50%
        return [(resource, 'generic', 50) for resource in generic]
    
    def _combine_recommendations(
        self,
        collaborative: List[EducationalResource],
        content: List[EducationalResource],
        popular: List[EducationalResource],
        limit: int
    ) -> List[tuple]:
        """
        Combina y diversifica recomendaciones de diferentes fuentes
        Prioridad: 40% collaborative, 40% content, 20% popular
        Retorna: List[tuple(resource, source, score)]
        """
        combined = []
        seen_ids = set()
        
        # Intercalar recomendaciones para diversidad
        # Scores base por fuente: collaborative=85, content=75, popular=60
        sources = [
            (collaborative, 0.4, 'collaborative', 85),
            (content, 0.4, 'content', 75),
            (popular, 0.2, 'popular', 60)
        ]
        
        # Calcular cuántos de cada fuente
        counts = {
            'collaborative': int(limit * 0.4),
            'content': int(limit * 0.4),
            'popular': int(limit * 0.2)
        }
        
        # Agregar de cada fuente con su score
        for recs, weight, source_name, base_score in sources:
            count = counts[source_name]
            added_from_source = 0
            
            for idx, resource in enumerate(recs):
                if len(combined) >= limit:
                    break
                if resource.id not in seen_ids:
                    # Decrementar score ligeramente por posición (max 15 puntos)
                    position_penalty = min(idx * 3, 15)
                    score = max(base_score - position_penalty, 40)
                    
                    combined.append((resource, source_name, score))
                    seen_ids.add(resource.id)
                    added_from_source += 1
                    if added_from_source >= count:
                        break
        
        # Rellenar con cualquier recomendación restante
        for recs, _, source_name, base_score in sources:
            for idx, resource in enumerate(recs):
                if len(combined) >= limit:
                    break
                if resource.id not in seen_ids:
                    position_penalty = min(idx * 3, 15)
                    score = max(base_score - position_penalty - 10, 35)  # Penalizar extras
                    combined.append((resource, source_name, score))
                    seen_ids.add(resource.id)
        
        return combined
    
    def _format_recommendations(
        self, 
        resources: List[tuple]
    ) -> List[Dict[str, Any]]:
        """
        Formatea recursos para la vista
        Acepta: List[tuple(resource, source, score)]
        """
        return [
            {
                "title": resource.title,
                "url": resource.url,
                "description": resource.description or "Recurso educativo recomendado",
                "type": resource.resource_type,
                "author": resource.author or "Desconocido",
                "tags": resource.tags or "",
                "difficulty": resource.difficulty_level or "N/A",
                "score": score,  # Porcentaje de confianza (0-100)
                "id": resource.id  # ID del recurso para tracking
            }
            for resource, source, score in resources
        ]
    
    def _get_fallback_recommendations(
        self, 
        context_id: str, 
        limit: int
    ) -> List[Dict[str, Any]]:
        """
        Recomendaciones de respaldo en caso de error
        """
        try:
            resources = EducationalResource.objects.filter(
                Q(lti_context_id=context_id) | Q(lti_context_id__isnull=True)
            ).order_by('?')[:limit]
            
            return self._format_recommendations(list(resources))
        except Exception as e:
            logger.error(f"Error in fallback recommendations: {e}")
            return [{
                "title": "No hay recomendaciones disponibles",
                "url": "#",
                "description": "Intenta agregar más recursos al sistema",
                "type": "other"
            }]
