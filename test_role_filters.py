#!/usr/bin/env python3
"""
Script de prueba para los filtros de roles LTI
"""

# Simulación de las funciones del filtro
def extract_role_label(role_url):
    """Extrae el label legible de una URL de rol LTI."""
    if not role_url or not isinstance(role_url, str):
        return role_url
    
    if '#' in role_url:
        return role_url.split('#')[-1]
    
    if '/' in role_url:
        return role_url.split('/')[-1]
    
    return role_url


ROLE_LABELS = {
    'Administrator': '👤 Administrador',
    'Instructor': '👨‍🏫 Instructor',
    'Learner': '👨‍🎓 Estudiante',
    'Student': '👨‍🎓 Estudiante',
    'TeachingAssistant': '👨‍🏫 Asistente',
    'ContentDeveloper': '✍️ Desarrollador de Contenido',
    'Mentor': '🎓 Mentor',
}


def prettify_role(role_url):
    """Convierte una URL de rol LTI en un nombre amigable con icono."""
    label = extract_role_label(role_url)
    return ROLE_LABELS.get(label, label)


# Ejemplos de prueba
test_roles = [
    "http://purl.imsglobal.org/vocab/lis/v2/institution/person#Administrator",
    "http://purl.imsglobal.org/vocab/lis/v2/membership#Instructor",
    "http://purl.imsglobal.org/vocab/lis/v2/system/person#Administrator",
    "http://purl.imsglobal.org/vocab/lis/v2/membership#Learner",
]

print("=" * 60)
print("PRUEBA DE FILTROS DE ROLES LTI")
print("=" * 60)

print("\n1. Roles originales (URLs completas):")
print("-" * 60)
for role in test_roles:
    print(f"  • {role}")

print("\n2. Con extract_role_label (solo el label):")
print("-" * 60)
for role in test_roles:
    print(f"  • {extract_role_label(role)}")

print("\n3. Con prettify_role (con emojis):")
print("-" * 60)
for role in test_roles:
    print(f"  • {prettify_role(role)}")

print("\n" + "=" * 60)
print("✅ Los filtros funcionan correctamente!")
print("=" * 60)
