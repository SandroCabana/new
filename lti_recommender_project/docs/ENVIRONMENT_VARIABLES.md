# 📚 Análisis de Variables de Entorno - LTI Recommender Project

## Resumen Ejecutivo

**Total de variables:** 47  
**Variables críticas (deben cambiarse):** 12  
**Variables opcionales:** 35

---

## 🔴 Variables CRÍTICAS (Seguridad)

Estas **DEBEN** cambiarse en producción:

| Variable | Valor por Defecto | ¿Por qué cambiar? | Cómo generar |
|----------|-------------------|-------------------|--------------|
| `SECRET_KEY` | `django-insecure-...` | Usado para firmar cookies/tokens | `python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'` |
| `DB_PASSWORD` | `lti_password` | Acceso a la base de datos | `openssl rand -base64 32` |
| `DJANGO_SUPERUSER_PASSWORD` | `admin123` | Acceso admin total | Elegir contraseña fuerte (min 12 caracteres) |
| `LTI_CLIENT_ID` | `your-client-id...` | Identifica la herramienta en Moodle | Obtenido de Moodle al registrar la tool |
| `LTI_PRIVATE_KEY_PATH` | `/app/keys/lti_private_key.pem` | Firma tokens LTI | Auto-generado en primer arranque |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | Previene HTTP Host header attacks | Agregar tu dominio: `example.com,www.example.com` |
| `CSRF_TRUSTED_ORIGINS` | `http://localhost,...` | Protección CSRF | Incluir: `https://your-domain.com,https://your-moodle.com` |

---

## 🟡 Variables IMPORTANTES (Configuración)

Deben configurarse para que la aplicación funcione correctamente:

### Django Core
| Variable | Descripción | Default | Producción |
|----------|-------------|---------|------------|
| `DEBUG` | Modo debug | `True` | `False` |
| `LOG_LEVEL` | Nivel de logging | `DEBUG` | `INFO` o `WARNING` |

### Base de Datos
| Variable | Descripción | Default |
|----------|-------------|---------|
| `DB_NAME` | Nombre de la DB | `lti_recommender_db` |
| `DB_USER` | Usuario PostgreSQL | `lti_user` |
| `DB_HOST` | Host de PostgreSQL | `db` (nombre del servicio Docker) |
| `DB_PORT` | Puerto PostgreSQL | `5432` |

### LTI Configuration
| Variable | Descripción | Ejemplo |
|----------|-------------|---------|
| `LTI_ISS` | Issuer del LMS | `https://moodle.university.edu` |
| `LTI_DEPLOYMENT_ID` | ID de deployment | `1` |
| `MOODLE_AUTH_URL` | URL de auth del LMS | `https://moodle.edu/mod/lti/auth.php` |
| `MOODLE_TOKEN_URL` | URL de token del LMS | `https://moodle.edu/mod/lti/token.php` |
| `MOODLE_JWKS_URL` | URL de JWKS del LMS | `https://moodle.edu/mod/lti/certs.php` |

### URLs de la Herramienta
| Variable | Descripción | Ejemplo |
|----------|-------------|---------|
| `LTI_JWKS_URL` | Public JWKS endpoint | `https://your-app.com/lti/jwks/` |
| `LTI_AUTH_LOGIN_URL` | Login initiation | `https://your-app.com/lti/login/` |
| `LTI_LAUNCH_URL` | Launch endpoint | `https://your-app.com/lti/launch/` |

---

## 🟢 Variables OPCIONALES (Features)

Pueden dejarse con valores por defecto:

### Cache (Redis)
| Variable | Descripción | Default | Nota |
|----------|-------------|---------|------|
| `REDIS_URL` | Conexión a Redis | `redis://redis:6379/0` | Si no se configura, usa LocMemCache |
| `CACHE_TTL` | Timeout del cache | `300` (5 min) | En segundos |

### Machine Learning
| Variable | Descripción | Default |
|----------|-------------|---------|
| `ML_EMBEDDING_MODEL` | Modelo de sentence-transformers | `sentence-transformers/all-MiniLM-L6-v2` |
| `ML_EMBEDDING_DIMENSION` | Dimensión del vector | `384` |
| `ML_SIMILARITY_THRESHOLD` | Umbral de similitud | `0.3` |
| `ML_CONTENT_WEIGHT` | Peso filtrado contenido | `0.5` |
| `ML_USER_WEIGHT` | Peso filtrado colaborativo | `0.3` |
| `ML_POPULARITY_WEIGHT` | Peso popularidad | `0.2` |

### Gunicorn (Performance)
| Variable | Descripción | Default | Recomendado |
|----------|-------------|---------|-------------|
| `GUNICORN_WORKERS` | Número de workers | `4` | `2-4 x CPU cores` |
| `GUNICORN_TIMEOUT` | Timeout por request | `120` seg | `120-180` seg |
| `GUNICORN_BIND` | Dirección de bind | `0.0.0.0:8000` | No cambiar |

