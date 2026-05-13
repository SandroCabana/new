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


class TrackedFeedbackSerializer(serializers.Serializer):
    score = serializers.FloatField(required=False, allow_null=True)
    comments = serializers.CharField(required=False, allow_null=True, allow_blank=True)


class TrackedDataSerializer(serializers.Serializer):
    activityType = serializers.CharField(required=False, default='viewed')
    associatedURL = serializers.CharField()
    resourceTitle = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    associatedDomains = serializers.ListField(
        child=serializers.CharField(),
        required=False, allow_empty=True, default=list
    )
    associatedKeywords = serializers.ListField(
        child=serializers.CharField(),
        required=False, allow_empty=True, default=list
    )
    startTime = serializers.CharField(required=False) # Accept various formats
    endTime = serializers.CharField(required=False)
    duration = serializers.FloatField(required=False, allow_null=True)
    activeTime = serializers.FloatField(required=False, allow_null=True)
    scrollDepth = serializers.FloatField(required=False, allow_null=True)
    contentSummary = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    videoData = serializers.JSONField(required=False, allow_null=True)
    feedback = TrackedFeedbackSerializer(required=False, allow_null=True)



class TrackedBatchSerializer(serializers.Serializer):
    userID = serializers.CharField(required=False, allow_null=True) # Optional, can be inferred from token
    associatedPLE = serializers.CharField()
    trackedDataList = serializers.ListField(
        child=TrackedDataSerializer(),
        allow_empty=False
    )


# =============================================
# Serializers for User History and Preview APIs
# =============================================

class ResourceSummarySerializer(serializers.Serializer):
    """Lightweight resource representation for history views."""
    id = serializers.IntegerField()
    title = serializers.CharField()
    url = serializers.CharField()
    resource_type = serializers.CharField()


class UserInteractionDetailSerializer(serializers.Serializer):
    """Detailed interaction for user history endpoint."""
    id = serializers.IntegerField()
    resource = ResourceSummarySerializer()
    interaction_type = serializers.CharField()
    time_spent = serializers.FloatField(allow_null=True)
    rating = serializers.IntegerField(allow_null=True)
    completion_percentage = serializers.FloatField(allow_null=True)
    timestamp = serializers.DateTimeField()
    metadata = serializers.JSONField(allow_null=True)


class UserStatsSerializer(serializers.Serializer):
    """Aggregated statistics for a user."""
    total_interactions = serializers.IntegerField()
    total_resources = serializers.IntegerField()
    total_time_spent = serializers.FloatField()
    average_rating = serializers.FloatField(allow_null=True)
    resource_type_breakdown = serializers.DictField(
        child=serializers.IntegerField()
    )
    most_visited_resources = ResourceSummarySerializer(many=True)
    first_interaction_date = serializers.DateTimeField(allow_null=True)
    last_interaction_date = serializers.DateTimeField(allow_null=True)


class PreviewResourceSerializer(serializers.Serializer):
    """Resource info that will be created/updated in preview."""
    url = serializers.CharField()
    title = serializers.CharField()
    is_new = serializers.BooleanField()
    resource_type = serializers.CharField()


class PreviewInteractionSerializer(serializers.Serializer):
    """Interaction that will be created in preview."""
    resource_url = serializers.CharField()
    interaction_type = serializers.CharField()
    time_spent = serializers.FloatField()
    rating = serializers.FloatField(allow_null=True)
    domains = serializers.ListField(child=serializers.CharField())
    keywords = serializers.ListField(child=serializers.CharField())


class PreviewResponseSerializer(serializers.Serializer):
    """Response for the preview endpoint showing what will be saved."""
    user_id = serializers.CharField()
    context_id = serializers.CharField()
    resources_to_create = PreviewResourceSerializer(many=True)
    resources_to_update = PreviewResourceSerializer(many=True)
    interactions_to_create = PreviewInteractionSerializer(many=True)
    summary = serializers.DictField()
