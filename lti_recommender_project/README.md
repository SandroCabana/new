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
