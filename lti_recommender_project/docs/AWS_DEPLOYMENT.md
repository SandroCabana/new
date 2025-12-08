# 🚀 Guía de Deployment en AWS

Guía completa para desplegar la aplicación LTI Recommender en AWS usando EC2 + RDS PostgreSQL.

---

## 📋 Infraestructura Actual

### AWS Resources Configurados

| Recurso | Detalles | Región |
|---------|----------|--------|
| **EC2 Instance** | `i-04d30b9e000fe2c8b` (ServerPruebas) | us-east-2 |
| Tipo | t3.micro | - |
| IP Pública | `18.219.4.185` | - |
| DNS Público | `ec2-18-219-4-185.us-east-2.compute.amazonaws.com` | - |
| **RDS PostgreSQL** | `database-1` | us-east-2c |
| Clase | db.t4g.micro | - |
| Motor | PostgreSQL | - |
| Endpoint | `database-1.cf2ogyqeql4q.us-east-2.rds.amazonaws.com:5432` | - |
| VPC | `vpc-0fda0d453f5503da7` | - |
| Security Group | `rds-ec2-1` (sg-06bd4a1cce4c473ed) | - |

---

## 🔐 Pre-requisitos

### 1. Acceso SSH a EC2

```bash
# Conectarse a la instancia EC2
ssh -i /path/to/your-key.pem ubuntu@18.219.4.185
```

### 2. Verificar Security Groups

Asegurarse de que los Security Groups permitan:

#### EC2 Security Group
- **Inbound**:
  - Puerto 22 (SSH) desde tu IP
  - Puerto 80 (HTTP) desde 0.0.0.0/0
  - Puerto 443 (HTTPS) desde 0.0.0.0/0

#### RDS Security Group (`rds-ec2-1`)
- **Inbound**:
  - Puerto 5432 (PostgreSQL) desde el Security Group de EC2
  - ✅ **Ya configurado** según tu setup actual

---

## 🛠️ Instalación Inicial en EC2

### Paso 1: Instalar Docker y Docker Compose

```bash
# Actualizar sistema
sudo apt-get update
sudo apt-get upgrade -y

# Instalar Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Agregar usuario al grupo docker
sudo usermod -aG docker $USER

# Instalar Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Reiniciar sesión para aplicar cambios de grupo
exit
# Volver a conectarse por SSH
```

### Paso 2: Verificar Instalación

```bash
docker --version
docker-compose --version
```

---

## 📦 Deployment de la Aplicación

### Paso 1: Clonar Repositorio

```bash
cd ~
git clone <URL-DE-TU-REPOSITORIO> lti_recommender
cd lti_recommender/lti_recommender_project
```

### Paso 2: Configurar Variables de Entorno

```bash
# Copiar archivo de producción
cp .env.production .env

# Editar variables críticas
nano .env
```

**Variables CRÍTICAS a actualizar:**

```bash
# 1. Secret Key - Generar una nueva
SECRET_KEY=tu-secret-key-aqui

# 2. Contraseña de RDS (la que configuraste al crear RDS)
DB_PASSWORD=tu-password-de-rds-aqui

# 3. Contraseña del admin de Django
DJANGO_SUPERUSER_PASSWORD=password-seguro-aqui

# 4. Client ID de Moodle (obtener después de registrar la herramienta)
LTI_CLIENT_ID=client-id-from-moodle

# 5. URLs de Moodle
MOODLE_AUTH_URL=https://tu-moodle.com/mod/lti/auth.php
MOODLE_TOKEN_URL=https://tu-moodle.com/mod/lti/token.php
MOODLE_JWKS_URL=https://tu-moodle.com/mod/lti/certs.php

# 6. Trusted Origins (agregar URL de Moodle)
CSRF_TRUSTED_ORIGINS=https://18.219.4.185,https://tu-moodle.com
```

#### Generar SECRET_KEY

```bash
python3 -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
```

### Paso 3: Crear Directorios Necesarios

