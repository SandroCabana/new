from rest_framework import serializers
from .models import UserInteraction


class UserInteractionSerializer(serializers.ModelSerializer):
    """
    Serializer para el modelo UserInteraction.
    Permite convertir instancias del modelo a JSON y viceversa.
    """
    def create(self, validated_data):
        """
        Sobrescribimos create para mapear el campo genérico 'value' 
        a campos específicos del modelo según el tipo de interacción.
        """
        interaction_type = validated_data.get('interaction_type')
        value = validated_data.get('value')

        if value is not None:
            if interaction_type == 'rated':
                validated_data['rating'] = int(value)
            elif interaction_type in ['viewed', 'time_spent']:
                # Asumimos que si envían value con viewed es tiempo gastado
                validated_data['time_spent'] = float(value)
            elif interaction_type == 'completed':
                 validated_data['completion_percentage'] = float(value)

        return super().create(validated_data)

    class Meta:
        model = UserInteraction
        fields = ['id', 'lti_user_id', 'lti_context_id', 'resource', 'interaction_type', 'value', 'timestamp']
        read_only_fields = ['id', 'timestamp']
