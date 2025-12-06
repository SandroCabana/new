#!/bin/bash
# Script para reiniciar el servidor Django y probar los filtros de template

echo "======================================================"
echo "REINICIO DEL SERVIDOR DJANGO"
echo "======================================================"
echo ""

# Detener cualquier proceso de Django corriendo
echo "1. Deteniendo procesos Django existentes..."
pkill -f "manage.py runserver" 2>/dev/null || echo "   No hay procesos Django corriendo"
sleep 2

# Verificar que la estructura de templatetags es correcta
echo ""
echo "2. Verificando estructura de archivos..."
if [ -f "apps/lti_integration/templatetags/__init__.py" ]; then
    echo "   ✓ __init__.py existe"
else
    echo "   ✗ __init__.py NO EXISTE"
fi

if [ -f "apps/lti_integration/templatetags/lti_filters.py" ]; then
    echo "   ✓ lti_filters.py existe"
else
    echo "   ✗ lti_filters.py NO EXISTE"
fi

# Compilar los archivos Python para verificar sintaxis
echo ""
echo "3. Verificando sintaxis de Python..."
python3 -m py_compile apps/lti_integration/templatetags/lti_filters.py
if [ $? -eq 0 ]; then
    echo "   ✓ Sintaxis correcta"
else
    echo "   ✗ ERROR de sintaxis"
    exit 1
fi

# Limpiar caché de Python
echo ""
echo "4. Limpiando caché de Python..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find . -type f -name "*.pyc" -delete 2>/dev/null
echo "   ✓ Caché limpiado"

# Iniciar el servidor Django
echo ""
echo "5. Iniciando servidor Django..."
echo "   Ejecuta el siguiente comando en una terminal:"
echo ""
echo "   cd /home/molker/new/lti_recommender_project"
echo "   python3 manage.py runserver"
echo ""
echo "======================================================"
echo "Después de que el servidor esté corriendo, prueba"
echo "acceder nuevamente desde Moodle para ver los cambios."
echo "======================================================"
