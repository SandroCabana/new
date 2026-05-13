# lti_recommender_project/apps/lti_integration/views.py
"""
LTI 1.3 Views — v2
Integra StudentProfile, LTIClaimsExtractor, cache-aside y explainability.
"""

from django.shortcuts import render
from django.http import JsonResponse
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.core.cache import cache
import json
import logging
from django.conf import settings

# Importaciones de PyLTI1p3
from pylti1p3.contrib.django import DjangoMessageLaunch, DjangoOIDCLogin, DjangoDbToolConf
from pylti1p3.contrib.django import DjangoCacheDataStorage
from pylti1p3.exception import LtiException

# Importaciones para la API (Django REST Framework)
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

# Importar modelos desde las nuevas apps
from lti_recommender_project.apps.resources.models import EducationalResource
from lti_recommender_project.apps.interactions.serializers import UserInteractionSerializer

logger = logging.getLogger(__name__)

# Inicialización global de tool_conf usando DjangoDbToolConf
tool_conf = DjangoDbToolConf()

# Cache TTL for recommendations (seconds)
RECS_CACHE_TTL = getattr(settings, 'RECOMMENDATION_CONFIG', {}).get(
    'RECOMMENDATION_CACHE_TTL', 1800
)


@csrf_exempt
def lti_login(request):
    """
    Endpoint de inicio de sesión de OpenID Connect (OIDC).
    Moodle enviará una solicitud de autenticación aquí para iniciar el flujo.
    """
    try:
        launch_data_storage = DjangoCacheDataStorage(cache_name='default')
        oidc_login = DjangoOIDCLogin(request, tool_conf, launch_data_storage=launch_data_storage)
        # oidc_login.enable_check_cookies()  # Removed as it often causes issues in LMS environments
        return oidc_login.redirect(settings.LTI_TOOL_CONFIG['LAUNCH_URL'])
    except Exception as e:
        logger.exception("Error during LTI login initiation:")
        return render(
            request,
            'lti_integration/error.html',
            {'message': f'Error en el inicio de sesión LTI: {e}'}
        )


@csrf_exempt
def lti_launch(request):
    """
    Endpoint de lanzamiento LTI.
    Moodle enviará una solicitud POST con los datos del lanzamiento LTI.
    """
    if request.method != 'POST':
        return render(
            request,
            'lti_integration/error.html',
            {'message': 'Solo se aceptan solicitudes POST para el lanzamiento LTI.'}
        )

    try:
        launch_data_storage = DjangoCacheDataStorage(cache_name='default')
        message_launch = DjangoMessageLaunch(request, tool_conf, launch_data_storage=launch_data_storage)
        message_launch.validate()
        launch_data = message_launch.get_launch_data()

        # --- Extract all LTI claims ---
        from lti_recommender_project.apps.lti_integration.lti_claims_extractor import LTIClaimsExtractor
        claims = LTIClaimsExtractor.extract_all(launch_data)

        user_id = claims['user_id']
        context_id = claims['context_id']

        # --- Sync LTIContext ---
        from lti_recommender_project.apps.lti_integration.models import LTIContext
        lti_context, _ = LTIContext.objects.update_or_create(
            context_id=context_id,
            defaults={'title': claims['context_title']}
        )

        # --- Build enriched StudentProfile ---
        from lti_recommender_project.apps.users.student_profile import StudentProfile
        profile = StudentProfile.from_lti_launch(launch_data)

        # --- Link Context to LTIIdentity ---
        from lti_recommender_project.apps.users.services.user_profile_service import UserProfileService
        
        launch_info = {
            'email': claims.get('email', ''),
            'name': claims.get('name', ''),
            'role': claims['roles'][0] if claims.get('roles') else 'Learner'
        }
        
        global_user = UserProfileService.get_or_create_profile(
            sub=user_id,
            issuer=claims.get('issuer', 'unknown_issuer'),
            launch_data=launch_info
        )
        
        # Link context
        from lti_recommender_project.apps.users.models import LTIIdentity
        identity = LTIIdentity.objects.filter(sub=user_id, issuer=claims.get('issuer', 'unknown_issuer')).first()
        if identity:
            identity.contexts.add(lti_context)
            # Update role and platform if not set
            if not identity.platform_id and claims.get('platform_guid'):
                identity.platform_id = claims['platform_guid']
                identity.save(update_fields=['platform_id'])


        # --- Get recommendations (cache-aside) ---
        recommendations = get_recommendations_cached(user_id, context_id, profile)

        # --- Enrich with explanations ---
        from lti_recommender_project.apps.recommendations.explainability import RecommendationExplainer
        recommendations = RecommendationExplainer.enrich_recommendations(
            recommendations,
            profile,
            is_instructor=claims['is_instructor'],
        )

        # --- Tokens for Extension Pairing ---
        jwt_tokens = UserProfileService.generate_jwt_tokens_for_global_user(
            global_user_id=global_user.id,
            context_id=context_id
        )

        context = {
            # Identity
            'user_id': user_id,
            'global_user_id': str(global_user.id),
            'user_name': claims['name'],
            'user_email': claims['email'],
            # Context
            'context_id': context_id,
            'course_title': claims['context_title'],
            'activity_title': claims['resource_link_title'],
            # Platform
            'platform_name': claims['platform_name'],
            # Roles
            'roles': claims['roles'],
            'is_instructor': claims['is_instructor'],
            # Recommendations
            'recommendations': recommendations,
            'profile': profile,
            # Tokens
            'extension_tokens': jwt_tokens,
            # A/B test variant
            'ab_variant': _get_ab_variant(str(global_user.id)),
            # Debug (solo en DEBUG=True)
            'raw_lti_data': json.dumps(launch_data, indent=2, ensure_ascii=False) if settings.DEBUG else None,
        }

        return render(request, 'lti_integration/recommendations.html', context)

    except LtiException as e:
        logger.exception("LTI launch error (LtiException):")
        return render(
            request,
            'lti_integration/error.html',
            {'message': f'Error en el lanzamiento LTI: {e}'}
        )
    except Exception as e:
        logger.exception("Unexpected error during LTI launch:")
        return render(
            request,
            'lti_integration/error.html',
            {'message': f'Error inesperado: {e}'}
        )


