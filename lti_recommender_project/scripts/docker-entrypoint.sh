#!/bin/bash
# Docker entrypoint script for LTI Recommender Django application

set -e

echo "🚀 Starting LTI Recommender application..."

# Generate LTI keys if they don't exist
echo "🔑 Setting up LTI keys..."
bash /app/scripts/generate-lti-keys.sh

# Wait for database to be ready
echo "⏳ Waiting for database..."
python << END
import sys
import time
import psycopg2
from psycopg2 import OperationalError
import os

max_retries = 30
retry_interval = 1

for i in range(max_retries):
    try:
        conn = psycopg2.connect(
            dbname=os.environ.get('DB_NAME', 'lti_recommender_db'),
            user=os.environ.get('DB_USER', 'lti_user'),
            password=os.environ.get('DB_PASSWORD', 'lti_user'),
            host=os.environ.get('DB_HOST', 'db'),
            port=os.environ.get('DB_PORT', '5432')
        )
        conn.close()
        print("✅ Database is ready!")
        sys.exit(0)
    except OperationalError:
        if i < max_retries - 1:
            print(f"⏳ Database not ready yet, retrying... ({i+1}/{max_retries})")
            time.sleep(retry_interval)
        else:
            print("❌ Database connection failed after max retries")
            sys.exit(1)
END

# Run database migrations
echo "🔄 Running database migrations..."
python manage.py migrate --noinput

# Collect static files
echo "📦 Collecting static files..."
python manage.py collectstatic --noinput --clear

# Create superuser if it doesn't exist
echo "👤 Creating superuser if needed..."
python manage.py shell << END
from django.contrib.auth import get_user_model
import os

User = get_user_model()
username = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'admin')
email = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@example.com')
password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', 'admin')

if not User.objects.filter(username=username).exists():
    User.objects.create_superuser(username, email, password)
    print(f"✅ Superuser '{username}' created successfully!")
else:
    print(f"ℹ️  Superuser '{username}' already exists")
END

echo "✅ Application setup complete!"
echo "🌐 Starting Gunicorn server..."

# Execute the main container command
exec "$@"
