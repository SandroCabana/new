#!/usr/bin/env python3
"""Script para arreglar variables Django rotas en el template"""

import re

template_path = "/home/molker/new/lti_recommender_project/apps/lti_integration/templates/lti_integration/recommendations.html"

# Leer el archivo
with open(template_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Arreglar todas las variables rotas que tienen saltos de línea y espacios
fixes = [
    (r'\{\{\s+user_name\s+\}\}', '{{ user_name }}'),
    (r'\{\{\s+user_email\s+\}\}', '{{ user_email }}'),
    (r'\{\{\s+role\|prettify_role\s+\}\}', '{{ role|prettify_role }}'),
    (r'\{\{\s+course_title\s+\}\}', '{{ course_title }}'),
    (r'\{\{\s+activity_title\s+\}\}', '{{ activity_title }}'),
    (r'\{\{\s+platform_name\s+\}\}', '{{ platform_name }}'),
]

# Aplicar correcciones
for pattern, replacement in fixes:
    content = re.sub(pattern, replacement, content, flags=re.MULTILINE | re.DOTALL)

# Escribir el archivo corregido
with open(template_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("✓ Template corregido exitosamente")

# Verificar que no queden variables rotas
broken_vars = re.findall(r'\{\{\s+\w+', content)
if broken_vars:
    print(f"⚠ Advertencia: Aún hay {len(broken_vars)} variables con formato sospechoso")
else:
    print("✓ No se encontraron variables con sintaxis incorrecta")
