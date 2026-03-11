# LTI Moodle Recommender — Contexto del Proyecto
> Última actualización: 2026-03-11

## Estado Actual ✅

| Servicio | Estado | Puerto externo |
|---|---|---|
| **web** (Gunicorn/Django) | ✅ healthy | interno :8000 |
| **nginx** | ✅ healthy | **:8080** → /admin, /api, /lti |
| **db** (PostgreSQL + pgvector) | ✅ healthy | :5432 |
| **redis** | ✅ healthy | :6379 |
| **celery_worker** | ⚠️ unhealthy (funciona) | - |
| **celery_beat** | ⚠️ unhealthy (funciona) | - |
| **LTI 1.3 Integration** | ✅ Configurado | Moodle ↔ Django OK |

**URL de acceso:** `http://localhost:8080/admin/`  
**LTI Launch URL:** `http://localhost:8080/lti/launch/`  
**Usuario admin:** `admin` (credenciales en `.env` → `DJANGO_SUPERUSER_*`)

### Estado de datos
| Dato | Cantidad |
|---|---|
| Recursos educativos en BD | **233** (arXiv: cs.AI, cs.LG, cs.CV, cs.CL, cs.SE) |
| Recursos con embedding generado | **233/233** ✅ completo |
| Interacciones de usuario | ✅ Capturando vía LTI / API |

---

## Arquitectura de Red — Puente Bridge (WSL/Desarrollo) 🌉

Un desafío crítico en el desarrollo local con **Docker Desktop + WSL2** es la comunicación entre el contenedor y Moodle (instalado nativamente en Windows).

### El problema del "Localhost Redirect"
Moodle está configurado para usarse en `http://localhost/stable_main`. Cuando Django intenta validar claves contra esa URL, falla porque su "localhost" es él mismo. Usar la IP del host causa que Moodle responda con un redirect 303 de vuelta a "localhost".

### La Solución: Nginx como Proxy Transparente
Hemos configurado una ruta en `nginx` (`/moodle-proxy/`) que reenvía la petición a la IP del host (`172.23.110.234`) pero **fuerza el encabezado `Host: localhost`**, engañando a Moodle para que no intente redirigir.

---

## Estructura de Directorios Clave

```
lti_moodle_recomender/
├── lti_recommender_project/       ← directorio de trabajo Docker
│   ├── Dockerfile                 ← build multi-stage Python 3.11-slim
│   ├── docker-compose.yml         ← orquestación de servicios
│   ├── .env                       ← variables de entorno (NO commitear)
│   ├── requirements.txt           ← dependencias Python
│   ├── celery_app.py              ← ⚠️ RENOMBRADO de celery.py (circular import fix)
│   ├── scripts/
│   │   ├── docker-entrypoint.sh   ← init: migraciones, static, superuser, gunicorn
│   │   └── generate-lti-keys.sh  ← genera claves RSA para LTI 1.3
│   ├── nginx/
│   │   └── conf.d/                ← configuración de virtual hosts
│   ├── apps/
│   │   ├── recommendations/       ← motor de recomendación + tareas Celery
│   │   │   └── services/embedding_service.py
│   │   ├── interactions/          ← tracking de interacciones LTI
│   │   ├── resources/             ← catálogo de recursos (tabla: recommender_app_educationalresource)
│   │   ├── analytics/             ← evaluación de modelos
│   │   └── users/                 ← usuarios LTI
│   └── scraper/                   ← Scrapy scraper
│       ├── scrapy.cfg             ← ⚠️ ejecutar scrapy desde ESTE directorio
│       └── scraper_project/
│           ├── settings.py        ← DJANGO_SETTINGS_MODULE=settings_docker
│           ├── pipelines.py       ← guarda en lti_recommender_project.apps.resources.models
│           └── spiders/
│               └── oer_spider.py  ← usa API de arXiv (OERCommons no tiene API pública)
├── ml/                            ← modelos ML
│   └── models/
│       ├── ensemble.py, neural_cf.py, sequential_rec.py
└── browser_extension/             ← extensión Chrome para tracking
```

---

## Arquitectura Docker

### Dockerfile (multi-stage)
- **Stage 1 (builder):** Instala dependencias con pip en `/root/.local`
- **Stage 2 (runtime):** Copia packages a `/home/django/.local` (usuario no-root)

**Rutas críticas dentro del contenedor:**
```
/srv/lti_recommender_project/  ← código fuente (PYTHONPATH=/srv)
/app/staticfiles/               ← archivos estáticos (volumen)
/app/logs/                      ← logs (volumen nombrado)
/app/keys/                      ← LTI RSA keys (volumen nombrado)
/home/django/.local/            ← paquetes pip instalados
```

### Tabla de BD real
El modelo `EducationalResource` usa `db_table = 'recommender_app_educationalresource'` (nombre legado). La app actual se llama `resources` pero la tabla mantiene el nombre original.

---

## Decisiones Técnicas Importantes

### 1. `celery.py` → `celery_app.py` (CRÍTICO)
Shadowing del paquete `celery` instalado causaba circular import.  
Celery se invoca con: `celery -A lti_recommender_project.celery_app worker/beat`

### 2. torch CPU-only (imagen ~2.5GB en vez de ~8GB)
```txt
--extra-index-url https://download.pytorch.org/whl/cpu
torch==2.2.0+cpu
```

