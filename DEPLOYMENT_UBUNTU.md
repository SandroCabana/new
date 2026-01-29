# 🚀 Guía de Deployment en Ubuntu Server

Guía paso a paso para desplegar el sistema LTI Recommender en un servidor Ubuntu remoto.

---

## 📋 Pre-requisitos

### Servidor Ubuntu
- Ubuntu 20.04 LTS o superior
- Mínimo 2GB RAM, 2 vCPU (recomendado: 4GB RAM para ML)
- Puerto 80 y 443 abiertos
- Acceso SSH

### Dominio (Opcional pero recomendado)
- Dominio apuntando a la IP del servidor
- Certificado SSL (o usar Let's Encrypt)

---

## 🔧 Paso 1: Preparar el Servidor

### 1.1 Conectar al servidor
```bash
ssh usuario@IP_DEL_SERVIDOR
```

### 1.2 Actualizar el sistema
```bash
sudo apt update && sudo apt upgrade -y
```

### 1.3 Instalar dependencias básicas
```bash
sudo apt install -y curl git wget nano ufw
```

### 1.4 Configurar firewall
```bash
sudo ufw allow OpenSSH
sudo ufw allow http
sudo ufw allow https
sudo ufw enable
```

---

## 🐳 Paso 2: Instalar Docker

### 2.1 Instalar Docker
```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
```

### 2.2 Instalar Docker Compose
```bash
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

### 2.3 Verificar instalación
```bash
# Cerrar sesión y volver a entrar para aplicar grupo docker
exit
ssh usuario@IP_DEL_SERVIDOR

docker --version
docker-compose --version
```

---

## 📦 Paso 3: Clonar el Proyecto

### 3.1 Crear directorio de aplicación
```bash
mkdir -p ~/lti_recommender
cd ~/lti_recommender
```

### 3.2 Clonar repositorio
```bash
git clone https://github.com/TU_USUARIO/lti_moodle_recomender.git .
# O transferir archivos con scp:
# scp -r ./lti_recommender_project usuario@IP:/home/usuario/lti_recommender/
```

### 3.3 Navegar al proyecto Django
```bash
cd lti_recommender_project
```

---

## ⚙️ Paso 4: Configurar Variables de Entorno

### 4.1 Copiar archivo de ejemplo
```bash
cp .env.production .env
```

### 4.2 Generar SECRET_KEY
```bash
python3 -c 'import secrets; print(secrets.token_urlsafe(50))'
# Copiar el resultado
```

### 4.3 Editar archivo .env
```bash
nano .env
```

**Variables críticas a modificar:**
```env
# Seguridad - OBLIGATORIO cambiar
SECRET_KEY=tu-clave-secreta-generada-arriba
DJANGO_SUPERUSER_PASSWORD=contraseña-segura-admin

# Dominio - Cambiar por tu IP o dominio
ALLOWED_HOSTS=tu-dominio.com,www.tu-dominio.com,IP_SERVIDOR

# Base de datos
DB_PASSWORD=contraseña-segura-postgres

# URLs LTI - Cambiar IP/dominio
LTI_JWKS_URL=https://tu-dominio.com/lti/jwks/
LTI_AUTH_LOGIN_URL=https://tu-dominio.com/lti/login/
LTI_LAUNCH_URL=https://tu-dominio.com/lti/launch/

# Orígenes CSRF - URLs de tu Moodle
CSRF_TRUSTED_ORIGINS=https://tu-dominio.com,https://tu-moodle.edu
```

Guardar: `Ctrl+O`, `Enter`, `Ctrl+X`

---

## 📁 Paso 5: Crear Directorios

```bash
mkdir -p logs keys nginx/ssl
chmod 755 scripts/*.sh
```

---

## 🏗️ Paso 6: Construir y Ejecutar

### 6.1 Construir imágenes Docker
```bash
docker-compose build
```
⏱️ *Esto puede tomar 5-15 minutos la primera vez.*

### 6.2 Iniciar servicios
```bash
docker-compose up -d
```

### 6.3 Verificar estado
```bash
docker-compose ps
```

Deberías ver algo como:
```
NAME                    STATUS              
lti_recommender_db      Up (healthy)        
lti_recommender_redis   Up (healthy)        
lti_recommender_web     Up (healthy)        
lti_recommender_nginx   Up (healthy)        
```

---

## 🔐 Paso 7: Configurar SSL (Let's Encrypt)

### 7.1 Instalar Certbot
```bash
sudo apt install -y certbot python3-certbot-nginx
```

### 7.2 Obtener certificado
```bash
sudo certbot --nginx -d tu-dominio.com -d www.tu-dominio.com
```

### 7.3 Renovación automática
```bash
sudo certbot renew --dry-run
```

---

## ✅ Paso 8: Verificar Deployment

### 8.1 Probar endpoints
```bash
# Admin
curl -I http://localhost/admin/

# JWKS
curl http://localhost/lti/jwks/

# Auth login (nuevo)
curl -X POST http://localhost/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"tu-contraseña"}'
```

### 8.2 Ver logs
```bash
# Todos los servicios
docker-compose logs -f

# Solo aplicación web
docker-compose logs -f web
```

### 8.3 Obtener clave pública LTI
```bash
docker-compose exec web cat /app/keys/lti_public_key.pem
```

---

## 🔗 Paso 9: Configurar en Moodle

1. Ir a **Administración del sitio** → **Plugins** → **Herramientas externas**

2. **Añadir herramienta externa** con estos valores:

| Campo | Valor |
|-------|-------|
| Nombre | Sistema de Recomendación EPAI |
| URL herramienta | `https://tu-dominio.com/lti/launch/` |
| URL de inicio de sesión | `https://tu-dominio.com/lti/login/` |
| URL de conjunto de claves públicas | `https://tu-dominio.com/lti/jwks/` |
| Versión LTI | 1.3 |

3. Copiar el **Client ID** generado y actualizar `.env`:
```bash
nano .env
# Actualizar: LTI_CLIENT_ID=el-client-id-de-moodle
docker-compose restart web
```

---

## 🔄 Comandos Útiles

### Reiniciar servicios
```bash
docker-compose restart
```

### Actualizar código
```bash
git pull origin main
docker-compose build
docker-compose up -d
```

### Acceder a Django shell
```bash
docker-compose exec web python manage.py shell
```

### Crear migraciones
```bash
docker-compose exec web python manage.py makemigrations
docker-compose exec web python manage.py migrate
```

### Limpiar todo y reiniciar
```bash
docker-compose down -v
docker-compose up -d --build
```

---

## 🐛 Troubleshooting

### Error: "Database connection failed"
```bash
# Verificar que PostgreSQL esté corriendo
docker-compose logs db
# Revisar credenciales en .env
```

### Error: "Permission denied"
```bash
sudo chown -R $USER:$USER ~/lti_recommender
chmod +x scripts/*.sh
```

### Error: "Port 80 already in use"
```bash
sudo lsof -i :80
sudo systemctl stop apache2  # Si Apache está corriendo
```

### Ver uso de recursos
```bash
docker stats
```

---

## 📊 Monitoreo

### Verificar salud de contenedores
```bash
docker-compose ps
```

### Espacio en disco
```bash
df -h
docker system df
```

### Limpieza de Docker
```bash
docker system prune -a  # ⚠️ Elimina todo lo no usado
```
