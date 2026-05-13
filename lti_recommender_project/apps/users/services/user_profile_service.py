"""
Servicio de Gestión de Perfiles de Usuario
Actualiza automáticamente los perfiles basándose en interacciones.
"""

import logging
from typing import Optional, Dict, Tuple
from collections import Counter
from django.db.models import Avg, Count
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)
User = get_user_model()


class UserProfileService:
    """
    Servicio para gestionar perfiles de usuario y actualizar
    preferencias basándose en el historial de interacciones.
    """
    
    @staticmethod
    def get_or_create_profile(sub: str, issuer: str, launch_data: Dict = None):
        """
        Obtiene o crea un perfil de usuario (GlobalUser + LTIIdentity).
        """
        from lti_recommender_project.apps.users.models import GlobalUser, LTIIdentity
        
        email = launch_data.get('email', '') if launch_data else ''
        name = launch_data.get('name', '') if launch_data else ''
        role = launch_data.get('role', 'Learner') if launch_data else 'Learner'
        
        # Primero intentar encontrar GlobalUser por email
        global_user = None
        if email:
            global_user = GlobalUser.objects.filter(email__iexact=email).first()
            
        if not global_user:
            # Intentar encontrar por LTIIdentity existente
            identity = LTIIdentity.objects.filter(sub=sub, issuer=issuer).first()
            if identity:
                global_user = identity.global_user
        
        if not global_user:
            # Create a new GlobalUser
            global_user = GlobalUser.objects.create(
                email=email,
                display_name=name
            )
            logger.info(f"Nuevo GlobalUser creado: {global_user.id}")
            
        # Get or create LTIIdentity
        identity, created = LTIIdentity.objects.get_or_create(
            issuer=issuer,
            sub=sub,
            defaults={
                'global_user': global_user,
                'role': role
            }
        )
        
        if created:
            logger.info(f"Nueva LTIIdentity creada para {sub} @ {issuer}")
            
        return global_user
    
    @staticmethod
    def update_profile_from_interaction(global_user_id, interaction):
        """
        Actualiza el perfil de usuario después de una interacción.
        """
        from lti_recommender_project.apps.users.models import GlobalUser
        
        try:
            profile = GlobalUser.objects.get(id=global_user_id)
            
            profile.total_interactions += 1
            UserProfileService._update_preferred_types(profile, interaction.resource)
            UserProfileService._update_interest_tags(profile, interaction.resource)
            UserProfileService._update_average_completion(profile, global_user_id)
            UserProfileService._update_average_rating(profile, global_user_id)
            UserProfileService._infer_user_level(profile, global_user_id)
            
            profile.save()
            
        except GlobalUser.DoesNotExist:
            pass
    
    @staticmethod
    def _update_preferred_types(profile, resource):
        if not resource.resource_type:
            return
        
        if not profile.preferences_json:
            profile.preferences_json = {}
        
        resource_type = resource.resource_type
        current_count = profile.preferences_json.get(resource_type, 0)
        profile.preferences_json[resource_type] = current_count + 1
    
    @staticmethod
    def _update_interest_tags(profile, resource):
        if not resource.tags:
            return
        
        if profile.interest_tags:
            current_tags = [tag.strip() for tag in profile.interest_tags.split(',')]
        else:
            current_tags = []
        
        new_tags = [tag.strip() for tag in resource.tags.split(',')]
        all_tags = current_tags + new_tags
        
        tag_counter = Counter(all_tags)
        top_tags = [tag for tag, _ in tag_counter.most_common(20)]
        profile.interest_tags = ', '.join(top_tags)
    
    @staticmethod
    def _update_average_completion(profile, global_user_id):
        from lti_recommender_project.apps.interactions.models import UserInteraction
        
        avg_completion = UserInteraction.objects.filter(
            global_user_id=global_user_id,
            completion_percentage__isnull=False
        ).aggregate(avg=Avg('completion_percentage'))['avg']
        
        if avg_completion is not None:
            profile.average_completion = avg_completion
    
    @staticmethod
    def _update_average_rating(profile, global_user_id):
        from lti_recommender_project.apps.interactions.models import UserInteraction
        
        avg_rating = UserInteraction.objects.filter(
            global_user_id=global_user_id,
            rating__isnull=False
        ).aggregate(avg=Avg('rating'))['avg']
        
        if avg_rating is not None:
            profile.average_rating = avg_rating
    
    @staticmethod
    def _infer_user_level(profile, global_user_id):
        from lti_recommender_project.apps.interactions.models import UserInteraction
        
        interactions = UserInteraction.objects.filter(
            global_user_id=global_user_id,
            resource__difficulty_level__isnull=False
        ).select_related('resource')
        
        if not interactions.exists():
            return
            
        level_counter = Counter()
        high_completion_levels = Counter()
        
        for interaction in interactions:
            level = interaction.resource.difficulty_level
            level_counter[level] += 1
            if interaction.completion_percentage and interaction.completion_percentage >= 70:
                high_completion_levels[level] += 2
                
        for level, count in high_completion_levels.items():
            level_counter[level] += count
            
        total = sum(level_counter.values())
        if total < 5:
            if not profile.inferred_level:
                profile.inferred_level = 'beginner'
            return
            
        beginner_ratio = level_counter.get('beginner', 0) / total
        intermediate_ratio = level_counter.get('intermediate', 0) / total
        advanced_ratio = level_counter.get('advanced', 0) / total
        
        if advanced_ratio > 0.4 or (intermediate_ratio > 0.3 and advanced_ratio > 0.2):
            profile.inferred_level = 'advanced'
        elif intermediate_ratio > 0.4 or (beginner_ratio < 0.5 and intermediate_ratio > 0.2):
            profile.inferred_level = 'intermediate'
        else:
            profile.inferred_level = 'beginner'
    
    @staticmethod
    def infer_user_level(global_user_id) -> str:
        from lti_recommender_project.apps.users.models import GlobalUser
        try:
            profile = GlobalUser.objects.get(id=global_user_id)
            UserProfileService._infer_user_level(profile, global_user_id)
            profile.save()
            return profile.inferred_level
        except GlobalUser.DoesNotExist:
            return 'beginner'

    @staticmethod
    def generate_jwt_tokens_for_global_user(global_user_id: str, context_id: str = None) -> Dict[str, str]:
        """
        Generates SimpleJWT tokens for a GlobalUser using a proxy Django User.
        Injects the global_user_id and context_id into the token.
        """
        from rest_framework_simplejwt.tokens import RefreshToken
        
        # Get or create proxy user
        proxy_user, _ = User.objects.get_or_create(
            username=str(global_user_id),
            defaults={
                'is_active': True,
                'email': f"{global_user_id}@lti-proxy.local"
            }
        )
        
        refresh = RefreshToken.for_user(proxy_user)
        
        # Inject custom claims
        refresh['global_user_id'] = str(global_user_id)
        if context_id:
            refresh['context_id'] = context_id
            
        return {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }
    def extract_user_interests(global_user_id) -> str:
        from lti_recommender_project.apps.users.models import GlobalUser
        try:
            profile = GlobalUser.objects.get(id=global_user_id)
            return profile.interest_tags or ""
        except GlobalUser.DoesNotExist:
            return ""

def get_user_profile_service() -> UserProfileService:
    return UserProfileService()
