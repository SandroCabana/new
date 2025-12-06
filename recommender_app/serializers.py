from rest_framework import serializers
from .models import UserInteraction, EducationalResource

class UserInteractionSerializer(serializers.ModelSerializer):
    # Campos que esperamos recibir en la API para una interacción
    resource_id = serializers.CharField(write_only=True) # ID del recurso, lo usaremos para buscar el objeto EducationalResource

    class Meta:
        model = UserInteraction
        # Campos que la API recibirá y/o devolverá (incluye nuevos campos de tracking)
        fields = [
            'lti_user_id', 'lti_context_id', 'resource_id', 'interaction_type', 'value', 
            'time_spent', 'completion_percentage', 'rating', 'scroll_depth',
            'downloaded', 'shared', 'metadata', 'timestamp'
        ]
        # timestamp es auto_now_add, por lo que no es necesario enviarlo en la creación
        read_only_fields = ['timestamp']

    def create(self, validated_data):
        # Lógica personalizada para manejar el 'resource_id' y obtener el objeto 'resource'
        resource_id_from_data = validated_data.pop('resource_id')
        
        try:
            # Intenta encontrar el recurso educativo por su resource_id y lti_context_id
            # Es importante que el resource_id sea único dentro de un lti_context_id
            resource = EducationalResource.objects.get(
                resource_id=resource_id_from_data, 
                lti_context_id=validated_data.get('lti_context_id') # Asocia el recurso al contexto LTI
            )
        except EducationalResource.DoesNotExist:
            # Si el recurso no existe, puedes elegir cómo manejarlo:
            # 1. Crear el recurso automáticamente (si los metadatos son mínimos o se pueden inferir)
            # 2. Lanzar un error para indicar que el recurso debe existir previamente
            # Por ahora, lanzamos un error para depuración.
            raise serializers.ValidationError(
                f"El recurso con ID '{resource_id_from_data}' no existe para el contexto '{validated_data.get('lti_context_id')}'."
            )

        # Crea la interacción de usuario con el objeto EducationalResource
        user_interaction = UserInteraction.objects.create(resource=resource, **validated_data)
        
        # Actualizar perfil de usuario automáticamente
        try:
            from lti_recommender_project.apps.users.services.user_profile_service import UserProfileService
            UserProfileService.update_profile_from_interaction(
                validated_data.get('lti_user_id'),
                user_interaction
            )
        except Exception as e:
            # No fallar si la actualización del perfil falla, solo loguear
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"No se pudo actualizar el perfil de usuario: {e}")
        
        return user_interaction