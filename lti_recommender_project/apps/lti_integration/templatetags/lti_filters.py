"""
Filtros personalizados para templates de LTI Integration
"""
from django import template

register = template.Library()


@register.filter(name='extract_role_label')
def extract_role_label(role_url):
    """
    Extrae el label legible de una URL de rol LTI.
    
    Ejemplo:
        Input: "http://purl.imsglobal.org/vocab/lis/v2/institution/person#Administrator"
        Output: "Administrator"
    
    Args:
        role_url (str): URL completa del rol LTI
        
    Returns:
        str: Label del rol extraído
    """
    if not role_url or not isinstance(role_url, str):
        return role_url
    
    # Extraer la parte después del # (fragment identifier)
    if '#' in role_url:
        return role_url.split('#')[-1]
    
    # Si no hay #, intentar obtener la última parte de la URL
    if '/' in role_url:
        return role_url.split('/')[-1]
    
    # Si no se puede parsear, devolver el valor original
    return role_url


# Mapeo de roles LTI a nombres más amigables (opcional)
ROLE_LABELS = {
    'Administrator': '👤 Administrador',
    'Instructor': '👨‍🏫 Instructor',
    'Learner': '👨‍🎓 Estudiante',
    'Student': '👨‍🎓 Estudiante',
    'TeachingAssistant': '👨‍🏫 Asistente',
    'ContentDeveloper': '✍️ Desarrollador de Contenido',
    'Mentor': '🎓 Mentor',
}


@register.filter(name='prettify_role')
def prettify_role(role_url):
    """
    Convierte una URL de rol LTI en un nombre amigable con icono.
    
    Ejemplo:
        Input: "http://purl.imsglobal.org/vocab/lis/v2/institution/person#Administrator"
        Output: "👤 Administrador"
    
    Args:
        role_url (str): URL completa del rol LTI
        
    Returns:
        str: Nombre amigable del rol con icono
    """
    label = extract_role_label(role_url)
    return ROLE_LABELS.get(label, label)


@register.filter(name='percentage')
def percentage(value):
    """
    Convierte un valor decimal (0.0 a 1.0) a formato porcentaje entero (0 a 100).
    Evita que Django redondee 0.65 a '1'.
    """
    try:
        return int(round(float(value) * 100))
    except (ValueError, TypeError):
        return 0
