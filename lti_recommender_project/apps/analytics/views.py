"""
Analytics views for the LTI Recommender System.
Provides metrics and statistics about system usage, model performance, and user engagement.
"""
from django.db.models import Count, Avg, Sum, F, Q
from django.db.models.functions import TruncDate, TruncHour
from django.utils import timezone
from datetime import timedelta
import logging

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from rest_framework.response import Response

from lti_recommender_project.apps.resources.models import EducationalResource
from lti_recommender_project.apps.interactions.models import UserInteraction
from lti_recommender_project.apps.users.models import UserProfile

logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([AllowAny])
def dashboard_overview(request):
    """
    GET /analytics/dashboard/
    Returns overview metrics for the analytics dashboard.
    """
    try:
        # Time ranges
        now = timezone.now()
        last_24h = now - timedelta(hours=24)
        last_7d = now - timedelta(days=7)
        last_30d = now - timedelta(days=30)
        
        # Basic counts
        total_resources = EducationalResource.objects.count()
        total_interactions = UserInteraction.objects.count()
        total_users = UserProfile.objects.count()
        
        # Recent activity
        interactions_24h = UserInteraction.objects.filter(timestamp__gte=last_24h).count()
        interactions_7d = UserInteraction.objects.filter(timestamp__gte=last_7d).count()
        
        # Unique active users
        active_users_24h = UserInteraction.objects.filter(
            timestamp__gte=last_24h
        ).values('lti_user_id').distinct().count()
        
        active_users_7d = UserInteraction.objects.filter(
            timestamp__gte=last_7d
        ).values('lti_user_id').distinct().count()
        
        # Average engagement metrics
        avg_rating = UserInteraction.objects.filter(
            rating__isnull=False
        ).aggregate(avg=Avg('rating'))['avg'] or 0
        
        avg_completion = UserInteraction.objects.filter(
            completion_percentage__isnull=False
        ).aggregate(avg=Avg('completion_percentage'))['avg'] or 0
        
        avg_time_spent = UserInteraction.objects.filter(
            time_spent__isnull=False
        ).aggregate(avg=Avg('time_spent'))['avg'] or 0
        
        # Top resource types
        resource_type_stats = list(
            EducationalResource.objects.values('resource_type').annotate(
                count=Count('id')
            ).order_by('-count')[:5]
        )
        
        return Response({
            'overview': {
                'total_resources': total_resources,
                'total_interactions': total_interactions,
                'total_users': total_users,
            },
            'activity': {
                'interactions_24h': interactions_24h,
                'interactions_7d': interactions_7d,
                'active_users_24h': active_users_24h,
                'active_users_7d': active_users_7d,
            },
            'engagement': {
                'avg_rating': round(avg_rating, 2),
                'avg_completion_percentage': round(avg_completion, 1),
                'avg_time_spent_seconds': round(avg_time_spent, 1),
            },
            'resource_types': resource_type_stats,
            'generated_at': now.isoformat(),
        })
    except Exception as e:
        logger.error(f"Error in dashboard_overview: {e}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def interaction_trends(request):
    """
    GET /analytics/trends/
    Returns interaction trends over time.
    
    Query params:
    - period: 'hourly', 'daily', 'weekly' (default: 'daily')
    - days: number of days to look back (default: 30)
    """
    try:
        period = request.query_params.get('period', 'daily')
        days = int(request.query_params.get('days', 30))
        
        start_date = timezone.now() - timedelta(days=days)
        
        if period == 'hourly':
            truncator = TruncHour('timestamp')
            limit = min(days * 24, 168)  # Max 7 days of hourly data
        else:
            truncator = TruncDate('timestamp')
            limit = days
        
        trends = list(
            UserInteraction.objects.filter(
                timestamp__gte=start_date
            ).annotate(
                period=truncator
            ).values('period').annotate(
                interaction_count=Count('id'),
                unique_users=Count('lti_user_id', distinct=True),
                avg_rating=Avg('rating'),
                avg_completion=Avg('completion_percentage'),
            ).order_by('period')[:limit]
        )
        
        # Convert datetime to string for JSON
        for item in trends:
            if item.get('period'):
                item['period'] = item['period'].isoformat()
        
        return Response({
            'period': period,
            'days': days,
            'data_points': len(trends),
            'trends': trends,
        })
    except Exception as e:
        logger.error(f"Error in interaction_trends: {e}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def resource_analytics(request):
    """
    GET /analytics/resources/
    Returns analytics for educational resources.
    
    Query params:
    - limit: number of resources to return (default: 20)
    - order_by: 'views', 'rating', 'completion' (default: 'views')
    """
    try:
        limit = int(request.query_params.get('limit', 20))
        order_by = request.query_params.get('order_by', 'views')
        
        # Build query
        resources = EducationalResource.objects.annotate(
            view_count=Count('interactions'),
            avg_rating=Avg('interactions__rating'),
            avg_completion=Avg('interactions__completion_percentage'),
            total_time_spent=Sum('interactions__time_spent'),
            unique_users=Count('interactions__lti_user_id', distinct=True),
        )
        
        # Order by specified metric
        order_field = {
            'views': '-view_count',
            'rating': '-avg_rating',
            'completion': '-avg_completion',
            'time': '-total_time_spent',
        }.get(order_by, '-view_count')
        
        resources = resources.order_by(order_field)[:limit]
        
        resource_data = []
        for resource in resources:
            resource_data.append({
                'id': resource.id,
                'title': resource.title,
                'resource_type': resource.resource_type,
                'difficulty_level': resource.difficulty_level,
                'view_count': resource.view_count or 0,
                'avg_rating': round(resource.avg_rating, 2) if resource.avg_rating else None,
                'avg_completion': round(resource.avg_completion, 1) if resource.avg_completion else None,
                'total_time_spent': round(resource.total_time_spent or 0, 1),
                'unique_users': resource.unique_users or 0,
            })
        
        return Response({
            'order_by': order_by,
            'limit': limit,
            'resources': resource_data,
        })
    except Exception as e:
        logger.error(f"Error in resource_analytics: {e}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def user_engagement(request):
    """
    GET /analytics/engagement/
    Returns user engagement metrics.
    """
    try:
        # User engagement distribution
        engagement_stats = UserProfile.objects.annotate(
            interaction_count=Count('lti_user_id', filter=Q(
                lti_user_id__in=UserInteraction.objects.values('lti_user_id')
            ))
        ).aggregate(
            total_users=Count('id'),
            users_with_interactions=Count('id', filter=Q(interaction_count__gt=0)),
        )
        
        # Engagement by level
        level_stats = list(
            UserProfile.objects.values('inferred_level').annotate(
                count=Count('id')
            ).order_by('-count')
        )
        
        # Top engaged users (anonymized)
        top_users = list(
            UserInteraction.objects.values('lti_user_id').annotate(
                interaction_count=Count('id'),
                avg_rating=Avg('rating'),
                total_time=Sum('time_spent'),
            ).order_by('-interaction_count')[:10]
        )
        
        # Anonymize user IDs
        for i, user in enumerate(top_users):
            user['rank'] = i + 1
            user['user_label'] = f"User #{i + 1}"
            del user['lti_user_id']
        
        return Response({
            'summary': engagement_stats,
            'by_level': level_stats,
            'top_engaged_users': top_users,
        })
    except Exception as e:
        logger.error(f"Error in user_engagement: {e}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def model_performance(request):
    """
    GET /analytics/models/
    Returns ML model availability and basic info.
    """
    try:
        from lti_recommender_project.ml.models.ensemble import get_ensemble_recommender
        
        ensemble = get_ensemble_recommender()
        model_info = ensemble.get_model_info()
        
        # Check individual model status
        model_status = {}
        
        try:
            from lti_recommender_project.ml.models.matrix_factorization import get_svd_model
            svd = get_svd_model()
            model_status['svd'] = {
                'loaded': svd._is_fitted,
                'type': 'Matrix Factorization (SVD)',
            }
        except Exception:
            model_status['svd'] = {'loaded': False, 'type': 'Matrix Factorization (SVD)'}
        
        try:
            from lti_recommender_project.ml.models.neural_cf import get_ncf_model
            ncf = get_ncf_model()
            model_status['ncf'] = {
                'loaded': ncf._is_fitted,
                'type': 'Neural Collaborative Filtering',
            }
        except Exception:
            model_status['ncf'] = {'loaded': False, 'type': 'Neural Collaborative Filtering'}
        
        try:
            from lti_recommender_project.ml.models.sequential_rec import get_sequential_model
            seq = get_sequential_model()
            model_status['sequential'] = {
                'loaded': seq._is_fitted,
                'type': 'Sequential (GRU4Rec)',
            }
        except Exception:
            model_status['sequential'] = {'loaded': False, 'type': 'Sequential (GRU4Rec)'}
        
        try:
            from lti_recommender_project.ml.models.factorization_machine import get_fm_model
            fm = get_fm_model()
            model_status['fm'] = {
                'loaded': fm._is_fitted,
                'type': 'Factorization Machine',
            }
        except Exception:
            model_status['fm'] = {'loaded': False, 'type': 'Factorization Machine'}
        
        return Response({
            'ensemble': {
                'n_models': model_info['n_models'],
                'strategy': model_info['strategy'],
                'models': model_info['models'],
                'weights': model_info['weights'],
            },
            'individual_models': model_status,
        })
    except Exception as e:
        logger.error(f"Error in model_performance: {e}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def context_analytics(request, context_id=None):
    """
    GET /analytics/context/<context_id>/
    Returns analytics for a specific course/context.
    """
    try:
        if not context_id:
            context_id = request.query_params.get('context_id')
        
        if not context_id:
            # Return list of contexts
            contexts = list(
                UserInteraction.objects.values('lti_context_id').annotate(
                    interaction_count=Count('id'),
                    unique_users=Count('lti_user_id', distinct=True),
                    unique_resources=Count('resource_id', distinct=True),
                ).order_by('-interaction_count')[:20]
            )
            return Response({'contexts': contexts})
        
        # Specific context analytics
        interactions = UserInteraction.objects.filter(lti_context_id=context_id)
        
        stats = interactions.aggregate(
            total_interactions=Count('id'),
            unique_users=Count('lti_user_id', distinct=True),
            unique_resources=Count('resource_id', distinct=True),
            avg_rating=Avg('rating'),
            avg_completion=Avg('completion_percentage'),
            total_time=Sum('time_spent'),
        )
        
        # Top resources in context
        top_resources = list(
            interactions.values(
                'resource__id', 'resource__title', 'resource__resource_type'
            ).annotate(
                view_count=Count('id'),
                avg_rating=Avg('rating'),
            ).order_by('-view_count')[:10]
        )
        
        return Response({
            'context_id': context_id,
            'stats': stats,
            'top_resources': top_resources,
        })
    except Exception as e:
        logger.error(f"Error in context_analytics: {e}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
