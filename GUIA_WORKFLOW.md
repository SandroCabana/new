# Guía de Workflow — LTI Moodle Recommender
> Última actualización: 2026-03-11

Esta guía cubre el flujo completo desde cero hasta tener el sistema con datos y recomendaciones activas.
Cada paso incluye la versión **automática** (Celery/Beat) y **manual** (shell/CLI).

---

## 📋 Flujo General

```
[0] Levantar servicios Docker
        ↓
[1] Verificar migraciones
        ↓
[2] Scraping de recursos educativos
        ↓
[3] Generar embeddings vectoriales
        ↓
[4] Entrenar modelos ML
        ↓
[5] Precomputar recomendaciones (cache)
        ↓
[6] Configurar Integración LTI 1.3
        ↓
[7] ¡Sistema listo para Moodle!
```

---

## PASO 0 — Levantar servicios Docker

```bash
cd ~/lti_moodle_recomender/lti_recommender_project

# Levantar todo
docker compose up -d

# Verificar estado
docker compose ps

# Ver logs en tiempo real
docker compose logs -f web
docker compose logs -f celery_worker
```

**Servicios esperados:**
| Contenedor | Estado |
|---|---|
| `lti_recommender_web` | Up (healthy) |
| `lti_recommender_db` | Up (healthy) |
| `lti_recommender_redis` | Up (healthy) |
| `lti_recommender_celery_worker` | Up |
| `lti_recommender_celery_beat` | Up |
| `lti_recommender_nginx` | Up |

**Si algún servicio falla:**
```bash
# Reiniciar un servicio específico
docker compose restart web

# Forzar recreación (después de cambios en código)
docker compose up -d --force-recreate web celery_worker celery_beat

# Rebuild completo (solo si cambias requirements.txt o Dockerfile)
docker compose build web
docker compose up -d --force-recreate web celery_worker celery_beat
```

---

## PASO 1 — Verificar migraciones

**⚠️ Obligatorio antes de cualquier otra cosa.**

```bash
# Verificar migraciones pendientes
docker exec -it lti_recommender_web python manage.py showmigrations | grep "\[ \]"

# Aplicar migraciones pendientes
docker exec -it lti_recommender_web python manage.py makemigrations
docker exec -it lti_recommender_web python manage.py migrate
```

**Nota importante sobre la migración 0004 de resources:**  
La columna `embedding` cambia de `jsonb` → `vector(768)`. PostgreSQL no puede hacer este cast directamente.
La migración usa `RemoveField + AddField` en vez de `AlterField`. Los embeddings previos se pierden pero se regeneran en el Paso 3.

---

## PASO 2 — Scraping de recursos educativos

### Automático (Celery Beat — se ejecuta nightly a las 3am UTC)
> Se configura automáticamente vía `django_celery_beat`. No requiere intervención.

### Manual — opción A: directo con Scrapy (recomendado para desarrollo)
```bash
# Spider oer: usa API de arXiv — ~250 recursos de cs.AI, cs.LG, cs.CV, cs.CL, cs.SE
docker exec -it lti_recommender_web bash -c \
  "cd /srv/lti_recommender_project/scraper && scrapy crawl oer"

# Spider oercommons: requiere scrapy-playwright (no instalado aún)
# docker exec -it lti_recommender_web bash -c \
#   "cd /srv/lti_recommender_project/scraper && scrapy crawl oercommons"
```

### Manual — opción B: via tarea Celery (en background)
```bash
docker exec -it lti_recommender_web python manage.py shell -c "
from lti_recommender_project.apps.recommendations.tasks import run_scraper_task
result = run_scraper_task.apply_async(queue='scraping')
print('Task ID:', result.id)
"

# Ver progreso
docker compose logs -f celery_worker
```

### Verificar resultado
```bash
docker exec -it lti_recommender_web python manage.py shell -c "
from lti_recommender_project.apps.resources.models import EducationalResource
print('Recursos en BD:', EducationalResource.objects.count())
"
```

### Ver recursos en el Admin
Ir a: **http://localhost:8080/admin/resources/educationalresource/**

---

## PASO 3 — Generar embeddings vectoriales

Los embeddings permiten búsqueda semántica. Modelo: `paraphrase-multilingual-mpnet-base-v2` (768 dims).  
**Primera ejecución:** descarga el modelo (~420MB, tarda ~2 min).  
**Ejecución posterior:** solo procesa recursos nuevos (incremental).

