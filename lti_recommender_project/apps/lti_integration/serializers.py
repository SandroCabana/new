from rest_framework import serializers
from .models import UserInteraction, EducationalResource

class UserInteractionSerializer(serializers.ModelSerializer):
    # Campos que esperamos recibir en la API para una interacción
    resource_id = serializers.CharField(write_only=True) # ID del recurso, lo usaremos para buscar el objeto EducationalResource

    class Meta:
        model = UserInteraction
        # Campos que la API recibirá y/o devolverá
        fields = ['lti_user_id', 'lti_context_id', 'resource_id', 'interaction_type', 'value', 'timestamp']
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
        return user_interaction