```bash
mkdir -p logs keys
```

### Paso 4: Iniciar Servicios con Docker Compose

```bash
# Construir imágenes
docker-compose build

# Iniciar servicios en background
docker-compose up -d

# Ver status
docker-compose ps
```

Deberías ver todos los servicios como `healthy`:
```
NAME                      STATUS
lti_recommender_db        Up (healthy)
lti_recommender_nginx     Up (healthy)
lti_recommender_redis     Up (healthy)
lti_recommender_web       Up (healthy)
```

### Paso 5: Verificar Logs

```bash
# Ver logs de todos los servicios
docker-compose logs -f

# Ver logs específicos
docker-compose logs -f web
docker-compose logs -f nginx
docker-compose logs -f db
```

---

## 🔑 Obtener Clave Pública LTI

```bash
# Obtener la clave pública para configurar en Moodle
docker-compose exec web cat /app/keys/lti_public_key.pem
```

**Copiar TODO el contenido** (incluyendo `-----BEGIN PUBLIC KEY-----` y `-----END PUBLIC KEY-----`)

---

## 🎓 Configurar en Moodle

### 1. Registrar External Tool

1. Ir a: **Site Administration** → **Plugins** → **Activity modules** → **External tool** → **Manage tools**
2. Click en **Configure a tool manually**
3. Llenar formulario:

| Campo | Valor |
|-------|-------|
| Tool name | `Sistema de Recomendación EPAI` |
| Tool URL | `https://18.219.4.185/lti/launch/` |
| LTI version | `LTI 1.3` |
| Public key type | `RSA key` |
| Public key | *Pegar la clave del paso anterior* |
| Initiate login URL | `https://18.219.4.185/lti/login/` |
| Redirection URI(s) | `https://18.219.4.185/lti/launch/` |

4. En la sección **Services**:
   - ✅ IMS LTI Names and Role Provisioning
   - ✅ IMS LTI Deep Linking

5. **Guardar cambios**

### 2. Copiar Client ID

Después de guardar, Moodle mostrará el **Client ID**. Copiarlo.

### 3. Actualizar .env con Client ID

```bash
nano .env
# Actualizar: LTI_CLIENT_ID=el-client-id-de-moodle
```

```bash
# Reiniciar servicios
docker-compose restart web
```

---

## ✅ Verificación

### 1. Verificar Endpoints

```bash
# Desde la EC2
curl http://localhost/admin/
curl http://localhost/lti/jwks/
curl http://localhost/nginx-health

# Desde tu navegador
http://18.219.4.185/admin/
http://18.219.4.185/lti/jwks/
```

### 2. Probar LTI desde Moodle

1. En un curso de Moodle, agregar actividad → **External tool**
2. Seleccionar tu herramienta registrada
3. Hacer click en la actividad
4. Debería lanzar la aplicación LTI correctamente

---

## 🔄 Actualizar la Aplicación

```bash
# Conectar a EC2
ssh -i /path/to/key.pem ubuntu@18.219.4.185

cd ~/lti_recommender/lti_recommender_project

# Pull latest changes
git pull origin main

# Rebuild y restart
docker-compose build
docker-compose up -d

# Ver logs
docker-compose logs -f web
```

---

## 💾 Backup de Base de Datos

### Backup Manual

```bash
# Backup de RDS (desde EC2)
docker-compose exec web python manage.py dumpdata > backup_$(date +%Y%m%d_%H%M%S).json
```

### Backup Automático

AWS RDS ya hace backups automáticos. Puedes configurar:

1. **Retention period**: 7-30 días
2. **Backup window**: Hora de menor tráfico
3. **Snapshots manuales**: Antes de cambios importantes

Para crear snapshot manual:
- AWS Console → RDS → database-1 → Actions → Take snapshot

---

## 🔒 Seguridad

### ✅ Checklist de Seguridad

