# LTI Moodle Recommender — Contexto del Proyecto
> Última actualización: 2026-03-16 06:45 (Meticulous Context Restoration)

## Estado Actual ✅

| Servicio | Estado | Puerto externo | Notas |
|---|---|---|---|
| **web** (Gunicorn/Django) | ✅ healthy | interno :8000 | Django 4.2.9 |
| **nginx** | ✅ healthy | **:8080** | Proxy para /admin, /api, /lti, /analytics |
| **db** (PostgreSQL + pgvector) | ✅ healthy | :5432 | pg15 + vector extension |
| **redis** | ✅ healthy | :6379 | DB 0=Cache, 1=Celery Broker, 2=Celery Results |
| **celery_worker** | ✅ healthy | - | Escucha colas: embeddings, ml_training, recommendations, scraping |
| **celery_beat** | ✅ healthy | - | Scheduler basado en base de datos |
| **LTI 1.3 Integration** | ✅ Funcional | Moodle ↔ Django OK |

**URLs de acceso (vía Nginx):**  
- **Admin Django:** `http://localhost:8080/admin/`  
- **Visual Dashboard ML:** `http://localhost:8080/analytics/dashboard/visual/`
- **LTI Launch URL:** `http://localhost:8080/lti/launch/`  
- **xAPI Receiver:** `http://localhost:8080/api/interactions/xapi/receiver/`

### Estado de datos (Verificado 16/Mar)
| Dato | Cantidad | Notas |
|---|---|---|
| **Total Recursos** | **1075** | Almacenados en `EducationalResource` |
| Recursos con embedding | **1075 (100%)** | Generados con `paraphrase-multilingual-mpnet-base-v2` |
| **Kaggle (Cursos)** | 707 | Dataset inicial e-learning |
| **arXiv (Papers EN)** | 268 | Scraping automatizado (CS/AI) |
| **YouTube (Videos ES)** | 75 | Canales: Platzi, midudev, quantum, etc. |
| **OpenAlex (Papers ES)** | 25 | Artículos académicos en español |

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
├── lti_recommender_project/       ← Directorio de trabajo Docker
│   ├── Dockerfile                 ← build multi-stage Python 3.11-slim
│   ├── docker-compose.yml         ← orquestación de servicios
│   ├── .env                       ← variables de entorno (Token xAPI, DB, etc.)
│   ├── requirements.txt           ← dependencias Python
│   ├── celery_app.py              ← ⚠️ RENOMBRADO de celery.py (circular import fix)
│   ├── scripts/
│   │   ├── docker-entrypoint.sh   ← init: migraciones, static, superuser, gunicorn
│   │   └── generate-lti-keys.sh  ← genera claves RSA para LTI 1.3
│   ├── nginx/
│   │   └── conf.d/                ← configuración de virtual hosts (Proxy LTI)
│   ├── apps/
│   │   ├── recommendations/       ← Motor híbrido + Tareas ML (Ensemble)
│   │   │   └── services/          ← Lógica de recomendación y embeddings
│   │   ├── interactions/          ← Tracking LTI + xAPI (Moodle Stream)
│   │   │   ├── xapi_views.py      ← Receptor de streams xAPI (LRS Parcial)
│   │   │   └── tasks.py           ← Procesamiento asíncrono de eventos
│   │   ├── resources/             ← Catálogo (HNSW Index en pgvector)
│   │   ├── analytics/             ← Dashboards Visuales y evaluación
│   │   └── users/                 ← Gestión de usuarios LTI
│   └── scraper/                   ← Scrapy scraper (Multi-spider)
│       ├── scrapy.cfg             ← Ejecutar scrapy desde ESTE directorio
│       └── scraper_project/
│           ├── settings.py        ← DJANGO_SETTINGS_MODULE=settings_docker
│           ├── pipelines.py       ← Guarda en EducationalResource
│           └── spiders/
│               ├── oer_spider.py         ← API arXiv (Papers EN)
│               ├── oercommons_spider.py  ← Web scraping OER Commons
│               ├── openalex_es_spider.py ← API OpenAlex (Papers ES)
│               └── youtube_edu_spider.py ← YouTube RSS (Videos ES)
├── ml/                            ← Modelos de Machine Learning (Core)
│   └── models/
│       ├── ensemble.py            ← Combinador (SVD, NCF, Sequential, FM, Hybrid)
│       └── neural_cf.py, fm.py, sequential_rec.py
└── browser_extension/             ← Extensión Chrome (Tracking Externo)
```

---

## Arquitectura Docker

### Dockerfile (multi-stage)
- **Stage 1 (builder):** Instala dependencias con pip en `/root/.local` utilizando `torch` CPU-only para ahorrar espacio.
- **Stage 2 (runtime):** Copia packages a `/home/django/.local` (usuario no-root por seguridad).

**Rutas críticas dentro del contenedor:**
```
/srv/lti_recommender_project/  ← Código fuente (PYTHONPATH=/srv)
/app/staticfiles/               ← Archivos estáticos colectados
/app/logs/                      ← Logs de la aplicación
/app/keys/                      ← Claves RSA para LTI 1.3
```

### Tabla de BD real
El modelo `EducationalResource` utiliza `db_table = 'recommender_app_educationalresource'`. Esta tabla cuenta con una columna `embedding` de tipo `vector(768)` optimizada con un índice **HNSW**.

---

## Decisiones Técnicas e Infraestructura

### 1. Vector Search (pgvector + HNSW)
Búsquedas de similitud coseno ultrarrápidas:
- **Index:** `pgvector.django.indexes.HnswIndex`
- **Config:** `m=16`, `ef_construction=64`, `opclasses=['vector_cosine_ops']`

### 2. Integración xAPI (Real-time tracking)
- **Mecanismo:** Webhook asíncrono desde Moodle (`logstore_xapi`).
- **Deduplicación:** Verificación de `statement_id` en metadata para evitar duplicados.
- **Mapeo:** Verbos traducidos a pesos (View=1.0, Attempt=2.0, Complete=5.0).
- **Auto-Ingesta:** Descubrimiento automático de actividades de Moodle no catalogadas.

### 3. Ensemble Weights (Actuales)
Combinación ponderada de modelos:
- **Hybrid (Semántico):** 0.25 (Pilar de cold-start)
- **Sequential:** 0.25 (Pattern capture)
- **Neural CF / FM:** 0.20 c/u (Deep Collaborative)
- **SVD:** 0.10 (Matrix Factorization)

---

## Comandos Frecuentes y Mantenimiento

```bash
# Verificar colas Celery
for q in celery embeddings ml_training recommendations scraping; do 
  echo -n "$q: "; docker exec lti_recommender_redis redis-cli -n 1 LLEN $q; 
