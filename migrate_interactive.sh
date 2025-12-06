#!/bin/bash

# Script Interactivo de Migración - Sistema de Recomendación IA
# Autor: Sandro Cabana
# Fecha: 2025

set -e  # Detener si hay errores

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Función para imprimir con color
print_step() {
    echo -e "${BLUE}===================================${NC}"
    echo -e "${GREEN}$1${NC}"
    echo -e "${BLUE}===================================${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

# Función para pedir confirmación
ask_confirmation() {
    while true; do
        read -p "$(echo -e ${YELLOW}$1 [y/n]: ${NC})" yn
        case $yn in
            [Yy]* ) return 0;;
            [Nn]* ) return 1;;
            * ) echo "Por favor responde 'y' (sí) o 'n' (no).";;
        esac
    done
}

# =========================================
# INICIO
# =========================================
clear
echo -e "${BLUE}"
cat << "EOF"
╔═══════════════════════════════════════════╗
║   MIGRACIÓN DE PROYECTO DE TESIS         ║
║   Sistema de Recomendación con IA        ║
╚═══════════════════════════════════════════╝
EOF
echo -e "${NC}"

# =========================================
# VERIFICACIONES INICIALES
# =========================================
print_step "VERIFICACIONES INICIALES"

# Verificar que estamos en el directorio correcto
echo "Directorio actual: $(pwd)"
echo ""
echo "Contenido del directorio:"
ls -la
echo ""

if ! ask_confirmation "¿Estás en el directorio del proyecto 'new'?"; then
    print_error "Por favor, navega al directorio correcto con 'cd' y vuelve a ejecutar el script."
    exit 1
fi

# Verificar que existe el proyecto Django
if [ ! -f "manage.py" ]; then
    print_error "No se encontró manage.py. ¿Estás en el directorio correcto?"
    exit 1
fi

print_success "Verificación exitosa"

# =========================================
# PASO 1: BACKUP
# =========================================
print_step "PASO 1: CREANDO BACKUP"

BACKUP_NAME="new_backup_$(date +%Y%m%d_%H%M%S)"
print_warning "Se creará un backup en: ../$BACKUP_NAME"

if ask_confirmation "¿Deseas crear un backup del proyecto actual?"; then
    cp -r . ../$BACKUP_NAME
    if [ $? -eq 0 ]; then
        print_success "Backup creado exitosamente en ../$BACKUP_NAME"
    else
        print_error "Error al crear backup. Abortando."
        exit 1
    fi
else
    print_warning "Continuando sin backup. ¡Esto es riesgoso!"
    if ! ask_confirmation "¿Estás seguro de continuar sin backup?"; then
        print_error "Operación cancelada por el usuario."
        exit 1
    fi
fi

# =========================================
# PASO 2: CREAR NUEVA ESTRUCTURA
# =========================================
print_step "PASO 2: CREANDO NUEVA ESTRUCTURA"

print_warning "Se crearán los siguientes directorios:"
echo "  - lti_recommender_project/config"
echo "  - lti_recommender_project/apps"
echo "  - lti_recommender_project/ml"
echo "  - lti_recommender_project/scraper"
echo "  - lti_recommender_project/api"
echo "  - lti_recommender_project/static"
echo "  - lti_recommender_project/media"
echo "  - lti_recommender_project/templates"
echo "  - lti_recommender_project/tests"
echo "  - lti_recommender_project/docs"
echo "  - lti_recommender_project/scripts"
echo "  - lti_recommender_project/deployment"

if ask_confirmation "¿Deseas crear la estructura de directorios?"; then
    # Crear directorios principales
    mkdir -p lti_recommender_project/{config,apps,ml,scraper,api,static,media,templates,tests,docs,scripts,deployment}
    
    # Crear subdirectorios de apps
    mkdir -p lti_recommender_project/apps/{core,lti_integration,users,interactions,resources,recommendations,analytics}
    
    # Crear estructura ML
    mkdir -p lti_recommender_project/ml/{data_preprocessing,models,training,saved_models,notebooks}
    
    # Crear __init__.py en todos los paquetes de apps
    for app in core lti_integration users interactions resources recommendations analytics; do
        touch lti_recommender_project/apps/$app/__init__.py
        touch lti_recommender_project/apps/$app/models.py
        touch lti_recommender_project/apps/$app/views.py
        touch lti_recommender_project/apps/$app/urls.py
        touch lti_recommender_project/apps/$app/serializers.py
        touch lti_recommender_project/apps/$app/admin.py
        touch lti_recommender_project/apps/$app/tests.py
    done
    
    # Crear __init__.py en ml
    touch lti_recommender_project/ml/__init__.py
    touch lti_recommender_project/ml/data_preprocessing/__init__.py
    touch lti_recommender_project/ml/models/__init__.py
    touch lti_recommender_project/ml/training/__init__.py
    
    # Crear .gitkeep en directorios vacíos
    touch lti_recommender_project/ml/saved_models/.gitkeep
    touch lti_recommender_project/media/.gitkeep
    touch lti_recommender_project/static/.gitkeep
    
    print_success "Estructura de directorios creada"
    
    # Mostrar estructura
    if command -v tree &> /dev/null; then
        tree -L 3 lti_recommender_project/
    else
        find lti_recommender_project/ -type d | head -20
    fi
fi

# =========================================
# PASO 3: MIGRAR CÓDIGO EXISTENTE
# =========================================
print_step "PASO 3: MIGRANDO CÓDIGO EXISTENTE"