def get_recommendations_cached(user_id: str, context_id: str, profile=None):
    """
    Cache-aside pattern para recomendaciones.
    
    Cache HIT → devuelve inmediatamente (~1ms)
    Cache MISS → calcula y guarda en Redis
    
    La cache se invalida automáticamente cuando el usuario registra
    una nueva interacción (via Django signal en interactions/models.py).
    """
    cache_key = f"recs:v2:{user_id}:{context_id}"
    cached = cache.get(cache_key)

    if cached is not None:
        logger.debug(f"Cache HIT for user={user_id[:8]}...")
        return cached

    logger.info(f"Cache MISS for user={user_id[:8]}... — computing recommendations")

    try:
        recommendations = get_recommendations_from_api(user_id, context_id, profile)
        # TTL adaptativo: usuarios con recs → 30min, sin recs → 5min
        ttl = RECS_CACHE_TTL if recommendations else 300
        cache.set(cache_key, recommendations, timeout=ttl)
        return recommendations
    except Exception as e:
        logger.error(f"Error computing recommendations for {user_id}: {e}")
        return _get_fallback_recommendations(context_id)


def invalidate_user_cache(user_id: str, context_id: str):
    """
    Invalida la cache de recomendaciones de un usuario.
    Llamado desde el signal post_save de UserInteraction.
    """
    cache_key = f"recs:v2:{user_id}:{context_id}"
    cache.delete(cache_key)
    logger.debug(f"Cache invalidated for user={user_id[:8]}...")


def get_recommendations_from_api(user_id: str, context_id: str, profile=None):
    """
    Obtiene recomendaciones usando el ensemble de modelos ML.
    Recibe un StudentProfile ya construido para evitar reconstrucción.
    """
    try:
        from lti_recommender_project.ml.models.ensemble import get_ensemble_recommender

        # A/B test: variant determines ensemble strategy
        variant = _get_ab_variant(user_id)
        strategy = 'rank_fusion' if variant == 'B' else 'weighted_average'

        engine = get_ensemble_recommender(strategy=strategy)
        recommendations = engine.get_recommendations(
            user_id=user_id,
            context_id=context_id,
            limit=10,
            exclude_viewed=True,
        )

        model_info = engine.get_model_info()
        logger.info(
            f"Ensemble recs for {user_id[:8]}...: "
            f"{len(recommendations)} recs from {model_info['n_models']} models "
            f"[variant={variant}, strategy={strategy}]"
        )

        if not recommendations:
            logger.info(f"No ML recs for {user_id} — using fallback")
            return _get_fallback_recommendations(context_id)

        return recommendations

    except Exception as e:
        logger.error(f"Error en ML recommendations: {e}", exc_info=True)
        return _get_fallback_recommendations(context_id)


def _get_fallback_recommendations(context_id: str, limit: int = 5):
    """Recomendaciones de respaldo cuando falla el engine."""
    from django.db.models import Q
    resources = EducationalResource.objects.filter(
        Q(lti_context_id=context_id) | Q(lti_context_id__isnull=True)
    ).order_by('-created_at')[:limit]

    return [
        {
            'id': r.id,
            'title': r.title,
            'url': r.url,
            'description': r.description or '',
            'type': r.resource_type,
            'difficulty': r.difficulty_level,
            'score': 0.5,
            'source': 'fallback',
        }
        for r in resources
    ] or [{'title': 'No hay recomendaciones disponibles. Agrega más recursos.', 'url': '#'}]


def _get_ab_variant(user_id: str) -> str:
    """
    A/B test: asignación determinística por hash del user_id.
    Mismo usuario → misma variante siempre.
    Variante A: weighted_average (control)
    Variante B: rank_fusion (tratamiento)
    """
    import hashlib
    hash_val = int(hashlib.md5(user_id.encode()).hexdigest(), 16)
    return 'B' if hash_val % 2 == 0 else 'A'


@csrf_exempt
def jwks(request):
    """
    Endpoint JWKS — Moodle usa esta URL para obtener las claves públicas.
    """
    try:
        jwks_dict = tool_conf.get_jwks()
        return JsonResponse(jwks_dict, safe=False)
    except Exception as e:
        logger.exception("Error generating JWKS:")
        return JsonResponse({'error': f'Error al generar JWKS: {str(e)}'}, status=500)


@csrf_exempt
@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def record_interaction(request):
    """
    Endpoint API para registrar interacciones de usuarios con recursos educativos.
    Invalida automáticamente la cache de recomendaciones del usuario.
    """
    logger.info(f"API - Received interaction data: {request.data}")

    serializer = UserInteractionSerializer(data=request.data)
    if serializer.is_valid():
        try:
            interaction = serializer.save()
            # Invalidate recommendation cache for this user
            invalidate_user_cache(
                interaction.lti_user_id,
                interaction.lti_context_id,
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.error(f"Error al guardar interacción: {e}")
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    else:
        logger.error(f"Datos de interacción inválidos: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