done

# Scraping Manual
docker exec -it lti_recommender_web bash -c "cd scraper && scrapy crawl youtube_edu"

# Re-entrenamiento total
docker exec -it lti_recommender_web python manage.py shell -c "from apps.recommendations.tasks import retrain_all_models; retrain_all_models.delay()"
```

---

## Issues Resueltos Recientemente (Marzo 2026)

- ✅ **Fix 502 Bad Gateway:** Corregido `NameError: name 'path' is not defined` en `interactions/urls.py`.
- ✅ **Celery Resource Peak:** Optimización de workers y purga de colas tras restart.
- ✅ **xAPI Implementation:** Recepción y procesamiento de Moodle Logs funcional.
- ✅ **Boolean Check Fix:** Corregido `ValueError` en `resource.embedding` usando `.any()`/`.all()`.

---

## Stack Tecnológico 🛠️

| Capa | Tecnología |
|---|---|
| **Backend** | Django 4.2.9, DRF 3.14 |
| **BBDD** | PostgreSQL 15 + pgvector (HNSW Index) |
| ML Models | `sentence-transformers 2.7.0` (SBERT), PyTorch (CPU), scikit-surprise |
| **Task Engine** | Redis 7 + Celery 5.3 (Multiple queues) |
| **Web Infrastructure** | Gunicorn + Nginx (Proxy SameSite friendly) |
| **Scraping** | `Scrapy 2.11.0`, `BeautifulSoup4 4.12.3`, `scrapy-user-agents 0.1.1` |
| **Entorno** | Docker Desktop + WSL2 (Linux/Windows) |
| **Standards** | LTI 1.3, xAPI (IEEE 9274.1.1) |