- [x] PostgreSQL en RDS (no expuesto públicamente)
- [x] Puerto 8000 de Django no expuesto (solo interno vía Nginx)
- [x] Security Groups configurados correctamente
- [ ] **Pendiente**: Configurar SSL/TLS (Let's Encrypt)
- [ ] **Pendiente**: Cambiar `SECRET_KEY` de Django
- [ ] **Pendiente**: Cambiar contraseña de RDS
- [ ] **Pendiente**: Cambiar contraseña de admin Django
- [ ] **Pendiente**: Actualizar `ALLOWED_HOSTS` si tienes dominio

### Configurar SSL con Let's Encrypt

```bash
# Instalar certbot
sudo apt-get install certbot

# Detener Nginx temporalmente
docker-compose stop nginx

# Obtener certificado (reemplazar con tu dominio)
sudo certbot certonly --standalone -d tu-dominio.com

# Copiar certificados a proyecto
sudo cp /etc/letsencrypt/live/tu-dominio.com/fullchain.pem ~/lti_recommender/lti_recommender_project/nginx/ssl/cert.pem
sudo cp /etc/letsencrypt/live/tu-dominio.com/privkey.pem ~/lti_recommender/lti_recommender_project/nginx/ssl/key.pem
sudo chown $USER:$USER ~/lti_recommender/lti_recommender_project/nginx/ssl/*.pem

# Editar nginx/conf.d/default.conf para descomentar bloque HTTPS

# Reiniciar Nginx
docker-compose start nginx
```

---

## 📊 Monitoring

### Ver recursos del sistema

```bash
# CPU, memoria de contenedores
docker stats

# Logs en tiempo real
docker-compose logs -f

# Estado de servicios
docker-compose ps
```

### Acceder a container shell

```bash
# Django shell
docker-compose exec web python manage.py shell

# Bash en contenedor web
docker-compose exec web bash

# PostgreSQL (RDS - requiere credenciales)
psql -h database-1.cf2ogyqeql4q.us-east-2.rds.amazonaws.com -U postgres -d lti_recommender_db
```

---

## 🆘 Troubleshooting

### Base de datos no conecta

```bash
# Verificar que RDS esté accesible desde EC2
docker-compose exec web python manage.py dbshell

# Si falla, verificar Security Group de RDS permite conexión desde EC2
```

### Nginx no inicia

```bash
# Ver logs
docker-compose logs nginx

# Verificar configuración
docker-compose exec nginx nginx -t
```

### Puerto 80 ya está en uso

```bash
# Ver qué proceso usa puerto 80
sudo netstat -tlnp | grep :80

# Detener Apache u otro servidor si existe
sudo systemctl stop apache2
```

### Reiniciar todo

```bash
docker-compose down
docker-compose up -d
```

---

## 📈 Escalabilidad Futura

### Upgrade de instancia EC2
Ir a AWS Console → EC2 → Instance → Actions → Instance Settings → Change instance type

Recomendado para producción:
- **t3.small** o **t3.medium** (más RAM y CPU)
- Reiniciar instancia después del cambio

### Upgrade de RDS
Ir a AWS Console → RDS → database-1 → Modify

Recomendado para producción:
- **db.t4g.small** o superior
- Multi-AZ deployment para alta disponibilidad

---

## 🎯 Próximos Pasos

1. **Obtener dominio** (ej: `lti.tu-universidad.edu`)
2. **Configurar DNS** apuntando a `18.219.4.185`
3. **Instalar SSL** con Let's Encrypt
4. **Actualizar `.env`** con dominio real
5. **Monitoreo**: Configurar CloudWatch para alertas
6. **Backups**: Automatizar backups de aplicación

---

## 📞 Soporte

Para problemas o preguntas, revisar:
- [DOCKER_SETUP.md](./DOCKER_SETUP.md) - Documentación de Docker
- [API_DOCUMENTATION.md](../../API_DOCUMENTATION.md) - Documentación de APIs
- Logs: `docker-compose logs -f web`
