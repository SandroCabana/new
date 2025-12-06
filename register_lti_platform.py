#!/usr/bin/env python
"""Script para registrar la plataforma Moodle en PyLTI1p3"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lti_recommender_project.settings')
django.setup()

from pylti1p3.contrib.django.lti1p3_tool_config.models import LtiTool, LtiToolKey
from django.conf import settings
import json

print("="*60)
print(" REGISTRO DE PLATAFORMA MOODLE LTI 1.3")
print("="*60)

# Leer las claves públicas
with open(settings.LTI_TOOL_CONFIG['PUBLIC_KEY_FILE'], 'r') as f:
    public_key = f.read()

with open(settings.LTI_TOOL_CONFIG['PRIVATE_KEY_FILE'], 'r') as f:
    private_key = f.read()

# Datos de la plataforma Moodle
issuer = "http://localhost/stable_main"
client_id = settings.LTI_TOOL_CONFIG['CLIENT_ID']
auth_login_url = settings.LTI_TOOL_CONFIG['MOODLE_AUTH_URL']
auth_token_url = settings.LTI_TOOL_CONFIG['MOODLE_TOKEN_URL']
auth_audience = None  # Moodle suele no requerirlo
key_set_url = settings.LTI_TOOL_CONFIG['MOODLE_JWKS_URL']

# Verificar si ya existe
existing_tool = LtiTool.objects.filter(
    issuer=issuer,
    client_id=client_id
).first()

if existing_tool:
    print(f"\n⚠ Ya existe una herramienta registrada para:")
    print(f"   Issuer: {issuer}")
    print(f"   Client ID: {client_id}")
    print(f"\n✓ Eliminando la configuración existente...")
    existing_tool.delete()
    print("✓ Configuración anterior eliminada")

# PASO 1: Crear la clave de la herramienta PRIMERO
print(f"\n[1/2] Registrando par de claves RSA...")
lti_tool_key = LtiToolKey.objects.create(
    name=f"{settings.LTI_TOOL_CONFIG['TOOL_NAME']} - Key",
    private_key=private_key,
    public_key=public_key,
)
print("✓ Claves RSA registradas")

# PASO 2: Crear la herramienta LTI con la clave
print(f"\n[2/2] Registrando plataforma Moodle...")
print(f"  Issuer: {issuer}")
print(f"  Client ID: {client_id}")

lti_tool = LtiTool.objects.create(
    title="Moodle LTI Platform",
    issuer=issuer,
    client_id=client_id,
    use_by_default=True,
    auth_login_url=auth_login_url,
    auth_token_url=auth_token_url,
    auth_audience=auth_audience,
    key_set_url=key_set_url,
    key_set=None,  # Moodle proporciona JWKS via URL
    deployment_ids=json.dumps(["1"]),  # Deployment ID por defecto
    tool_key=lti_tool_key,  # Asociar la clave directamente
)

print("✓ Herramienta LTI creada con clave asociada")

print("\n" + "="*60)
print(" CONFIGURACIÓN COMPLETADA EXITOSAMENTE")
print("="*60)

print(f"\n📋 Resumen de la configuración:")
print(f"   Herramienta: {lti_tool.title}")
print(f"   Issuer: {lti_tool.issuer}")
print(f"   Client ID: {lti_tool.client_id}")
print(f"   Clave: {lti_tool_key.name}")
print(f"\n✅ Ahora puedes lanzar la herramienta desde Moodle")
print(f"\n💡 URLs de tu herramienta para configurar en Moodle:")
print(f"   Login URL: {settings.LTI_TOOL_CONFIG['AUTH_LOGIN_URL']}")
print(f"   Redirect URL: {settings.LTI_TOOL_CONFIG['LAUNCH_URL']}")
print(f"   JWKS URL: {settings.LTI_TOOL_CONFIG['JWKS_URL']}")
