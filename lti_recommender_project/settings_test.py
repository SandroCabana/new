"""
Test settings for running Django tests with SQLite.
"""
from lti_recommender_project.settings import *

# Override database for tests - use SQLite in memory
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

# Faster password hashing for tests
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

# Disable migrations for faster tests
class DisableMigrations:
    def __contains__(self, item):
        return True
    
    def __getitem__(self, item):
        return None

# MIGRATION_MODULES = DisableMigrations()

# Speed up tests
DEBUG = False
TEMPLATE_DEBUG = False
