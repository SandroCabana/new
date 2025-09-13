# lti_recommender_project/recommender_app/views.py

from django.shortcuts import render, redirect
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
import json
import logging
from django.conf import settings
from .models import EducationalResource

# Importaciones de PyLTI1p3
from pylti1p3.contrib.django import DjangoMessageLaunch, DjangoOIDCLogin, DjangoDbToolConf
from pylti1p3.contrib.django import DjangoCacheDataStorage
from pylti1p3.exception import LtiException # Importa LtiException para un manejo de errores más específico
# Importaciones para la API (Django REST Framework)
from rest_framework import status 
from rest_framework.decorators import api_view
from rest_framework.response import Response 
from .serializers import UserInteractionSerializer 
logger = logging.getLogger(__name__)

# Inicialización global de tool_conf usando DjangoDbToolConf
# Esta instancia se encarga de cargar la configuración de la herramienta desde la base de datos de Django.
tool_conf = DjangoDbToolConf()

@csrf_exempt
def lti_login(request):
    """
    Endpoint de inicio de sesión de OpenID Connect (OIDC).
    Moodle (la plataforma LTI) enviará una solicitud de autenticación aquí para iniciar el flujo.
    """
    try:
        # Inicializa el almacenamiento de datos de lanzamiento usando el caché de Django.
        # Esto es crucial para persistir el estado de la sesión entre las redirecciones LTI.
        launch_data_storage = DjangoCacheDataStorage(cache_name='default')

        # Crea una instancia de DjangoOIDCLogin para manejar el flujo OIDC.
        oidc_login = DjangoOIDCLogin(request, tool_conf, launch_data_storage=launch_data_storage)

        # Habilita la comprobación de cookies. Esto es vital para entornos con iframes
        # y políticas de privacidad de cookies de terceros (SameSite=None, Secure).
        # Si el navegador bloquea las cookies, mostrará una página intermedia para el usuario.
        oidc_login.enable_check_cookies()

        # Redirige el navegador de vuelta a la URL de lanzamiento de la herramienta en Moodle.
        # La librería maneja la validación y la construcción de la URL de redirección.
        return oidc_login.redirect(settings.LTI_TOOL_CONFIG['LAUNCH_URL'])
    except Exception as e:
        # Captura cualquier excepción durante el inicio de sesión OIDC y registra el error.
        logger.exception("Error during LTI login initiation:")
        # Renderiza una página de error amigable para el usuario.
        return render(request, 'recommender_app/error.html', {'message': f'Error en el inicio de sesión LTI: {e}'})



@csrf_exempt
def lti_launch(request):
    """
    Endpoint de lanzamiento LTI.
    Moodle enviará una solicitud POST a esta URL con los datos del lanzamiento LTI.
    Aquí es donde procesamos la solicitud y mostramos las recomendaciones.
    """
    # Se asegura de que la solicitud sea POST, como lo requiere LTI 1.3 para lanzamientos.
    if request.method != 'POST':
        return render(request, 'recommender_app/error.html', {'message': 'Acceso no permitido. Solo se aceptan solicitudes POST para el lanzamiento LTI.'})

    try:
        # Inicializa el almacenamiento de datos de lanzamiento usando el caché de Django.
        launch_data_storage = DjangoCacheDataStorage(cache_name='default')

        # Crea una instancia de DjangoMessageLaunch para manejar el lanzamiento LTI.
        message_launch = DjangoMessageLaunch(request, tool_conf, launch_data_storage=launch_data_storage)

        # Valida el lanzamiento LTI y obtiene los datos decodificados.
        # Si la validación falla, se lanzará una LtiException.
        message_launch.validate()
        launch_data = message_launch.get_launch_data()

        # --- EXTRACCIÓN DE DATOS PARA LA PLANTILLA ---
        # Obtiene el ID de usuario del claim 'sub' (estándar LTI 1.3).
        user_id = launch_data.get("sub", "N/A")

        # Obtiene el ID del contexto (curso) de los claims anidados.
        context_claim = launch_data.get("https://purl.imsglobal.org/spec/lti/claim/context", {})
        context_id = context_claim.get("id", "N/A")
        course_title = context_claim.get("title", "N/A")

        # Obtiene los roles del usuario.
        roles = launch_data.get("https://purl.imsglobal.org/spec/lti/claim/roles") or launch_data.get("roles", [])

        # Obtiene el nombre y email del usuario.
        user_name = launch_data.get("name", "N/A")
        user_email = launch_data.get("email", "N/A")

        # Obtiene el título de la actividad LTI.
        resource_link_claim = launch_data.get("https://purl.imsglobal.org/spec/lti/claim/resource_link", {})
        activity_title = resource_link_claim.get("title", "N/A")

        # Obtiene el nombre de la plataforma LTI.
        tool_platform_claim = launch_data.get("https://purl.imsglobal.org/spec/lti/claim/tool_platform", {})
        platform_name = tool_platform_claim.get("name", "N/A")
        # --- FIN DE EXTRACCIÓN DE DATOS ---

        # Lógica para obtener recomendaciones (aquí se llama a la función de ejemplo).
        recommendations = get_recommendations_from_api(user_id, context_id)

        # Prepara los datos para pasar a la plantilla.
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
            'raw_lti_data': json.dumps(launch_data, indent=2, ensure_ascii=False), # Datos brutos para depuración
        }

        # Renderiza la plantilla con las recomendaciones obtenidas.
        return render(request, 'recommender_app/recommendations.html', context)

    except LtiException as e:
        # Captura errores específicos de validación LTI (ej. "State not found", firma inválida).
        logger.exception("LTI launch error (LtiException):")
        return render(request, 'recommender_app/error.html', {'message': f'Error en el lanzamiento LTI: {e}'})
    except Exception as e:
        # Captura cualquier otro error inesperado.
        logger.exception("Unexpected error during LTI launch:")
        return render(request, 'recommender_app/error.html', {'message': f'Error inesperado durante el lanzamiento LTI: {e}'})

