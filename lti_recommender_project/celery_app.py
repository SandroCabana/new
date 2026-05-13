"""
Celery application for LTI Recommender.
Handles async tasks: model retraining, embedding updates, precompute.
"""
import os
from celery import Celery
from celery.schedules import crontab

# Use docker settings by default if DJANGO_SETTINGS_MODULE not set
os.environ.setdefault(
    'DJANGO_SETTINGS_MODULE',
    'lti_recommender_project.settings_docker'
)

app = Celery('lti_recommender')

# Read Celery config from Django settings (CELERY_ prefix)
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks in all installed apps
app.autodiscover_tasks()

# Fix deprecation warnings and ensure connection resilience
app.conf.broker_connection_retry_on_startup = True
app.conf.broker_connection_retry = True

# ============================================================================
# BEAT SCHEDULE — periodic tasks
# ============================================================================
app.conf.beat_schedule = {
    # Retrain ML models every night at 2am UTC
    'retrain-ml-models-nightly': {
        'task': 'lti_recommender_project.apps.recommendations.tasks.retrain_all_models',
        'schedule': crontab(hour=2, minute=0),
        'options': {'queue': 'ml_training'},
    },
    # Incremental embedding update every hour
    'update-embeddings-hourly': {
        'task': 'lti_recommender_project.apps.recommendations.tasks.update_embeddings_incremental',
        'schedule': crontab(minute=5),  # 5 past every hour
        'options': {'queue': 'embeddings'},
    },
    # Precompute recs for active users every 30 min
    'precompute-recommendations': {
        'task': 'lti_recommender_project.apps.recommendations.tasks.precompute_active_users',
        'schedule': crontab(minute='*/30'),
        'options': {'queue': 'recommendations'},
    },
    # Run scraper for new resources every night at 3am UTC
    'scrape-new-resources-nightly': {
        'task': 'lti_recommender_project.apps.recommendations.tasks.run_scraper_task',
        'schedule': crontab(hour=3, minute=0),
        'options': {'queue': 'scraping'},
    },
}

app.conf.task_queues = {
    'ml_training': {'exchange': 'ml_training'},
    'embeddings': {'exchange': 'embeddings'},
    'recommendations': {'exchange': 'recommendations'},
    'scraping': {'exchange': 'scraping'},
}

app.conf.task_default_queue = 'recommendations'


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Debug task to verify Celery is working."""
    print(f'Request: {self.request!r}')
