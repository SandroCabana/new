#!/bin/bash
# ==============================================================================
# AWS Deployment Script para LTI Recommender
# ==============================================================================
# Este script automatiza el deployment en la instancia EC2

set -e  # Exit on error

# ==============================================================================
# Configuración
# ==============================================================================
EC2_HOST="18.219.4.185"
EC2_USER="ubuntu"
SSH_KEY_PATH="${SSH_KEY_PATH:-~/.ssh/aws-key.pem}"
APP_DIR="/home/ubuntu/lti_recommender/lti_recommender_project"
REPO_URL="${REPO_URL:-}"  # Definir en .env o pasar como argumento

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# ==============================================================================
# Funciones
# ==============================================================================

print_header() {
    echo -e "${GREEN}================================${NC}"
    echo -e "${GREEN}$1${NC}"
    echo -e "${GREEN}================================${NC}"
}

print_info() {
    echo -e "${YELLOW}➜${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

# Ejecutar comando en EC2
run_ssh() {
    ssh -i "$SSH_KEY_PATH" -o StrictHostKeyChecking=no "${EC2_USER}@${EC2_HOST}" "$@"
}

# ==============================================================================
# Validaciones Pre-Deploy
# ==============================================================================

print_header "Validando Pre-requisitos"

# Verificar SSH key
if [ ! -f "$SSH_KEY_PATH" ]; then
    print_error "SSH key not found at: $SSH_KEY_PATH"
    print_info "Set SSH_KEY_PATH environment variable or place key at ~/.ssh/aws-key.pem"
    exit 1
fi
print_success "SSH key found"

# Verificar conexión SSH
print_info "Testing SSH connection to EC2..."
if run_ssh "echo 'Connected'" > /dev/null 2>&1; then
    print_success "SSH connection successful"
else
    print_error "Cannot connect to EC2 instance"
    print_info "Check your SSH key permissions: chmod 400 $SSH_KEY_PATH"
    exit 1
fi

# ==============================================================================
# Deployment
# ==============================================================================

print_header "Starting Deployment"

# Paso 1: Instalar Docker si no está instalado
print_info "Checking Docker installation..."
if ! run_ssh "command -v docker" > /dev/null 2>&1; then
    print_info "Installing Docker..."
    run_ssh "curl -fsSL https://get.docker.com -o get-docker.sh && sudo sh get-docker.sh"
    run_ssh "sudo usermod -aG docker \$USER"
    print_success "Docker installed"
else
    print_success "Docker already installed"
fi

# Paso 2: Instalar Docker Compose si no está instalado
print_info "Checking Docker Compose installation..."
if ! run_ssh "command -v docker-compose" > /dev/null 2>&1; then
    print_info "Installing Docker Compose..."
    run_ssh 'sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose'
    run_ssh "sudo chmod +x /usr/local/bin/docker-compose"
    print_success "Docker Compose installed"
else
    print_success "Docker Compose already installed"
fi

# Paso 3: Clonar o actualizar repositorio
print_info "Setting up application code..."
if run_ssh "[ -d '$APP_DIR' ]"; then
    print_info "Updating existing repository..."
    run_ssh "cd $APP_DIR && git pull origin main"
    print_success "Repository updated"
else
    if [ -z "$REPO_URL" ]; then
        print_error "Repository not found on server and no REPO_URL provided"
        print_info "Please clone the repository manually or set REPO_URL environment variable"
        exit 1
    fi
    print_info "Cloning repository..."
    run_ssh "mkdir -p /home/ubuntu/lti_recommender"
    run_ssh "git clone $REPO_URL /home/ubuntu/lti_recommender"
    print_success "Repository cloned"
fi

# Paso 4: Verificar archivo .env
print_info "Checking .env file..."
if ! run_ssh "[ -f '$APP_DIR/.env' ]"; then
    print_error ".env file not found on server"
    print_info "Copying .env.production to .env..."
    run_ssh "cd $APP_DIR && cp .env.production .env"
    print_error "IMPORTANT: Edit .env file with your actual credentials!"
    print_info "Run: ssh -i $SSH_KEY_PATH ${EC2_USER}@${EC2_HOST} 'nano $APP_DIR/.env'"
    read -p "Press Enter after you've configured .env file..."
fi
print_success ".env file exists"

# Paso 5: Crear directorios necesarios
print_info "Creating required directories..."
run_ssh "cd $APP_DIR && mkdir -p logs keys nginx/ssl"
print_success "Directories created"

# Paso 6: Build de imágenes Docker
print_info "Building Docker images (this may take several minutes)..."
run_ssh "cd $APP_DIR && docker-compose build --no-cache"
print_success "Docker images built"

# Paso 7: Detener servicios antiguos si existen
print_info "Stopping old services..."
run_ssh "cd $APP_DIR && docker-compose down" || true
print_success "Old services stopped"

# Paso 8: Iniciar servicios
print_info "Starting services..."
run_ssh "cd $APP_DIR && docker-compose up -d"
print_success "Services started"

# Paso 9: Esperar que los servicios estén saludables
print_info "Waiting for services to be healthy (30 seconds)..."
sleep 30

# Paso 10: Verificar estado de servicios
print_info "Checking service status..."
run_ssh "cd $APP_DIR && docker-compose ps"

# Paso 11: Mostrar logs recientes
print_info "Recent logs from web service:"
run_ssh "cd $APP_DIR && docker-compose logs --tail=20 web"

# ==============================================================================
# Post-Deployment
# ==============================================================================

print_header "Deployment Complete!"

echo ""
print_success "Application deployed successfully!"
echo ""
echo "📌 Next Steps:"
echo ""
echo "1. Get LTI Public Key:"
echo "   ssh -i $SSH_KEY_PATH ${EC2_USER}@${EC2_HOST} 'docker-compose -f $APP_DIR/docker-compose.yml exec web cat /app/keys/lti_public_key.pem'"
echo ""
echo "2. Configure in Moodle:"
echo "   - Tool URL: https://${EC2_HOST}/lti/launch/"
echo "   - Login URL: https://${EC2_HOST}/lti/login/"
echo "   - JWKS URL: https://${EC2_HOST}/lti/jwks/"
echo ""
echo "3. Test endpoints:"
echo "   - Admin: http://${EC2_HOST}/admin/"
echo "   - JWKS: http://${EC2_HOST}/lti/jwks/"
echo "   - Health: http://${EC2_HOST}/nginx-health"
echo ""
echo "4. View logs:"
echo "   ssh -i $SSH_KEY_PATH ${EC2_USER}@${EC2_HOST} 'cd $APP_DIR && docker-compose logs -f'"
echo ""
print_info "For troubleshooting, see: docs/AWS_DEPLOYMENT.md"
