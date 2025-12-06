# Guía de Instalación - Sistema LTI Recommender

## Requisitos Previos

- Python 3.10+
- pip y venv
- Moodle 3.8+ (para integración LTI)
- Git (opcional)

## Instalación Paso a Paso

### 1. Clonar o Descargar el Proyecto

```bash
cd /ruta/deseada
# Si usas git:
git clone <repository-url> lti_recommender
cd lti_recommender
```

### 2. Crear Entorno Virtual

```bash
python3 -m venv venv_lti_recommender
source venv_lti_recommender/bin/activate  # En Linux/Mac
# En Windows: venv_lti_recommender\Scripts\activate
```

### 3. Instalar Dependencias

```bash
pip install -r requirements.txt
```

**Dependencias principales:**
- Django 5.2.4
- djangorestframework 3.16.0
- PyLTI1p3 2.0.0
- Scrapy (para scraper OER)

### 4. Configurar Base de Datos

El proyecto usa SQLite por defecto (desarrollo). Para producción, considera PostgreSQL.

```bash
python3 manage.py migrate
```

### 5. Crear Superusuario

```bash
python3 manage.py createsuperuser
```

Sigue las instrucciones para crear tu cuenta de administrador.

### 6. Generar Claves LTI (si no existen)

Las claves ya deberían estar en el proyecto (`lti_public_key.pem`, `lti_private_key.pem`). 

Si necesitas regenerarlas:

```bash
# Generar clave privada
openssl genrsa -out lti_private_key.pem 2048

# Generar clave pública
openssl rsa -in lti_private_key.pem -pubout -out lti_public_key.pem
```

### 7. Configurar Variables de Entorno (Opcional)

Crea un archivo `.env` en la raíz del proyecto:

```env
DEBUG=True
SECRET_KEY=tu-clave-secreta-aqui
ALLOWED_HOSTS=localhost,127.0.0.1

# Moodle URLs
MOODLE_URL=http://localhost/stable_main
```

### 8. Poblar Base de Datos con Recursos

#### Opción A: Agregar manualmente desde el admin

```bash
python3 manage.py runserver
```

Visita `http://127.0.0.1:8000/admin/` y agrega recursos educativos.

#### Opción B: Usar el scraper (requiere Scrapy instalado)

```bash
cd scraper_project
scrapy crawl oer_improved -s CLOSESPIDER_ITEMCOUNT=20
```

### 9. Ejecutar Servidor de Desarrollo

```bash
python3 manage.py runserver
```

El servidor estará disponible en `http://127.0.0.1:8000/`

## Configuración de Moodle (Integración LTI 1.3)

### 1. Acceder al Panel de Administración de Moodle

1. Inicia sesión como administrador
2. Ve a **Administración del sitio** → **Plugins** → **Actividades** → **Herramienta externa**
3. Click en **Gestionar herramientas**

### 2. Configurar Nueva Herramienta LTI

Click en **Configurar una herramienta manualmente** y completa:

**Configuración Básica:**
- **Nombre de la herramienta**: Sistema de Recomendación EPAI
- **URL de la herramienta**: `http://127.0.0.1:8000/lti/launch/`
- **Versión LTI**: LTI 1.3
- **Clave pública**: Copia el contenido de `lti_public_key.pem`

**URLs de Configuración:**
- **URL de inicio de sesión**: `http://127.0.0.1:8000/lti/login/`
- **URL de redirección**: `http://127.0.0.1:8000/lti/launch/`
- **URL del conjunto de claves públicas**: `http://127.0.0.1:8000/lti/jwks/`

**Servicios:**
- ✅ Aceptar calificaciones desde la herramienta
- ✅ Compartir el nombre del lanzador con la herramienta
- ✅ Compartir el correo del lanzador con la herramienta
- ✅ Aceptar información de miembros del curso desde la herramienta

**Configuración de Privacidad:**
- Compartir nombre: Siempre
- Compartir email: Siempre

### 3. Obtener Client ID de Moodle

Después de guardar, Moodle generará un **Client ID**. Cópialo.

### 4. Actualizar settings.py con Client ID

Edita `/lti_recommender_project/settings.py`:

```python
LTI_TOOL_CONFIG = {
    'CLIENT_ID': 'TU_CLIENT_ID_DE_MOODLE',  # ← Actualiza esto
    # ... resto de configuración
}
```

### 5. Agregar Actividad LTI en un Curso

1. Entra a un curso en Moodle
2. Activa edición
3. Agrega una actividad → **Herramienta externa**
4. Selecciona tu herramienta configurada
5. Guarda y lanza

## Verificación de Instalación

### Test 1: Sistema Django

```bash
python3 manage.py check
```

Debe mostrar: `System check identified no issues (0 silenced).`

### Test 2: Endpoint JWKS

Con el servidor corriendo, visita:
```
http://127.0.0.1:8000/lti/jwks/
```

Deberías ver un JSON con claves públicas.

### Test 3: Admin Panel

Visita `http://127.0.0.1:8000/admin/` y verifica que puedes:
- Ver recursos educativos
- Ver interacciones de usuarios

### Test 4: Integración LTI

Lanza la actividad desde Moodle y verifica:
- ✅ Redirección exitosa
- ✅ Página de recomendaciones se carga
- ✅ Datos del usuario se muestran correctamente

## Solución de Problemas

### Error: "State not found"

**Causa**: Problema con cookies de terceros o caché.

**Solución**:
1. Limpia caché del navegador
2. Verifica que `SESSION_COOKIE_SAMESITE = None` en settings.py
3. Usa HTTPS en producción

### Error: "Invalid signature"

**Causa**: Claves LTI no coinciden.

**Solución**:
1. Verifica que la clave pública en Moodle coincida con `lti_public_key.pem`
2. Regenera claves si es necesario

### No se muestran recomendaciones

**Causa**: No hay recursos en la base de datos.

**Solución**:
```bash
python3 manage.py shell
>>> from lti_recommender_project.apps.resources.models import EducationalResource
>>> EducationalResource.objects.count()
```

Si es 0, agrega recursos manualmente o ejecuta el scraper.

## Próximos Pasos

1. **Agregar más recursos**: Usa el admin o el scraper
2. **Personalizar recomendaciones**: Edita `recommendation_engine.py`
3. **Configurar para producción**: Ver documentación de deployment

## Soporte

Para problemas o preguntas, consulta la documentación en `/docs/` o revisa los logs:

```bash
tail -f /var/log/django/lti_recommender.log
```
