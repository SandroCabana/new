# API Documentation - LTI Recommender System

## Base URL

```
http://127.0.0.1:8000
```

## Endpoints

### 1. LTI Endpoints

#### 1.1 LTI Login (OIDC)

**Endpoint:** `POST /lti/login/`

**Descripción:** Endpoint de inicio de sesión OpenID Connect. Moodle envía la solicitud de autenticación aquí.

**Parámetros (enviados por Moodle):**
- `iss`: Issuer (URL de Moodle)
- `login_hint`: Hint del usuario
- `target_link_uri`: URI de destino
- `lti_message_hint`: Hint del mensaje LTI

**Respuesta:** Redirección a Moodle para completar autenticación

---

#### 1.2 LTI Launch

**Endpoint:** `POST /lti/launch/`

**Descripción:** Endpoint principal de lanzamiento LTI. Procesa el lanzamiento y muestra recomendaciones.

**Headers:**
```
Content-Type: application/x-www-form-urlencoded
```

**Parámetros (JWT en form data):**
- `id_token`: Token JWT firmado por Moodle
- `state`: Estado de la sesión

**Respuesta Exitosa:**
```html
<!-- Página HTML con recomendaciones personalizadas -->
```

**Datos Extraídos del Launch:**
- `user_id`: ID único del usuario
- `context_id`: ID del curso/contexto
- `user_name`: Nombre del usuario
- `user_email`: Email del usuario
- `course_title`: Título del curso
- `roles`: Roles del usuario en el curso

---

#### 1.3 JWKS (JSON Web Key Set)

**Endpoint:** `GET /lti/jwks/`

**Descripción:** Proporciona las claves públicas de la herramienta para que Moodle verifique firmas.

**Respuesta:**
```json
{
  "keys": [
    {
      "kty": "RSA",
      "alg": "RS256",
      "use": "sig",
      "kid": "unique-key-id",
      "n": "modulus-base64",
      "e": "AQAB"
    }
  ]
}
```

---

### 2. API REST Endpoints

#### 2.1 Registrar Interacción

**Endpoint:** `POST /api/interactions/`

**Descripción:** Registra una interacción del usuario con un recurso educativo.

**Headers:**
```
Content-Type: application/json
```

**Request Body:**
```json
{
  "lti_user_id": "usuario123",
  "lti_context_id": "curso456",
  "resource": 1,
  "interaction_type": "viewed",
  "value": 120.5
}
```

**Campos:**
- `lti_user_id` (string, requerido): ID del usuario LTI
- `lti_context_id` (string, requerido): ID del contexto/curso
- `resource` (integer, requerido): ID del recurso educativo
- `interaction_type` (string, requerido): Tipo de interacción (`viewed`, `completed`, `downloaded`, etc.)
- `value` (float, opcional): Valor asociado (ej: tiempo en segundos, puntuación)

**Respuesta Exitosa (201 Created):**
```json
{
  "id": 42,
  "lti_user_id": "usuario123",
  "lti_context_id": "curso456",
  "resource": 1,
  "interaction_type": "viewed",
  "value": 120.5,
  "timestamp": "2025-11-24T13:45:00Z"
}
```

**Respuesta de Error (400 Bad Request):**
```json
{
  "resource": ["This field is required."],
  "interaction_type": ["This field is required."]
}
```

---

## Modelos de Datos

### EducationalResource

```python
{
  "id": 1,
  "resource_id": "unique-hash-id",
  "title": "Introducción a Python",
  "description": "Curso básico de programación en Python",
  "url": "https://example.com/python-intro",
  "author": "Juan Pérez",
  "resource_type": "video",  # video, pdf, article, quiz, tool, other
  "tags": "programación, python, básico",
  "difficulty_level": "beginner",  # beginner, intermediate, advanced
  "lti_context_id": "curso123",  # null para recursos genéricos
  "created_at": "2025-11-20T10:00:00Z",
  "updated_at": "2025-11-24T12:00:00Z"
}
```

### UserInteraction

```python
{
  "id": 1,
  "lti_user_id": "usuario123",
  "lti_context_id": "curso456",
  "resource": 1,  # FK a EducationalResource
  "interaction_type": "viewed",
  "value": 120.5,
  "timestamp": "2025-11-24T13:45:00Z"
}
```

---

## Ejemplos de Uso

### Ejemplo 1: Registrar que un usuario vio un video

```bash
curl -X POST http://127.0.0.1:8000/api/interactions/ \
  -H "Content-Type: application/json" \
  -d '{
    "lti_user_id": "user_abc123",
    "lti_context_id": "course_xyz789",
    "resource": 5,
    "interaction_type": "viewed",
    "value": 300
  }'
```

### Ejemplo 2: Obtener JWKS

```bash
curl http://127.0.0.1:8000/lti/jwks/
```

### Ejemplo 3: Verificar recursos en la base de datos

```bash
python3 manage.py shell
>>> from lti_recommender_project.apps.resources.models import EducationalResource
>>> resources = EducationalResource.objects.all()
>>> for r in resources:
...     print(f"{r.id}: {r.title} ({r.resource_type})")
```

---

## Motor de Recomendaciones

El sistema utiliza un motor híbrido que combina:

1. **Filtrado Colaborativo (40%)**: Recomienda recursos que usuarios similares han visto
2. **Filtrado Basado en Contenido (40%)**: Recomienda recursos similares a los que el usuario ha interactuado
3. **Popularidad (20%)**: Recursos más vistos en el contexto actual

### Uso Programático

```python
from lti_recommender_project.apps.lti_integration.recommendation_engine import RecommendationEngine

engine = RecommendationEngine()
recommendations = engine.get_recommendations(
    user_id="user123",
    context_id="course456",
    limit=5,
    exclude_viewed=True
)

for rec in recommendations:
    print(f"{rec['title']} - {rec['url']}")
```

---

## Códigos de Estado HTTP

| Código | Significado |
|--------|-------------|
| 200 | OK - Solicitud exitosa |
| 201 | Created - Recurso creado exitosamente |
| 400 | Bad Request - Datos inválidos |
| 404 | Not Found - Recurso no encontrado |
| 500 | Internal Server Error - Error del servidor |

---

## Autenticación

Los endpoints LTI (`/lti/*`) no requieren autenticación adicional ya que usan el flujo LTI 1.3 con JWT firmados.

Los endpoints de API (`/api/*`) actualmente no requieren autenticación, pero se recomienda implementar autenticación por token en producción.

---

## Rate Limiting

Actualmente no hay límites de tasa implementados. Para producción, considera implementar throttling con Django REST Framework:

```python
REST_FRAMEWORK = {
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle'
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',
        'user': '1000/hour'
    }
}
```

---

## Webhooks / Callbacks

El sistema no implementa webhooks actualmente. Las interacciones deben ser registradas activamente mediante POST a `/api/interactions/`.

---

## Versionado de API

Versión actual: **v1** (implícita, no en URL)

Para futuras versiones, se recomienda usar versionado en URL:
```
/api/v1/interactions/
/api/v2/interactions/
```