### Archivos Estáticos
| Variable | Descripción | Default |
|----------|-------------|---------|
| `STATIC_URL` | URL base para estáticos | `/static/` |
| `STATIC_ROOT` | Directorio de estáticos | `/app/staticfiles` |
| `MEDIA_URL` | URL base para media | `/media/` |
| `MEDIA_ROOT` | Directorio de media |`/app/media` |

### Seguridad (Cookies)
| Variable | Descripción | Default | Producción |
|----------|-------------|---------|------------|
| `SESSION_COOKIE_SECURE` | HTTPS only | `False` | `True` |
| `SESSION_COOKIE_SAMESITE` | SameSite policy | `None` | `None` (para LTI) |
| `CSRF_COOKIE_SECURE` | HTTPS only | `False` | `True` |

---

## 📊 Distribución de Variables por Categoría

```
Total: 47 variables

🔴 Críticas (Seguridad):        7 (15%)
🟡 Importantes (Config):       15 (32%)
🟢 Opcionales (Features):      25 (53%)
```

---

## 🔍 Valores Hardcoded Encontrados en `settings.py`

### ❌ Problemas de Seguridad
```python
# settings.py (ORIGINAL)
SECRET_KEY = 'django-insecure-jg)6h)8!+iv14os2zi76$_5ao-^h99zic!il%-ek2y9jli2*ue'  # ❌ EXPUESTO
DEBUG = True  # ❌ No debe estar siempre en True
ALLOWED_HOSTS = []  # ❌ Vacío permite cualquier host en DEBUG
```

### ❌ Credenciales Expuestas
```python
# settings.py (ORIGINAL)
DATABASES = {
    'default': {
        'NAME': 'lti_recommender_db',  # ❌ Hardcoded
        'USER': 'lti_user',            # ❌ Hardcoded  
        'PASSWORD': 'lti_user',        # ❌ CONTRASEÑA EN CÓDIGO
        'HOST': 'localhost',           # ❌ No funciona en Docker
    }
}
```

### ❌ Configuración LTI Hardcoded
```python
# settings.py (ORIGINAL)
LTI_TOOL_CONFIG = {
    'CLIENT_ID': 'HzDcDuQZIXoITpL',  # ❌ Específico de un Moodle
    'MOODLE_AUTH_URL': 'http://localhost/stable_main/mod/lti/auth.php',  # ❌ Environment específico
}
```

---

## ✅ Solución: `settings_docker.py`

Todas las variables ahora se leen de `.env`:

```python
# settings_docker.py (NUEVO)
import environ

env = environ.Env()
environ.Env.read_env('.env')

SECRET_KEY = env('SECRET_KEY')  # ✅ Desde .env
DEBUG = env.bool('DEBUG', default=False)  # ✅ Default seguro
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS')  # ✅ Configurable

DATABASES = {
    'default': {
        'NAME': env('DB_NAME'),      # ✅ Desde .env
        'USER': env('DB_USER'),       # ✅ Desde .env
        'PASSWORD': env('DB_PASSWORD'),  # ✅ Desde .env (nunca en código)
        'HOST': env('DB_HOST'),       # ✅ Funciona en Docker
    }
}
```

---

## 🚀 Quick Start Checklist

### Desarrollo Local

```bash
cp .env.example .env
nano .env  # Editar solo LTI_CLIENT_ID si testeas con Moodle
docker-compose up -d
```

### Producción

```bash
cp .env.production .env
nano .env
```

Cambiar OBLIGATORIAMENTE:
- [ ] `SECRET_KEY` (generar nuevo)
- [ ] `DEBUG=False`
- [ ] `DB_PASSWORD` (generar seguro)
- [ ] `DJANGO_SUPERUSER_PASSWORD` (cambiar de "admin123")
- [ ] `ALLOWED_HOSTS` (agregar tu dominio)
- [ ] `LTI_CLIENT_ID` (desde Moodle)
- [ ] `MOODLE_*_URL` (URLs reales de tu Moodle)
- [ ] `CSRF_TRUSTED_ORIGINS` (incluir tu dominio y Moodle)

```bash
docker-compose build
docker-compose up -d
```

---

## 📝 Comandos Útiles

### Generar SECRET_KEY
```bash
python3 -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
```

### Generar Password Seguro
```bash
openssl rand -base64 32
```

### Ver Claves LTI Generadas
```bash
docker-compose exec web cat /app/keys/lti_public_key.pem
```

### Verificar Configuración
```bash
docker-compose exec web python manage.py check --deploy
```

---

## ⚠️ Advertencias Finales

1. **NUNCA** commitear `.env` al repositorio (ya está en `.gitignore`)
2. **NUNCA** usar valores de `.env.example` en producción
3. **SIEMPRE** usar HTTPS en producción (`SESSION_COOKIE_SECURE=True`)
4. **SIEMPRE** cambiar `SECRET_KEY` y `DB_PASSWORD`
5. **VERIFICAR** que `DEBUG=False` en producción

---

## 📚 Referencias

- [Django Environment Variables Best Practices](https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/)
- [LTI 1.3 Security](https://www.imsglobal.org/spec/security/v1p0/)
- [Docker Security](https://docs.docker.com/engine/security/)
