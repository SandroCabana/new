# lti_recommender_project/recommender_app/views.py

from django.shortcuts import render, redirect
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
import json
import logging
from django.conf import settings

# Importaciones de PyLTI1p3
from pylti1p3.contrib.django import DjangoMessageLaunch, DjangoOIDCLogin, DjangoDbToolConf
from pylti1p3.contrib.django import DjangoCacheDataStorage
from pylti1p3.exception import LtiException # Importa LtiException para un manejo de errores más específico

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
    try:
        # Inicializa el almacenamiento de datos de lanzamiento usando el caché de Django.
        launch_data_storage = DjangoCacheDataStorage(cache_name='default')

        # Crea una instancia de DjangoMessageLaunch para manejar el lanzamiento LTI.
        message_launch = DjangoMessageLaunch(request, tool_conf, launch_data_storage=launch_data_storage)

        # Esto valida el lanzamiento y obtiene los datos
        launch_data = message_launch.get_launch_data()

        # Obtiene los datos del usuario y del contexto desde el lanzamiento LTI.
        user_id = launch_data.get("sub")  # "sub" es el estándar para el user_id en LTI 1.3
        context_id = launch_data.get("https://purl.imsglobal.org/spec/lti/claim/context", {}).get("id")

        # Aquí puedes integrar tu lógica de recomendación, por ejemplo, llamando a una API REST o un modelo de ML.
        recommendations = get_recommendations_from_api(user_id, context_id)

        # Renderiza la plantilla con las recomendaciones obtenidas.
        roles = launch_data.get("https://purl.imsglobal.org/spec/lti/claim/roles") or launch_data.get("roles") or []
        raw_lti_data = json.dumps(launch_data, indent=2, ensure_ascii=False)
        return render(
            request,
            'recommender_app/recommendations.html',
            {
                'recommendations': recommendations,
                'user_id': user_id,
                'context_id': context_id,
                'roles': roles,
                'raw_lti_data': raw_lti_data,
            }
        )

    except LtiException as e:
        logger.exception("LTI launch error:")
        return render(request, 'recommender_app/error.html', {'message': f'Error en el lanzamiento LTI: {e}'})
    except Exception as e:
        logger.exception("Unexpected error during LTI launch:")
        return render(request, 'recommender_app/error.html', {'message': f'Error inesperado durante el lanzamiento LTI: {e}'})

def get_recommendations_from_api(user_id, context_id):
    """
    Función de ejemplo para obtener recomendaciones.
    Aquí es donde integrarías tu lógica de API REST o modelo de recomendación.
    """
    # Aquí iría la lógica para comunicarse con tu API REST.
    # Por ahora, devuelve datos de ejemplo.
    return [
        {"title": "Recurso 1 recomendado (desde API)", "url": "#"},
        {"title": "Recurso 2 recomendado (desde API)", "url": "#"},
        {"title": "Recurso 3 recomendado (desde API)", "url": "#"},
    ]


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
