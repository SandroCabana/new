from rest_framework import serializers
from .models import UserInteraction


class UserInteractionSerializer(serializers.ModelSerializer):
    """
    Serializer para el modelo UserInteraction.
    Permite convertir instancias del modelo a JSON y viceversa.
    """
    class Meta:
        model = UserInteraction
        fields = ['id', 'lti_user_id', 'lti_context_id', 'resource', 'interaction_type', 'value', 'timestamp']
        read_only_fields = ['id', 'timestamp']