### Automático (Celery Beat — se ejecuta cada hora)
> Configurado automáticamente. Detecta recursos nuevos/modificados.

### Manual
```bash
docker exec -it lti_recommender_web python manage.py shell -c "
from lti_recommender_project.apps.recommendations.tasks import update_embeddings_incremental
result = update_embeddings_incremental.apply_async(queue='embeddings')
print('Task ID:', result.id)
"

# Monitorear progreso
docker compose logs -f celery_worker
```

### Verificar resultado
```bash
docker exec -it lti_recommender_web python manage.py shell -c "
from lti_recommender_project.apps.resources.models import EducationalResource
total = EducationalResource.objects.count()
con_emb = EducationalResource.objects.exclude(embedding=None).count()
print(f'Total: {total} | Con embedding: {con_emb} | Sin embedding: {total - con_emb}')
"
```

**⚠️ Si quedan recursos sin embedding después de que el task termina:**
Reiniciar el worker para recargar el módulo corregido y volver a lanzar:
```bash
docker compose restart celery_worker
# Luego volver a lanzar la tarea manual de arriba
```

---

## PASO 4 — Entrenar modelos ML

Los modelos colaborativos (SVD, NCF, Sequential) requieren datos de interacción de usuarios.  
El modelo de **contenido/semántico** funciona solo con embeddings (Paso 3).

### Automático (Celery Beat — se ejecuta nightly a las 2am UTC)
> Configrado automáticamente.

### Manual
```bash
docker exec -it lti_recommender_web python manage.py shell -c "
from lti_recommender_project.apps.recommendations.tasks import retrain_all_models
result = retrain_all_models.apply_async(queue='ml_training')
print('Task ID:', result.id)
"

# Ver resultado
docker compose logs -f celery_worker | grep -E "retrain|SVD|NCF|Sequential|error"
```

### Estado esperado
Después del entrenamiento, el sistema ejecuta **Automáticamente un "Evaluador Offline"**:
1. Extrae un `test_set` (holdout de las últimas interacciones de los usuarios).
2. Evalúa métricas complejas (Precision@5, NDCG@5, HitRate@10).
3. Ajusta los pesos dinámicos del modelo **Ensemble / Híbrido** según quien tuvo mejor desempeño.
4. Guarda los resultados en la BD (`analytics_modelevaluationresult`).

```
# Logs esperados en celery_worker
[INFO] matrix_factorization Training complete. RMSE: 1.0105
[INFO] evaluate_models Evaluating ensemble...
[INFO] tasks Offline eval saved for ensemble: P@5=0...
[INFO] ensemble Auto-adjusted weights: {'svd': 0.33, 'ncf': 0.21, ...}
```

### 🔴 Ver métricas (Dashboard Visual)
Para ver los resultados históricos del modelo y sus tendencias:
👉 Ir a: **http://localhost:8080/analytics/dashboard/visual/**

**Nota:** El motor de recomendaciones usa el ensemble híbrido. Aunque algunos modelos colaborativos fallen inicialmente (por falta de interacciones en cold-start), las recomendaciones por **similaridad semántica** (embeddings) seguirán funcionando correctamente.

---

## PASO 5 — Precomputar recomendaciones en cache

Pre-calcula y cachea recomendaciones para usuarios activos (reduce latencia de respuesta).

### Automático (Celery Beat — cada 30 minutos)
> Configurado automáticamente. Solo tiene efecto cuando hay usuarios con interacciones.

### Manual
```bash
docker exec -it lti_recommender_web python manage.py shell -c "
from lti_recommender_project.apps.recommendations.tasks import precompute_active_users
result = precompute_active_users.apply_async(queue='recommendations')
print('Task ID:', result.id)
"
```

---

## PASO 6 — Configurar Integración LTI 1.3 🎓

Este paso vincula Moodle con el recomendador.

### 6.1 — Generar Claves RSA (Automático)
Las claves se generan al arrancar el contenedor en `/app/keys/`.  
Puedes ver la **Llave Pública** en: `http://localhost:8080/lti/jwks/`

