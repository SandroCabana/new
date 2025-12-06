# Guía de Configuración de PostgreSQL para LTI Recommender

## Instalación de PostgreSQL

### En Ubuntu/Debian:
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

### En macOS:
```bash
brew install postgresql
brew services start postgresql
```

## Configuración de la Base de Datos

### 1. Crear usuario y base de datos

```bash
sudo -u postgres psql
```

Dentro de psql:
```sql
CREATE DATABASE lti_recommender_db;
CREATE USER lti_user WITH PASSWORD 'lti_user';
ALTER ROLE lti_user SET client_encoding TO 'utf8';
ALTER ROLE lti_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE lti_user SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE lti_recommender_db TO lti_user;
\q
```

### 2. Instalar adaptador de PostgreSQL para Python

```bash
pip install psycopg2-binary
```

### 3. Actualizar settings.py

Edita `/home/molker/new/lti_recommender_project/settings.py`:

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'lti_recommender_db',
        'USER': 'lti_user',
        'PASSWORD': 'tu_password_seguro',
        'HOST': 'localhost',
        'PORT': '5432',
        'OPTIONS': {
            'connect_timeout': 10,
        },
        'CONN_MAX_AGE': 600,  # Conexiones persistentes para mejor rendimiento
    }
}
```

### 4. Migrar datos de SQLite a PostgreSQL (Opcional)

Si ya tienes datos en SQLite y quieres migrarlos:

```bash
# Exportar datos de SQLite
python3 manage.py dumpdata --natural-foreign --natural-primary \
    -e contenttypes -e auth.Permission \
    --indent 2 > datadump.json

# Cambiar a PostgreSQL en settings.py

# Crear tablas en PostgreSQL
python3 manage.py migrate

# Importar datos
python3 manage.py loaddata datadump.json
```

### 5. Crear índices adicionales para mejor rendimiento

Crea un archivo de migración personalizado:

```bash
python3 manage.py makemigrations --empty resources --name add_performance_indexes
```

Edita el archivo de migración generado:

```python
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('resources', '0001_initial'),
    ]

    operations = [
        migrations.RunSQL(
            sql=[
                "CREATE INDEX idx_resource_url_hash ON recommender_app_educationalresource USING hash (url);",
                "CREATE INDEX idx_resource_tags_gin ON recommender_app_educationalresource USING gin (to_tsvector('english', tags));",
                "CREATE INDEX idx_resource_title_gin ON recommender_app_educationalresource USING gin (to_tsvector('english', title));",
            ],
            reverse_sql=[
                "DROP INDEX IF EXISTS idx_resource_url_hash;",
                "DROP INDEX IF EXISTS idx_resource_tags_gin;",
                "DROP INDEX IF EXISTS idx_resource_title_gin;",
            ]
        ),
    ]
```

Aplica la migración:
```bash
python3 manage.py migrate
```

## Ventajas de PostgreSQL sobre SQLite

1. **Concurrencia**: Múltiples escrituras simultáneas
2. **Escalabilidad**: Maneja millones de registros eficientemente
3. **Búsqueda de texto completo**: GIN indexes para búsqueda rápida en tags/títulos
4. **JSON nativo**: Mejor para datos estructurados complejos
5. **Replicación**: Fácil configurar réplicas para alta disponibilidad
6. **ACID completo**: Transacciones más robustas

## Optimizaciones Recomendadas

### 1. Configurar connection pooling con pgBouncer

```bash
sudo apt install pgbouncer
```

### 2. Ajustar configuración de PostgreSQL

Edita `/etc/postgresql/14/main/postgresql.conf`:

```conf
shared_buffers = 256MB
effective_cache_size = 1GB
maintenance_work_mem = 64MB
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100
random_page_cost = 1.1
effective_io_concurrency = 200
work_mem = 4MB
min_wal_size = 1GB
max_wal_size = 4GB
```

Reinicia PostgreSQL:
```bash
sudo systemctl restart postgresql
```

## Monitoreo y Mantenimiento

### Ver estadísticas de la base de datos:
```sql
SELECT schemaname, tablename, n_live_tup, n_dead_tup 
FROM pg_stat_user_tables 
ORDER BY n_live_tup DESC;
```

### Vacuum regular (limpieza):
```bash
# Configurar en crontab
0 2 * * * psql -U lti_user -d lti_recommender_db -c "VACUUM ANALYZE;"
```

### Backup automático:
```bash
# Script de backup
pg_dump -U lti_user lti_recommender_db > backup_$(date +%Y%m%d).sql
```

## Troubleshooting

### Error: "Peer authentication failed"
Edita `/etc/postgresql/14/main/pg_hba.conf`:
```
# Cambiar de:
local   all             all                                     peer

# A:
local   all             all                                     md5
```

Reinicia: `sudo systemctl restart postgresql`

### Error: "Too many connections"
Aumenta `max_connections` en `postgresql.conf`:
```
max_connections = 200
```
