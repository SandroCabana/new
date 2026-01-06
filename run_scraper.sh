
#!/bin/bash
set -e

# Define paths
PROJECT_ROOT="/home/sandrocabana/lti_moodle_recomender"
VENV_PYTHON="$PROJECT_ROOT/venv_lti_recommender/bin/python3"
SCRAPY_PROJECT_DIR="$PROJECT_ROOT/scraper_project"

# Activate venv just in case, though we use direct python path
source "$PROJECT_ROOT/venv_lti_recommender/bin/activate" 2>/dev/null || true

# Install scraper requirements if missing
#$VENV_PYTHON -m pip install scrapy scrapy-user-agents

# Run migrations to ensure DB schema exists
# echo "Running migrations..."
# cd "$PROJECT_ROOT"
# VENV_PYTHON manage.py migrate


# Check initial count
echo "Checking initial resource count..."
PWD=$PROJECT_ROOT $VENV_PYTHON check_count.py

# Run Scraper
echo "Running Scraper..."
cd "$SCRAPY_PROJECT_DIR"
PYTHONPATH="$PROJECT_ROOT" "$VENV_PYTHON" -m scrapy crawl oer_comprehensive

# Check final count
echo "Checking final resource count..."
cd "$PROJECT_ROOT"
$VENV_PYTHON check_count.py