### 6.2 — Registrar Herramienta en Moodle
1. Ve a **Administración del sitio → Plugins → Herramienta externa → Gestionar herramientas**.
2. Haz clic en **Configurar una herramienta manualmente**.
   - **URL de la herramienta**: `http://localhost:8080/lti/launch/`
   - **Keyset URL**: `http://localhost:8080/lti/jwks/`
   - **Login URL**: `http://localhost:8080/lti/login/`

### 6.3 — Registro en Django (Admin)
Usa estas URLs para el puente Nginx:
- **Key Set URL**: `http://nginx/moodle-proxy/stable_main/mod/lti/certs.php`
- **Auth Token URL**: `http://nginx/moodle-proxy/stable_main/mod/lti/token.php`

---

## PASO 7 — Verificación completa del sistema

```bash
# Estado de datos
docker exec -it lti_recommender_web python manage.py shell -c "
from lti_recommender_project.apps.resources.models import EducationalResource
from lti_recommender_project.apps.interactions.models import UserInteraction
total = EducationalResource.objects.count()
con_emb = EducationalResource.objects.exclude(embedding=None).count()
interacciones = UserInteraction.objects.count()
print(f'Recursos: {total} | Con embedding: {con_emb} | Interacciones: {interacciones}')
"

# Verificar cola de Redis
docker exec lti_recommender_redis redis-cli -n 1 LLEN embeddings
docker exec lti_recommender_redis redis-cli -n 1 LLEN ml_training
docker exec lti_recommender_redis redis-cli -n 1 LLEN scraping

# Probar búsqueda semántica
docker exec -it lti_recommender_web python manage.py shell -c "
from lti_recommender_project.apps.recommendations.services.embedding_service import get_embedding_service
svc = get_embedding_service()
results = svc.find_similar_resources('machine learning neural networks', limit=3)
for r in results:
    print(f'  - {r.title[:60]} ({r.resource_type})')
"
```

---

## 📋 Referencia rápida de colas Celery

| Task | Cola | Trigger automático |
|---|---|---|
| `run_scraper_task` | `scraping` | Nightly 3am UTC |
| `update_embeddings_incremental` | `embeddings` | Hourly |
| `retrain_all_models` | `ml_training` | Nightly 2am UTC |
| `precompute_active_users` | `recommendations` | Cada 30 min |

**⚠️ Regla crítica:** Siempre usar `apply_async(queue='<queue>')`, nunca `.delay()` sin queue.  
`.delay()` envía al queue `celery` (default) que el worker **no escucha**.

```bash
# Ver tareas activas en cada cola
docker exec lti_recommender_redis redis-cli -n 1 LLEN embeddings
docker exec lti_recommender_redis redis-cli -n 1 LLEN ml_training
docker exec lti_recommender_redis redis-cli -n 1 LLEN recommendations
docker exec lti_recommender_redis redis-cli -n 1 LLEN scraping
docker exec lti_recommender_redis redis-cli -n 1 LLEN celery  # ← debe ser siempre 0
```

---

## 🔧 Comandos de mantenimiento

```bash
# Limpiar cola atascada (si hay tasks zombi)
docker exec lti_recommender_redis redis-cli -n 1 DEL celery

# Ver logs de un contenedor específico
docker compose logs --tail=50 celery_worker
docker compose logs --tail=50 web

# Acceder al shell de la BD
docker exec -it lti_recommender_db psql -U lti_user -d lti_recommender_db

# Ver columnas de una tabla
docker exec lti_recommender_db psql -U lti_user -d lti_recommender_db \
  -c "\d recommender_app_educationalresource"

# Borrar todos los embeddings y regenerar desde cero
docker exec -it lti_recommender_web python manage.py shell -c "
from lti_recommender_project.apps.resources.models import EducationalResource
EducationalResource.objects.all().update(embedding=None, embedding_updated_at=None)
print('Embeddings borrados. Lanzar update_embeddings_incremental para regenerar.')
"
```

---

## 📅 Schedule automático (Celery Beat)

| Hora (UTC) | Tarea | Cola |
|---|---|---|
| Cada hora | `update_embeddings_incremental` | `embeddings` |
| Cada 30 min | `precompute_active_users` | `recommendations` |
| 2:00am | `retrain_all_models` | `ml_training` |
| 3:00am | `run_scraper_task` + embeddings | `scraping` → `embeddings` |

Ver y editar el schedule en: **http://localhost:8080/admin/django_celery_beat/periodictask/**
