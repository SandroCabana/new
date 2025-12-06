#!/bin/bash
# Plan de Migración - Sistema de Recomendación IA
# Ejecutar paso a paso

# =========================================
# PASO 1: Backup del proyecto actual
# =========================================
echo "=== PASO 1: Creando backup ==="
cd /path/to/your/project
cp -r new new_backup_$(date +%Y%m%d)

# =========================================
# PASO 2: Crear nueva estructura
# =========================================
echo "=== PASO 2: Creando nueva estructura ==="

# Crear directorios principales
mkdir -p lti_recommender_project/{config,apps,ml,scraper,api,static,media,templates,tests,docs,scripts,deployment}

# Mover configuración existente
mv lti_recommender_project/* config/
mv config/settings.py config/settings/base.py

# Crear apps
mkdir -p apps/{core,lti_integration,users,interactions,resources,recommendations,analytics}

# Crear estructura ML
mkdir -p ml/{data_preprocessing,models,training,saved_models,notebooks}

# =========================================
# PASO 3: Migrar código existente
# =========================================
echo "=== PASO 3: Migrando código existente ==="

# Mover app de recomendaciones
mv recommender_app/* apps/lti_integration/

# Mover scraper
mv scraper_project scraper/

# =========================================
# PASO 4: Actualizar requirements.txt
# =========================================
echo "=== PASO 4: Actualizando dependencias ==="

cat > requirements.txt << 'EOF'
# Core Django
Django==4.2.9
djangorestframework==3.14.0
django-cors-headers==4.3.1
django-environ==0.11.2

# LTI Integration
pylti1p3==2.6.0
PyJWT==2.8.0

# Database
psycopg2-binary==2.9.9
dj-database-url==2.1.0

# Machine Learning
scikit-learn==1.4.0
pandas==2.2.0
numpy==1.26.3
scipy==1.12.0

# Deep Learning (opcional)
torch==2.1.2
transformers==4.36.2

# NLP
nltk==3.8.1
spacy==3.7.2

# Scraping
scrapy==2.11.0
beautifulsoup4==4.12.3
selenium==4.16.0
playwright==1.40.0

# Celery & Redis
celery==5.3.4
redis==5.0.1
django-celery-beat==2.5.0

# Utils
python-dotenv==1.0.0
requests==2.31.0
Pillow==10.2.0

# Development
pytest==7.4.4
pytest-django==4.7.0
black==23.12.1
flake8==7.0.0
ipython==8.19.0
jupyter==1.0.0

# Production
gunicorn==21.2.0
whitenoise==6.6.0
EOF

# =========================================
# PASO 5: Crear archivos de configuración
# =========================================
echo "=== PASO 5: Creando archivos de configuración ==="

# .env.example
cat > .env.example << 'EOF'
# Django
DEBUG=True
SECRET_KEY=your-secret-key-here
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/lti_recommender

# LTI
LTI_ISS=https://your-moodle-instance.com
LTI_CLIENT_ID=your-client-id
LTI_DEPLOYMENT_ID=your-deployment-id

# Redis
REDIS_URL=redis://localhost:6379/0

# ML Models
ML_MODEL_PATH=/path/to/models
EOF

# .gitignore
cat > .gitignore << 'EOF'
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
venv/
env/
ENV/

# Django
*.log
db.sqlite3
db.sqlite3-journal
/media
/static_root

# ML
*.pkl
*.joblib
*.h5
*.pt
/ml/saved_models/*
!/ml/saved_models/.gitkeep

# IDE
.vscode/
.idea/
*.swp
*.swo

# Environment
.env
*.pem

# Scraper
scraper/data/*
*.json
EOF

# =========================================
# PASO 6: Crear configuración modular
# =========================================
echo "=== PASO 6: Configuración modular ==="

# config/settings/__init__.py
cat > config/settings/__init__.py << 'EOF'
import os

env = os.environ.get('DJANGO_ENV', 'development')

if env == 'production':
    from .production import *
else:
    from .development import *
EOF

# config/settings/development.py
cat > config/settings/development.py << 'EOF'
from .base import *

DEBUG = True
ALLOWED_HOSTS = ['localhost', '127.0.0.1']

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

INSTALLED_APPS += ['django_extensions']
EOF

# =========================================
# PASO 7: Crear modelos base
# =========================================
echo "=== PASO 7: Creando modelos base ==="

# apps/users/models.py
cat > apps/users/models.py << 'EOF'
from django.contrib.auth.models import User
from django.db import models

class UserProfile(models.Model):
    """Perfil extendido del usuario con datos de aprendizaje"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    moodle_user_id = models.CharField(max_length=255, unique=True)
    
    # Estilo de aprendizaje (FSLSM)
    learning_style = models.JSONField(default=dict, help_text="Felder-Silverman Learning Style")
    
    # Nivel de conocimiento por tema
    knowledge_level = models.JSONField(default=dict, help_text="{'topic': score}")
    
    # Preferencias del usuario
    preferences = models.JSONField(default=dict)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'user_profiles'
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'
    
    def __str__(self):
        return f"{self.user.username} - Profile"
EOF

# apps/interactions/models.py
cat > apps/interactions/models.py << 'EOF'
from django.contrib.auth.models import User
from django.db import models

class UserInteraction(models.Model):
    """Registro de interacciones del usuario con recursos"""
    INTERACTION_TYPES = [
        ('view', 'View'),
        ('click', 'Click'),
        ('download', 'Download'),
        ('complete', 'Complete'),
        ('rate', 'Rate'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='interactions')
    resource = models.ForeignKey('resources.Resource', on_delete=models.CASCADE)
    interaction_type = models.CharField(max_length=50, choices=INTERACTION_TYPES)
    
    duration_seconds = models.IntegerField(default=0)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    # Contexto adicional (navegador, dispositivo, etc.)
    context = models.JSONField(default=dict)
    
    class Meta:
        db_table = 'user_interactions'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['resource', 'interaction_type']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.interaction_type} - {self.resource.title[:30]}"
EOF

# apps/resources/models.py
cat > apps/resources/models.py << 'EOF'
from django.db import models

class Topic(models.Model):
    """Temas o áreas de conocimiento"""
    name = models.CharField(max_length=200, unique=True)
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE)
    description = models.TextField(blank=True)
    
    class Meta:
        db_table = 'topics'
    
    def __str__(self):
        return self.name

class Resource(models.Model):
    """Recursos educativos"""
    RESOURCE_TYPES = [
        ('video', 'Video'),
        ('pdf', 'PDF Document'),
        ('article', 'Article'),
        ('interactive', 'Interactive'),
        ('quiz', 'Quiz'),
    ]
    
    title = models.CharField(max_length=500)
    description = models.TextField()
    url = models.URLField(max_length=1000)
    resource_type = models.CharField(max_length=100, choices=RESOURCE_TYPES)
    
    topics = models.ManyToManyField(Topic, related_name='resources')
    difficulty_level = models.CharField(max_length=50)  # beginner, intermediate, advanced
    
    # Embeddings para similitud
    embeddings = models.JSONField(null=True, blank=True)
    
    # Metadatos
    source = models.CharField(max_length=200)  # OER Commons, Khan Academy, etc.
    language = models.CharField(max_length=10, default='en')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'resources'
        indexes = [
            models.Index(fields=['resource_type', 'difficulty_level']),
        ]
    
    def __str__(self):
        return self.title
EOF

# =========================================
# PASO 8: Script de inicialización
# =========================================
cat > scripts/setup_project.sh << 'EOF'
#!/bin/bash

echo "Configurando proyecto..."

# Activar entorno virtual
source venv_lti_recommender/bin/activate

# Instalar dependencias
pip install -r requirements.txt

# Crear migraciones
python manage.py makemigrations

# Aplicar migraciones
python manage.py migrate

# Crear superusuario
python manage.py createsuperuser

# Cargar datos de ejemplo
python manage.py loaddata fixtures/sample_data.json

echo "Proyecto configurado correctamente!"
EOF

chmod +x scripts/setup_project.sh

# =========================================
# FINALIZACIÓN
# =========================================
echo ""
echo "✅ Migración completada!"
echo ""
echo "Próximos pasos:"
echo "1. Revisar la nueva estructura"
echo "2. Ejecutar: source venv_lti_recommender/bin/activate"
echo "3. Ejecutar: pip install -r requirements.txt"
echo "4. Ejecutar: python manage.py makemigrations"
echo "5. Ejecutar: python manage.py migrate"
echo ""