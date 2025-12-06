"""
Servicio de Gestión de Perfiles de Usuario
Actualiza automáticamente los perfiles basándose en interacciones.
"""

import logging
from typing import Optional, Dict
from collections import Counter
from django.db.models import Avg, Count

logger = logging.getLogger(__name__)


class UserProfileService:
    """
    Servicio para gestionar perfiles de usuario y actualizar
    preferencias basándose en el historial de interacciones.
    """
    
    @staticmethod
    def get_or_create_profile(lti_user_id: str, launch_data: Dict = None):
        """
        Obtiene o crea un perfil de usuario.
        
        Args:
            lti_user_id: ID único del usuario LTI
            launch_data: Datos del lanzamiento LTI (opcional)
            
        Returns:
            Instancia de UserProfile
        """
        from lti_recommender_project.apps.users.models import UserProfile
        
        defaults = {}
        
        if launch_data:
            defaults['display_name'] = launch_data.get('name', '')
            defaults['email'] = launch_data.get('email', '')
        
        profile, created = UserProfile.objects.get_or_create(
            lti_user_id=lti_user_id,
            defaults=defaults
        )
        
        if created:
            logger.info(f"Nuevo perfil creado para usuario {lti_user_id}")
        
        return profile
    
    @staticmethod
    def update_profile_from_interaction(user_id: str, interaction):
        """
        Actualiza el perfil de usuario después de una interacción.
        
        Args:
            user_id: ID del usuario
            interaction: Instancia de UserInteraction
        """
        from lti_recommender_project.apps.users.models import UserProfile
        
        try:
            profile = UserProfile.objects.get(lti_user_id=user_id)
            
            # Actualizar contador de interacciones
            profile.total_interactions += 1
            
            # Actualizar tipos de recursos preferidos
            UserProfileService._update_preferred_types(profile, interaction.resource)
            
            # Actualizar tags de interés
            UserProfileService._update_interest_tags(profile, interaction.resource)
            
            # Actualizar promedio de completitud
            UserProfileService._update_average_completion(profile, user_id)
            
            # Actualizar promedio de ratings
            UserProfileService._update_average_rating(profile, user_id)
            
            # Inferir nivel del usuario
            UserProfileService._infer_user_level(profile, user_id)
            
            profile.save()
            logger.info(f"Perfil actualizado para usuario {user_id}")
            
        except UserProfile.DoesNotExist:
            logger.warning(f"Perfil no encontrado para usuario {user_id}")
    
    @staticmethod
    def _update_preferred_types(profile, resource):
        """Actualiza los tipos de recursos preferidos."""
        if not resource.resource_type:
            return
        
        if not profile.preferred_resource_types:
            profile.preferred_resource_types = {}
        
        resource_type = resource.resource_type
        current_count = profile.preferred_resource_types.get(resource_type, 0)
        profile.preferred_resource_types[resource_type] = current_count + 1
    
    @staticmethod
    def _update_interest_tags(profile, resource):
        """Actualiza los tags de interés del usuario."""
        if not resource.tags:
            return
        
        # Obtener tags actuales del perfil
        if profile.interest_tags:
            current_tags = [tag.strip() for tag in profile.interest_tags.split(',')]
        else:
            current_tags = []
        
        # Agregar nuevos tags del recurso
        new_tags = [tag.strip() for tag in resource.tags.split(',')]
        all_tags = current_tags + new_tags
        
        # Contar frecuencia y mantener los top 20 tags
        tag_counter = Counter(all_tags)
        top_tags = [tag for tag, _ in tag_counter.most_common(20)]
        
        profile.interest_tags = ', '.join(top_tags)
    
    @staticmethod
    def _update_average_completion(profile, user_id: str):
        """Actualiza el promedio de completitud del usuario."""
        from lti_recommender_project.apps.interactions.models import UserInteraction
        
        avg_completion = UserInteraction.objects.filter(
            lti_user_id=user_id,
            completion_percentage__isnull=False
        ).aggregate(
            avg=Avg('completion_percentage')
        )['avg']
        
        if avg_completion is not None:
            profile.average_completion = avg_completion
    
    @staticmethod
    def _update_average_rating(profile, user_id: str):
        """Actualiza el promedio de ratings del usuario."""
        from lti_recommender_project.apps.interactions.models import UserInteraction
        
        avg_rating = UserInteraction.objects.filter(
            lti_user_id=user_id,
            rating__isnull=False
        ).aggregate(
            avg=Avg('rating')
        )['avg']
        
        if avg_rating is not None:
            profile.average_rating = avg_rating
    
    @staticmethod
    def _infer_user_level(profile, user_id: str):
        """
        Infiere el nivel del usuario basándose en sus interacciones.
        """
        from lti_recommender_project.apps.interactions.models import UserInteraction
        
        # Obtener recursos con los que ha interactuado y su nivel de dificultad
        interactions = UserInteraction.objects.filter(
            lti_user_id=user_id,
            resource__difficulty_level__isnull=False
        ).select_related('resource')
        
        if not interactions.exists():
            # Sin suficientes datos, mantener como beginner
            return
        
        # Contar interacciones por nivel de dificultad
        level_counter = Counter()
        high_completion_levels = Counter()
        
        for interaction in interactions:
            level = interaction.resource.difficulty_level
            level_counter[level] += 1
            
            # Dar más peso a recursos completados exitosamente
            if interaction.completion_percentage and interaction.completion_percentage >= 70:
                high_completion_levels[level] += 2
        
        # Combinar contadores
        for level, count in high_completion_levels.items():
            level_counter[level] += count
        
        # Inferir nivel basándose en el patrón
        total = sum(level_counter.values())
        if total < 5:
            # Pocos datos, mantener nivel actual o beginner
            if not profile.inferred_level:
                profile.inferred_level = 'beginner'
            return
        
        # Calcular proporciones
        beginner_ratio = level_counter.get('beginner', 0) / total
        intermediate_ratio = level_counter.get('intermediate', 0) / total
        advanced_ratio = level_counter.get('advanced', 0) / total
        
        # Lógica de inferencia
        if advanced_ratio > 0.4 or (intermediate_ratio > 0.3 and advanced_ratio > 0.2):
            profile.inferred_level = 'advanced'
        elif intermediate_ratio > 0.4 or (beginner_ratio < 0.5 and intermediate_ratio > 0.2):
            profile.inferred_level = 'intermediate'
        else:
            profile.inferred_level = 'beginner'
    
    @staticmethod
    def infer_user_level(user_id: str) -> str:
        """
        Infiere y retorna el nivel del usuario.
        
        Args:
            user_id: ID del usuario
            
        Returns:
            Nivel inferido ('beginner', 'intermediate', 'advanced')
        """
        from lti_recommender_project.apps.users.models import UserProfile
        
        try:
            profile = UserProfile.objects.get(lti_user_id=user_id)
            UserProfileService._infer_user_level(profile, user_id)
            profile.save()
            return profile.inferred_level
        except UserProfile.DoesNotExist:
            return 'beginner'
    
    @staticmethod
    def extract_user_interests(user_id: str) -> str:
        """
        Extrae y retorna los tags de interés del usuario.
        
        Args:
            user_id: ID del usuario
            
        Returns:
            String de tags separados por comas
        """
        from lti_recommender_project.apps.users.models import UserProfile
        
        try:
            profile = UserProfile.objects.get(lti_user_id=user_id)
            return profile.interest_tags or  ""
        except UserProfile.DoesNotExist:
            return ""


# Función de conveniencia para obtener el servicio
def get_user_profile_service() -> UserProfileService:
    """Retorna una instancia del servicio de perfil de usuario."""
    return UserProfileService()
