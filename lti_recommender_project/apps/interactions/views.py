from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
import hashlib
import uuid
import datetime
from django.utils import timezone
from .serializers import TrackedBatchSerializer
from lti_recommender_project.apps.resources.models import EducationalResource
from lti_recommender_project.apps.interactions.models import UserInteraction
import logging

logger = logging.getLogger(__name__)

class TrackedDataBatchView(APIView):
    """
    Endpoint for receiving batch tracking data from external sources (e.g. Chrome Extension).
    """
    permission_classes = [IsAuthenticated] # Assuming DRF Token based auth as per plan

    def post(self, request):
        serializer = TrackedBatchSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning(f"Batch Serializer Errors: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        
        # 1. Resolve User ID (Priority: Payload > JWT > Email)
        user_id = data.get('userID')
        if not user_id:
            jwt_payload = getattr(request.auth, 'payload', {}) if request.auth else {}
            user_id = jwt_payload.get('global_user_id')
        
        if not user_id:
            from lti_recommender_project.apps.users.models import GlobalUser
            g_user = GlobalUser.objects.filter(email__iexact=request.user.email).first()
            user_id = str(g_user.id) if g_user else None
            
        if not user_id:
            return Response({"error": "No se pudo identificar al usuario global."}, status=status.HTTP_400_BAD_REQUEST)

        context_id = data['associatedPLE']
        tracked_data_list = data['trackedDataList']

        # Enqueue processing task
        try:
            from .tasks import process_tracking_batch
            # In simplejwt, request.user.username is global_user.id or we can get global_user_id from the token
            # Actually, user_id from the payload is supposed to be global_user_id
            process_tracking_batch.delay(
                global_user_id=user_id,
                context_id=context_id,
                items=tracked_data_list
            )
            
            response_payload = {
                "trackedBatchID": str(uuid.uuid4()),
                "status": "enqueued",
                "message": "Los datos han sido encolados para su procesamiento asíncrono."
            }
            return Response(response_payload, status=status.HTTP_202_ACCEPTED)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UserHistoryView(APIView):
    """
    GET /interactions/user-history/
    Returns paginated list of user's interactions with resource details.
    Query params: page, page_size, interaction_type, start_date, end_date
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from lti_recommender_project.apps.users.models import GlobalUser
        
        # 1. Resolve GlobalUser (Support JWT and Token)
        global_user = None
        jwt_payload = getattr(request.auth, 'payload', {}) if request.auth else {}
        global_user_id = jwt_payload.get('global_user_id')

        if global_user_id:
            global_user = GlobalUser.objects.filter(id=global_user_id).first()
        
        if not global_user:
            global_user = GlobalUser.objects.filter(email__iexact=request.user.email).first()

        if not global_user:
            return Response({'results': [], 'total': 0, 'message': 'No se encontró perfil global para este usuario.'})

        # Query params
        page = int(request.query_params.get('page', 1))
        page_size = min(int(request.query_params.get('page_size', 20)), 100)
        interaction_type = request.query_params.get('interaction_type')
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        # Build query - Filter by global_user object
        interactions = UserInteraction.objects.filter(
            global_user=global_user
        ).select_related('resource').order_by('-timestamp')
        
        # Apply filters
        if interaction_type:
            interactions = interactions.filter(interaction_type=interaction_type)
        if start_date:
            interactions = interactions.filter(timestamp__gte=start_date)
        if end_date:
            interactions = interactions.filter(timestamp__lte=end_date)
        
        # Pagination
        total = interactions.count()
        offset = (page - 1) * page_size
        interactions = interactions[offset:offset + page_size]
        
        # Serialize
        data = []
        for interaction in interactions:
            data.append({
                'id': interaction.id,
                'resource': {
                    'id': interaction.resource.id,
                    'title': interaction.resource.title,
                    'url': interaction.resource.url,
                    'resource_type': interaction.resource.resource_type,
                },
                'interaction_type': interaction.interaction_type,
                'time_spent': interaction.time_spent,
                'rating': interaction.rating,
                'completion_percentage': interaction.completion_percentage,
                'timestamp': interaction.timestamp.isoformat(),
                'metadata': interaction.metadata,
            })
        
        return Response({
            'page': page,
            'page_size': page_size,
            'total': total,
            'total_pages': (total + page_size - 1) // page_size,
            'results': data
        })


class UserStatsView(APIView):
    """
    GET /interactions/user-stats/
    Returns aggregated statistics for the user.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from django.db.models import Sum, Avg, Count, Min, Max
        from lti_recommender_project.apps.users.models import GlobalUser
        
        # Resolve GlobalUser
        global_user = None
        jwt_payload = getattr(request.auth, 'payload', {}) if request.auth else {}
        global_user_id = jwt_payload.get('global_user_id')

        if global_user_id:
            global_user = GlobalUser.objects.filter(id=global_user_id).first()
        
        if not global_user:
            global_user = GlobalUser.objects.filter(email__iexact=request.user.email).first()

        if not global_user:
            return Response({'total_interactions': 0, 'total_resources': 0, 'message': 'Sin datos.'})

        # Get aggregated stats - Filter by global_user
        interactions = UserInteraction.objects.filter(global_user=global_user)
        
        stats = interactions.aggregate(
            total_interactions=Count('id'),
            total_time_spent=Sum('time_spent'),
            average_rating=Avg('rating'),
            first_interaction_date=Min('timestamp'),
            last_interaction_date=Max('timestamp'),
        )
        
        # Resource type breakdown
        resource_types = interactions.values(
            'resource__resource_type'
        ).annotate(
            count=Count('id')
        )
        resource_type_breakdown = {
            item['resource__resource_type']: item['count']
            for item in resource_types if item['resource__resource_type']
        }
        
        # Count unique resources
        total_resources = interactions.values('resource').distinct().count()
        
        # Most visited resources
        most_visited = interactions.values(
            'resource__id', 'resource__title', 'resource__url', 'resource__resource_type'
        ).annotate(
            visit_count=Count('id')
        ).order_by('-visit_count')[:5]
        
        most_visited_resources = [
            {
                'id': item['resource__id'],
                'title': item['resource__title'],
                'url': item['resource__url'],
                'resource_type': item['resource__resource_type'],
            }
            for item in most_visited
        ]
        
        return Response({
            'total_interactions': stats['total_interactions'] or 0,
            'total_resources': total_resources,
            'total_time_spent': stats['total_time_spent'] or 0.0,
            'average_rating': stats['average_rating'],
            'resource_type_breakdown': resource_type_breakdown,
            'most_visited_resources': most_visited_resources,
            'first_interaction_date': stats['first_interaction_date'],
            'last_interaction_date': stats['last_interaction_date'],
        })


class DataPreviewView(APIView):
    """
    POST /interactions/preview/
    Preview what data will be saved WITHOUT actually saving.
    This allows the user to review before confirming the batch send.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from .serializers import TrackedBatchSerializer
        import hashlib
        
        serializer = TrackedBatchSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning(f"Preview Serializer Errors: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        
        # 1. Resolve User ID (Priority: Payload > JWT > Email)
        user_id = data.get('userID')
        if not user_id:
            jwt_payload = getattr(request.auth, 'payload', {}) if request.auth else {}
            user_id = jwt_payload.get('global_user_id')
        
        if not user_id:
            from lti_recommender_project.apps.users.models import GlobalUser
            g_user = GlobalUser.objects.filter(email__iexact=request.user.email).first()
            user_id = str(g_user.id) if g_user else None

        if not user_id:
            return Response({"error": "No se pudo identificar al usuario global."}, status=status.HTTP_400_BAD_REQUEST)

        context_id = data['associatedPLE']
        tracked_data_list = data['trackedDataList']
        
        resources_to_create = []
        resources_to_update = []
        interactions_to_create = []
        total_time = 0
        
        for tracked_item in tracked_data_list:
            url = tracked_item['associatedURL']
            url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()
            
            # Calculate time spent
            from django.utils.dateparse import parse_datetime
            from datetime import datetime
            
            s_time = tracked_item.get('startTime')
            e_time = tracked_item.get('endTime')
            
            # Parse if string, otherwise use as is
            dt_start = parse_datetime(s_time) if isinstance(s_time, str) else s_time
            dt_end = parse_datetime(e_time) if isinstance(e_time, str) else e_time
            
            # Fallback to now if parsing fails
            dt_start = dt_start or datetime.now()
            dt_end = dt_end or datetime.now()

            time_spent = max(0, (dt_end - dt_start).total_seconds())
            total_time += time_spent
            
            # Check if resource exists
            existing_resource = EducationalResource.objects.filter(url=url).first()
            
            resource_info = {
                'url': url,
                'title': existing_resource.title if existing_resource else f"External Resource {url_hash[:8]}",
                'is_new': existing_resource is None,
                'resource_type': tracked_item['activityType'],
            }
            
            if existing_resource:
                resources_to_update.append(resource_info)
            else:
                resources_to_create.append(resource_info)
            
            # Get feedback info
            feedback = tracked_item.get('feedback', {}) or {}
            rating = feedback.get('score')
            
            interactions_to_create.append({
                'resource_url': url,
                'interaction_type': 'external_view',
                'time_spent': time_spent,
                'rating': rating,
                'domains': tracked_item.get('associatedDomains', []),
                'keywords': tracked_item.get('associatedKeywords', []),
            })
        
        return Response({
            'user_id': user_id,
            'context_id': context_id,
            'resources_to_create': resources_to_create,
            'resources_to_update': resources_to_update,
            'interactions_to_create': interactions_to_create,
            'summary': {
                'total_items': len(tracked_data_list),
                'new_resources': len(resources_to_create),
                'existing_resources': len(resources_to_update),
                'total_time_seconds': total_time,
                'total_time_formatted': f"{int(total_time // 60)}m {int(total_time % 60)}s",
            }
        })

