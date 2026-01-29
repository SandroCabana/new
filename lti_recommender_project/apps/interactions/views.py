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

class TrackedDataBatchView(APIView):
    """
    Endpoint for receiving batch tracking data from external sources (e.g. Chrome Extension).
    """
    permission_classes = [IsAuthenticated] # Assuming DRF Token based auth as per plan

    def post(self, request):
        serializer = TrackedBatchSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        user_id = str(data['userID'])
        context_id = data['associatedPLE']
        tracked_data_list = data['trackedDataList']

        response_tracked_data_ids = []

        for tracked_item in tracked_data_list:
            # 1. Calculate time_spent
            start_time = tracked_item['startTime']
            end_time = tracked_item['endTime']
            time_spent = (end_time - start_time).total_seconds()
            
            # Ensure non-negative time_spent
            if time_spent < 0:
                time_spent = 0

            # 2. Get or Create Resource
            url = tracked_item['associatedURL']
            
            # Generate hash for resource_id if needed
            url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()
            
            resource, created = EducationalResource.objects.get_or_create(
                url=url,
                defaults={
                    'resource_id': url_hash,
                    'title': f"External Resource {url_hash[:8]}", # Default title
                    'description': "Imported from external tracking",
                    'resource_type': tracked_item['activityType'],
                    'lti_context_id': context_id # Associate with logic context? Or keep null? Keeping logic simpler.
                                                 # User said associatedPLE maps to lti_context_id, so maybe resource context?
                                                 # But resources are unique by URL. Let's assume global resources for now 
                                                 # or update if existing. For get_or_create, unique is on URL mostly?
                                                 # Model has unique_together ('resource_id', 'lti_context_id').
                                                 # If we use url to find, we might have issues if unique constraint is strict.
                                                 # Let's try to get by url first regardless of context.
                }
            )

            # Update tags/metadata if needed (simple append or replace logic could be complex, skipping for now or just setting if new)
            if created:
                tags = tracked_item.get('associatedKeywords', [])
                domains = tracked_item.get('associatedDomains', [])
                # Store domains in metadata or description?
                # User said: "associatedDomains and keywords to tags/metadata"
                resource.tags = ",".join(tags) if tags else ""
                # We don't have a metadata field on Resource similar to Interaction, keeping it simple.
                resource.save()
            
            # 3. Create UserInteraction
            feedback = tracked_item.get('feedback', {})
            rating = None
            comments = None
            if feedback:
                rating = feedback.get('score')
                comments = feedback.get('comments')
            
            # Prepare metadata
            interaction_metadata = {
                "domains": tracked_item.get('associatedDomains', []),
                "comments": comments
            }
            
            # Decide interaction types
            # Logic: If rating exists -> 'rated'. if time_spent > 0 -> 'viewed'.
            # We can create multiple interactions or one main one. 
            # Requirement says "Create UserInteraction", singular implies one per tracked item.
            # Let's verify standard interaction types.
            interaction_type = tracked_item['activityType'] # Use activity type as base? or 'external_view'?
            # User said: "Interaction: Create UserInteraction. rating = feedback.score."
            # and "activityType -> resource.resource_type".
            # Let's default to 'viewed' for the interaction type unless explicit. 
            # Actually, let's use 'viewed' as the primary interaction, and add rating to it.
            
            UserInteraction.objects.create(
                lti_user_id=user_id,
                lti_context_id=context_id,
                resource=resource,
                interaction_type='external_view', # Distinct from internal 'viewed'? Or just 'viewed'? 'viewed' is safer.
                value=time_spent, # Mapping value to time_spent generic field
                time_spent=time_spent,
                rating=rating, # Can be null
                metadata=interaction_metadata
            )

            # Generate a trackedDataID for response
            response_tracked_data_ids.append({
                "trackedDataID": str(uuid.uuid4()),
                "status": "processed"
            })

        response_payload = {
            "trackedBatchID": str(uuid.uuid4()),
            "trackedDataList": response_tracked_data_ids
        }

        return Response(response_payload, status=status.HTTP_201_CREATED)


class UserHistoryView(APIView):
    """
    GET /interactions/user-history/
    Returns paginated list of user's interactions with resource details.
    Query params: page, page_size, interaction_type, start_date, end_date
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Get user_id from authenticated user (via LTI)
        user_id = str(request.user.id)
        
        # Query params
        page = int(request.query_params.get('page', 1))
        page_size = min(int(request.query_params.get('page_size', 20)), 100)
        interaction_type = request.query_params.get('interaction_type')
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        # Build query
        interactions = UserInteraction.objects.filter(
            lti_user_id=user_id
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
        
        user_id = str(request.user.id)
        
        # Get aggregated stats
        interactions = UserInteraction.objects.filter(lti_user_id=user_id)
        
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
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        user_id = str(data['userID'])
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
            start_time = tracked_item['startTime']
            end_time = tracked_item['endTime']
            time_spent = max(0, (end_time - start_time).total_seconds())
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

