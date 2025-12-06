# 🐳 Docker Setup Guide - LTI Recommender Project

Complete guide for running the LTI Recommender system with Docker.

---

## 📋 Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Start](#quick-start)
3. [Environment Configuration](#environment-configuration)
4. [Build and Run](#build-and-run)
5 [Accessing the Application](#accessing-the-application)
6. [LTI Integration with Moodle](#lti-integration-with-moodle)
7. [Maintenance](#maintenance)
8. [Troubleshooting](#troubleshooting)
9. [Production Deployment](#production-deployment)

---

## Prerequisites

- **Docker:** Version 20.10+ ([Install Docker](https://docs.docker.com/get-docker/))
- **Docker Compose:** Version 2.0+ (usually included with Docker Desktop)
- **Minimum Resources:**
  - CPU: 2 cores
  - RAM: 4GB
  - Disk: 10GB free space

**Verify installation:**
```bash
docker --version
docker-compose --version
```

---

## Quick Start

### 1. Clone and Navigate

```bash
cd /home/molker/new/lti_recommender_project
```

### 2. Create Environment File

```bash
cp .env.production .env
```

### 3. Edit Environment Variables

```bash
nano .env  # or use your preferred editor
```

**Minimum required changes:**
- `SECRET_KEY` - Generate a new one
- `DB_PASSWORD` - Change from default
- `LTI_CLIENT_ID` - Get from Moodle
- `MOODLE_AUTH_URL`, `MOODLE_TOKEN_URL`, `MOODLE_JWKS_URL` - Update with your Moodle URL

### 4. Start Everything

```bash
docker-compose up -d
```

### 5. Check Status

```bash
docker-compose ps
```

All services should show `healthy` status.

---

## Environment Configuration

### Generate SECRET_KEY

```bash
python3 -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
```

Copy the output and paste it into `.env`:
```bash
SECRET_KEY=your-generated-key-here
```

### Critical Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `SECRET_KEY` | Django secret (MUST change!) | `django-insecure-xyz123...` |
| `DEBUG` | Debug mode (False in production) | `False` |
| `ALLOWED_HOSTS` | Comma-separated allowed domains | `example.com,www.example.com` |
| `DB_PASSWORD` | PostgreSQL password | `mySuperSecurePass123!` |
| `LTI_CLIENT_ID` | From Moodle LTI registration | `HzDcDuQZIXoITpL` |
| `MOODLE_AUTH_URL` | Moodle auth endpoint | `https://moodle.edu/mod/lti/auth.php` |

### LTI Keys

LTI RSA keys are **generated automatically** on first run. They will be stored in `./keys/` directory.

To regenerate keys:
```bash
rm -rf keys/
docker-compose restart web
```

---

## Build and Run

### Development

```bash
# Build images
docker-compose build

# Start services in foreground (see logs)
docker-compose up

# Start in background (detached)
docker-compose up -d

# View logs
docker-compose logs -f web
```

### Production

1. **Use production settings:**
```bash
# In Dockerfile
ENV DJANGO_SETTINGS_MODULE=lti_recommender_project.settings_docker
```

2. **Build with no cache:**
```bash
docker-compose build --no-cache
```

3. **Start with restart policy:**
```bash
docker-compose up -d --force-recreate
```

---

## Accessing the Application

### Admin Panel

Open: http://localhost:8000/admin/

**Default credentials** (from `.env`):
- Username: `admin` (or `$DJANGO_SUPERUSER_USERNAME`)
- Password: `admin` (or `$DJANGO_SUPERUSER_PASSWORD`)

**⚠️ CHANGE these in production!**

### API Endpoints

- LTI JWKS: http://localhost:8000/lti/jwks/
- LTI Login: http://localhost:8000/lti/login/
- LTI Launch: http://localhost:8000/lti/launch/

---

## LTI Integration with Moodle

### 1. Get Your Public Key

```bash
docker-compose exec web cat /app/keys/lti_public_key.pem
```

### 2. Register Tool in Moodle

1. Go to **Site Administration** → **Plugins** → **External Tools** → **Manage tools**
2. Click **Configure a tool manually**
3. Fill in:
   - **Tool name:** LTI Recommender
   - **Tool URL:** `http://your-server:8000/lti/launch/`
   - **LTI version:** LTI 1.3
   - **Public key:** Paste the output from step 1
   - **Initiate login URL:** `http://your-server:8000/lti/login/`
   - **Redirection URL(s):** `http://your-server:8000/lti/launch/`

4. Save and get the **Client ID**

### 3. Update Your Configuration

Edit `.env` with the Client ID from Moodle:
```bash
LTI_CLIENT_ID=your-client-id-from-moodle
```

Restart:
```bash
docker-compose restart web
```

### 4. Test

1. Add an **External Tool** activity in a Moodle course
2. Select your tool
3. Click on it - should launch the LTI app!

---

## Maintenance

### Database Backup

```bash
# Backup
docker-compose exec db pg_dump -U lti_user lti_recommender_db > backup_$(date +%Y%m%d).sql

# Restore
cat backup_20241206.sql | docker-compose exec -T db psql -U lti_user lti_recommender_db
```

### Update Application

```bash
# Pull latest code
git pull

# Rebuild
docker-compose build

# Apply migrations
docker-compose exec web python manage.py migrate

# Restart
docker-compose restart web
```

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f web
docker-compose logs -f db

# Last 100 lines
docker-compose logs --tail=100 web
```

### Access Container Shell

```bash
# Django app
docker-compose exec web bash

# Database
docker-compose exec db psql -U lti_user -d lti_recommender_db

# Redis
docker-compose exec redis redis-cli
```

---

## Troubleshooting

### Issue: "Database is unavailable"

**Solution:**
```bash
# Check database status
docker-compose ps db

# View database logs
docker-compose logs db

# Restart database
docker-compose restart db
```

### Issue: "Permission denied on /app/keys"

**Solution:**
```bash
# Fix permissions
sudo chown -R 1000:1000 keys/
```

### Issue: "Module not found: sentence_transformers"

**Solution:**
```bash
# Rebuild with no cache
docker-compose build --no-cache web
```

### Issue: "LTI launch failed"

**Checklist:**
1. ✅ Client ID matches Moodle configuration
2. ✅ Public key is correctly copied to Moodle
3. ✅ URLs in `.env` match your deployment
4. ✅ CSRF_TRUSTED_ORIGINS includes Moodle URL

### Clear Everything and Start Fresh

```bash
# Stop and remove containers, networks, volumes
docker-compose down -v

# Remove images
docker-compose down --rmi all

# Start clean
docker-compose up -d
```

---

## Production Deployment

### 1. Use HTTPS

**Nginx Configuration** (uncomment in `docker-compose.yml`):

Create `nginx/nginx.conf`:
```nginx
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl;
    server_name your-domain.com;

    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;

    location / {
        proxy_pass http://web:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static/ {
        alias /app/staticfiles/;
    }

    location /media/ {
        alias /app/media/;
    }
}
```

### 2. Security Checklist

- [ ] Change `SECRET_KEY`
- [ ] Set `DEBUG=False`
- [ ] Change default passwords (DB, admin)
- [ ] Use strong `DB_PASSWORD`
- [ ] Enable HTTPS
- [ ] Set `ALLOWED_HOSTS` correctly
- [ ] Add Moodle URL to `CSRF_TRUSTED_ORIGINS`
- [ ] Restrict database port (don't expose 5432)
- [ ] Regular backups enabled

### 3. Performance Tuning

**Increase Gunicorn workers** in `.env`:
```bash
GUNICORN_WORKERS=8  # 2-4 x CPU cores
```

**Enable Redis caching**:
```bash
REDIS_URL=redis://redis:6379/0
```

### 4. Monitoring

**Health checks:**
```bash
curl http://localhost:8000/admin/
```

**Resource usage:**
```bash
docker stats
```

---

## Summary

**Start:** `docker-compose up -d`  
**Stop:** `docker-compose down`  
**Logs:** `docker-compose logs -f web`  
**Rebuild:** `docker-compose build --no-cache`  
**Shell:** `docker-compose exec web bash`

For issues, check logs first: `docker-compose logs`

---

**Need help?** Check the [implementation plan](file:///../.gemini/antigravity/brain/21ddec30-68d5-41f0-8d32-59448ca4cd9e/implementation_plan.md) or create an issue in the repository.