### 3. Nginx en puerto 8080 (no 80)
Apache/PHP (Moodle nativo en WSL) ocupa el puerto 80 del host.

### 4. Rutas Celery — queues (CRÍTICO)
El worker escucha colas específicas. Los tasks deben especificar `queue=`:
```python
# En @shared_task decorators:
update_embeddings_incremental → queue='embeddings'
retrain_all_models            → queue='ml_training'
precompute_active_users       → queue='recommendations'
run_scraper_task              → queue='scraping'

# Al despachar manualmente:
task.apply_async(queue='embeddings')
```
⚠️ Si se usa `.delay()` sin queue, va al queue `celery` (default) que el worker **no escucha**.

### 5. Scraper — fuente de datos
OERCommons no tiene API pública. El spider `oer` usa la **API de arXiv**:
```
http://export.arxiv.org/api/query?search_query=cat:cs.AI&max_results=50
```
Categorías: `cs.AI`, `cs.LG`, `cs.CV`, `cs.CL`, `cs.SE` → ~250 recursos por crawl.

Para ejecutar el scraper manualmente:
```bash
docker exec -it lti_recommender_web bash -c "cd /srv/lti_recommender_project/scraper && scrapy crawl oer"
```

### 6. Migraciones - Nota importante
La migración `0004` convierte la columna `embedding` de `jsonb` → `vector(768)`.
PostgreSQL no puede hacer este cast directamente, por eso la migración usa `RemoveField` + `AddField` en vez de `AlterField`. Los embeddings previos se pierden pero se regeneran con la tarea Celery.

---

## Variables de Entorno Clave (.env)

```env
DJANGO_SETTINGS_MODULE=lti_recommender_project.settings_docker
SECRET_KEY=django-insecure-local-dev-key-change-in-production-abc123xyz789
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0
CSRF_TRUSTED_ORIGINS=http://localhost,http://127.0.0.1,http://localhost:8080,http://127.0.0.1:8080
SESSION_COOKIE_SAMESITE=Lax
CSRF_COOKIE_SAMESITE=Lax
DB_NAME=lti_recommender_db / DB_USER=lti_user / DB_HOST=db
REDIS_URL=redis://redis:6379/0 / CELERY_BROKER_URL=redis://redis:6379/1
ML_EMBEDDING_MODEL=paraphrase-multilingual-mpnet-base-v2
LTI_CLIENT_ID=local-dev-placeholder  # ← completar con Moodle real
```

---

## Comandos Frecuentes

```bash
# Poblar BD con recursos educativos (arXiv)
docker exec -it lti_recommender_web bash -c "cd /srv/lti_recommender_project/scraper && scrapy crawl oer"

# Generar embeddings para recursos nuevos
docker exec -it lti_recommender_web python manage.py shell -c "
from lti_recommender_project.apps.recommendations.tasks import update_embeddings_incremental
update_embeddings_incremental.apply_async(queue='embeddings')
"

# Verificar estado de datos
docker exec -it lti_recommender_web python manage.py shell -c "
from lti_recommender_project.apps.resources.models import EducationalResource
print('Total:', EducationalResource.objects.count())
print('Con embedding:', EducationalResource.objects.exclude(embedding=None).count())
"

# Migraciones
docker exec -it lti_recommender_web python manage.py makemigrations
docker exec -it lti_recommender_web python manage.py migrate

# Ver logs worker
docker compose logs -f celery_worker

# Reiniciar servicio
docker compose restart web
docker compose up -d --force-recreate web celery_worker celery_beat

# Rebuild (después de cambios en requirements.txt o Dockerfile)
docker compose build web
docker compose up -d --force-recreate web celery_worker celery_beat
```

---

## Pendientes / Issues Conocidos

| Issue | Severidad | Descripción |
|---|---|---|
| `celery_worker` / `nginx` unhealthy | Baja | Health checks mal configurados, servicios funcionales |
| Modelo SVD falla | Media | Falta instalar `scikit-surprise` en requirements.txt |
| `SequentialRecommendationModel` import roto | Media | Clase no exportada correctamente en `sequential_rec.py` |
| Sin datos de interacción | Media | NCF y modelos colaborativos requieren usuarios LTI reales |
| LTI no configurado | Alta | Requiere registrar la herramienta en Moodle real y configurar `.env` |
| `scrapy-user-agents` no instalado | Baja | Middleware comentado; añadido a requirements.txt para próximo rebuild |

---

## Stack Tecnológico

| Capa | Tecnología |
|---|---|
| Backend | Django 4.2.9, DRF 3.14 |
| Base de datos | PostgreSQL 15 + pgvector 0.3.2 |
| Cache/Queue | Redis 7, Celery 5.3.6 |
| ML | sentence-transformers 2.7, torch 2.2 CPU, scikit-learn 1.4 |
| Web server | Gunicorn 21.2 + Nginx (alpine) |
| LTI | PyLTI1p3 2.0 (LTI 1.3) |
| Embeddings | paraphrase-multilingual-mpnet-base-v2 (768 dims, multilingual) |
| Scraping | Scrapy 2.11.0 + arXiv API |
| Entorno | Docker Desktop + WSL2 (Linux/Windows) |