def get_recommendations_from_api(user_id, context_id):
    """
    Función para obtener recomendaciones reales consultando la base de datos de EducationalResource.
    Por ahora, filtra recursos por el ID del curso.
    """
    recommended_resources = []
    try:
        # Filtra los recursos por el lti_context_id del curso actual
        # Asegúrate de que los recursos que agregaste en el admin tengan el mismo lti_context_id
        # que el curso de Moodle desde el que estás lanzando (ej. "2" para "base de datos I").
        resources_from_db = EducationalResource.objects.filter(lti_context_id=context_id).order_by('?')[:5] # Limita a 5, orden aleatorio

        if not resources_from_db.exists():
            logger.info(f"No se encontraron recursos para el contexto LTI: {context_id}. Intentando buscar recursos genéricos.")
            # Si no hay recursos específicos del curso, busca algunos recursos sin contexto LTI asignado
            resources_from_db = EducationalResource.objects.filter(lti_context_id__isnull=True).order_by('?')[:5]
            if not resources_from_db.exists():
                logger.info("No se encontraron recursos genéricos.")
                return [
                    {"title": "No hay recomendaciones disponibles para este curso. Intenta añadir más recursos.", "url": "#"}
                ]

        for resource in resources_from_db:
            recommended_resources.append({
                "title": resource.title,
                "url": resource.url,
                "description": resource.description, # Puedes usar la descripción en la plantilla si la modificas
                "type": resource.resource_type,      # Puedes usar el tipo en la plantilla
            })

    except Exception as e:
        logger.error(f"Error al obtener recomendaciones de la base de datos: {e}")
        # En caso de error, devuelve un conjunto de recomendaciones de fallback
        return [
            {"title": "Error al cargar recomendaciones desde la base de datos.", "url": "#"}
        ]
    
    return recommended_resources


@csrf_exempt
def jwks(request):
    """
    Endpoint JWKS (JSON Web Key Set).
    Moodle usará esta URL para obtener las claves públicas de tu herramienta
    y verificar la firma de los JWTs que tu herramienta le envíe.
    """
    try:
        # Renderiza el conjunto de claves públicas de la herramienta.
        return DjangoJwks.render_jwks(tool_conf)
    except Exception as e:
        logger.exception("Error generating JWKS:")
        return render(request, 'recommender_app/error.html', {'message': f'Error al generar JWKS: {e}'})
@api_view(['POST'])
def record_interaction(request):
    """
    Endpoint API para registrar interacciones de usuarios con recursos educativos.
    Espera un método POST con datos de interacción en formato JSON.
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