print_warning "Se moverá el código existente a la nueva estructura"

if ask_confirmation "¿Deseas migrar el código existente?"; then
    
    # Migrar configuración de Django
    if [ -d "lti_recommender_project" ] && [ -f "lti_recommender_project/settings.py" ]; then
        mkdir -p lti_recommender_project/config/settings
        cp lti_recommender_project/settings.py lti_recommender_project/config/settings/base.py
        cp lti_recommender_project/urls.py lti_recommender_project/config/
        cp lti_recommender_project/wsgi.py lti_recommender_project/config/
        cp lti_recommender_project/asgi.py lti_recommender_project/config/
        print_success "Configuración Django migrada"
    fi
    
    # Migrar app de recomendaciones
    if [ -d "recommender_app" ]; then
        cp -r recommender_app/* lti_recommender_project/apps/lti_integration/
        print_success "App de recomendaciones migrada"
    fi
    
    # Migrar scraper
    if [ -d "scraper_project" ]; then
        cp -r scraper_project/* lti_recommender_project/scraper/
        print_success "Scraper migrado"
    fi
    
    # Copiar archivos clave
    [ -f "manage.py" ] && cp manage.py lti_recommender_project/
    [ -f "db.sqlite3" ] && cp db.sqlite3 lti_recommender_project/
    [ -f "requirements.txt" ] && cp requirements.txt lti_recommender_project/requirements_old.txt
    [ -f "lti_private_key.pem" ] && cp lti_private_key.pem lti_recommender_project/
    [ -f "lti_public_key.pem" ] && cp lti_public_key.pem lti_recommender_project/
fi

# =========================================
# PASO 4: CREAR ARCHIVOS DE CONFIGURACIÓN
# =========================================
print_step "PASO 4: CREANDO ARCHIVOS DE CONFIGURACIÓN"

if ask_confirmation "¿Deseas crear los archivos de configuración (.env, .gitignore, etc.)?"; then
    
    # Crear .gitignore
    cat > lti_recommender_project/.gitignore << 'EOF'
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
venv/
venv_lti_recommender/
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
!/scraper/data/.gitkeep
*.json
EOF
    print_success ".gitignore creado"
    
    # Crear .env.example
    cat > lti_recommender_project/.env.example << 'EOF'
# Django
DEBUG=True
SECRET_KEY=your-secret-key-here
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DATABASE_URL=sqlite:///db.sqlite3

# LTI
LTI_ISS=https://your-moodle-instance.com
LTI_CLIENT_ID=your-client-id
LTI_DEPLOYMENT_ID=your-deployment-id

# Redis (opcional)
REDIS_URL=redis://localhost:6379/0

# ML Models
ML_MODEL_PATH=ml/saved_models
EOF
    print_success ".env.example creado"
    
    # Crear README.md
    cat > lti_recommender_project/README.md << 'EOF'
# Sistema de Recomendación de Temas con IA para E-Learning

Sistema de recomendación basado en inteligencia artificial para plataformas Moodle.

## Requisitos
- Python 3.10+
- Django 4.2+
- PostgreSQL (opcional, SQLite por defecto)

## Instalación

1. Crear entorno virtual:
```bash
python3 -m venv venv
source venv/bin/activate
```

2. Instalar dependencias:
```bash
pip install -r requirements.txt
```

3. Configurar variables de entorno:
```bash
cp .env.example .env
# Editar .env con tus valores
```

4. Ejecutar migraciones:
```bash
python manage.py migrate
```

5. Crear superusuario:
```bash
python manage.py createsuperuser
```

6. Ejecutar servidor:
```bash
python manage.py runserver
```

## Estructura del Proyecto

Ver documentación en `docs/`

## Autor
Sandro Jesus Cabana Heredia
EOF
    print_success "README.md creado"
fi

# =========================================
# PASO 5: CREAR REQUIREMENTS.TXT
# =========================================
print_step "PASO 5: CREANDO REQUIREMENTS.TXT"

if ask_confirmation "¿Deseas crear un nuevo requirements.txt optimizado?"; then
    cat > lti_recommender_project/requirements.txt << 'EOF'
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

# Scraping
scrapy==2.11.0
beautifulsoup4==4.12.3

# Utils
python-dotenv==1.0.0
requests==2.31.0
Pillow==10.2.0

# Development
ipython==8.19.0

# Production
gunicorn==21.2.0
whitenoise==6.6.0
EOF
    print_success "requirements.txt creado"
fi

# =========================================
# FINALIZACIÓN
# =========================================
print_step "MIGRACIÓN COMPLETADA"

echo ""
print_success "¡Migración completada exitosamente!"
echo ""
echo -e "${YELLOW}Próximos pasos:${NC}"
echo "1. cd lti_recommender_project"
echo "2. python3 -m venv venv"
echo "3. source venv/bin/activate"
echo "4. pip install -r requirements.txt"
echo "5. python manage.py makemigrations"
echo "6. python manage.py migrate"
echo "7. python manage.py createsuperuser"
echo "8. python manage.py runserver"
echo ""
print_warning "Recuerda revisar y ajustar los archivos de configuración según tus necesidades."
echo ""

# Preguntar si quiere ver la estructura
if ask_confirmation "¿Deseas ver la estructura final del proyecto?"; then
    if command -v tree &> /dev/null; then
        tree -L 3 lti_recommender_project/
    else
        find lti_recommender_project/ -type d
    fi
fi

print_success "Script finalizado. ¡Buena suerte con tu tesis!"