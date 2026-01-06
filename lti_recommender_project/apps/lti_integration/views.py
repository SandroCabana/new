# lti_recommender_project/apps/lti_integration/views.py

from django.shortcuts import render
from django.http import JsonResponse
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
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


@csrf_exempt
def lti_login(request):
    """
    Endpoint de inicio de sesión de OpenID Connect (OIDC).
    Moodle (la plataforma LTI) enviará una solicitud de autenticación aquí para iniciar el flujo.
    """
    try:
        launch_data_storage = DjangoCacheDataStorage(cache_name='default')
        oidc_login = DjangoOIDCLogin(request, tool_conf, launch_data_storage=launch_data_storage)
        oidc_login.enable_check_cookies()
        return oidc_login.redirect(settings.LTI_TOOL_CONFIG['LAUNCH_URL'])
    except Exception as e:
        logger.exception("Error during LTI login initiation:")
        return render(request, 'lti_integration/error.html', {'message': f'Error en el inicio de sesión LTI: {e}'})


@csrf_exempt
def lti_launch(request):
    """
    Endpoint de lanzamiento LTI.
    Moodle enviará una solicitud POST a esta URL con los datos del lanzamiento LTI.
    """
    if request.method != 'POST':
        return render(request, 'lti_integration/error.html', {'message': 'Acceso no permitido. Solo se aceptan solicitudes POST para el lanzamiento LTI.'})

    try:
        launch_data_storage = DjangoCacheDataStorage(cache_name='default')
        message_launch = DjangoMessageLaunch(request, tool_conf, launch_data_storage=launch_data_storage)
        message_launch.validate()
        launch_data = message_launch.get_launch_data()

        # Extracción de datos
        user_id = launch_data.get("sub", "N/A")
        context_claim = launch_data.get("https://purl.imsglobal.org/spec/lti/claim/context", {})
        context_id = context_claim.get("id", "N/A")
        course_title = context_claim.get("title", "N/A")
        roles = launch_data.get("https://purl.imsglobal.org/spec/lti/claim/roles") or launch_data.get("roles", [])
        user_name = launch_data.get("name", "N/A")
        user_email = launch_data.get("email", "N/A")
        resource_link_claim = launch_data.get("https://purl.imsglobal.org/spec/lti/claim/resource_link", {})
        activity_title = resource_link_claim.get("title", "N/A")
        tool_platform_claim = launch_data.get("https://purl.imsglobal.org/spec/lti/claim/tool_platform", {})
        platform_name = tool_platform_claim.get("name", "N/A")

        # Obtener recomendaciones
        recommendations = get_recommendations_from_api(user_id, context_id)

        context = {
            'user_id': user_id,
            'context_id': context_id,
            'roles': roles,
            'user_name': user_name,
            'user_email': user_email,
            'course_title': course_title,
            'activity_title': activity_title,
            'platform_name': platform_name,
            'recommendations': recommendations,
            'raw_lti_data': json.dumps(launch_data, indent=2, ensure_ascii=False),
        }

        return render(request, 'lti_integration/recommendations.html', context)

    except LtiException as e:
        logger.exception("LTI launch error (LtiException):")
        return render(request, 'lti_integration/error.html', {'message': f'Error en el lanzamiento LTI: {e}'})
    except Exception as e:
        logger.exception("Unexpected error during LTI launch:")
        return render(request, 'lti_integration/error.html', {'message': f'Error inesperado durante el lanzamiento LTI: {e}'})


def get_recommendations_from_api(user_id, context_id):
    """
    Función para obtener recomendaciones usando el motor de ML.
    """
    try:
        from lti_recommender_project.apps.recommendations.services.recommendation_engine import RecommendationEngine
        
        engine = RecommendationEngine()
        recommendations = engine.get_recommendations(
            user_id=user_id,
            context_id=context_id,
            limit=5,
            exclude_viewed=True
        )
        
        if not recommendations:
            logger.info(f"No recommendations generated for user {user_id} in context {context_id}")
            # Fallback a recursos del contexto
            resources_from_db = EducationalResource.objects.filter(
                lti_context_id=context_id
            ).order_by('?')[:5]
            
            if not resources_from_db.exists():
                resources_from_db = EducationalResource.objects.filter(
                    lti_context_id__isnull=True
                ).order_by('?')[:5]
            
            recommendations = [
                {
                    "title": resource.title,
                    "url": resource.url,
                    "description": resource.description or "",
                    "type": resource.resource_type,
                    "difficulty": resource.difficulty_level,
                    "score": 50  # Score neutro para fallback (50%)
                }
                for resource in resources_from_db
            ]
        
        return recommendations if recommendations else [
            {"title": "No hay recomendaciones disponibles. Agrega más recursos.", "url": "#"}
        ]
        
    except Exception as e:
        logger.error(f"Error al obtener recomendaciones: {e}")
        return [{"title": "Error al cargar recomendaciones.", "url": "#"}]


@csrf_exempt
def jwks(request):
    """
    Endpoint JWKS (JSON Web Key Set).
    Moodle usará esta URL para obtener las claves públicas de tu herramienta.
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
    """
    logger.info(f"API - Received interaction data: {request.data}")

    serializer = UserInteractionSerializer(data=request.data)
    if serializer.is_valid():
        try:
            serializer.save()
            logger.info("Interacción guardada exitosamente.")
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.error(f"Error al guardar interacción: {e}")
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    else:
        logger.error(f"Datos de interacción inválidos: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
