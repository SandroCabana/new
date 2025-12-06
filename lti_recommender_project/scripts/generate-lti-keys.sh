#!/bin/bash
# Script para generar claves RSA para LTI 1.3 si no existen

set -e

KEY_DIR="${LTI_KEY_DIR:-/app/keys}"
PRIVATE_KEY="${KEY_DIR}/lti_private_key.pem"
PUBLIC_KEY="${KEY_DIR}/lti_public_key.pem"

echo "🔑 Checking LTI RSA keys..."

# Crear directorio si no existe
mkdir -p "$KEY_DIR"

# Verificar si las claves ya existen
if [ -f "$PRIVATE_KEY" ] && [ -f "$PUBLIC_KEY" ]; then
    echo "✅ LTI keys already exist in $KEY_DIR"
    echo "   Private key: $PRIVATE_KEY"
    echo "   Public key: $PUBLIC_KEY"
    exit 0
fi

echo "🔐 Generating new RSA key pair for LTI..."

# Generar clave privada (2048 bits)
openssl genrsa -out "$PRIVATE_KEY" 2048

# Extraer clave pública de la privada
openssl rsa -in "$PRIVATE_KEY" -pubout -out "$PUBLIC_KEY"

# Establecer permisos restrictivos
chmod 600 "$PRIVATE_KEY"
chmod 644 "$PUBLIC_KEY"

echo "✅ LTI RSA keys generated successfully!"
echo "   Private key: $PRIVATE_KEY"
echo "   Public key: $PUBLIC_KEY"
echo ""
echo "⚠️  IMPORTANT: Keep the private key secure!"
echo "   You can now register this tool with your LMS using the public key."
