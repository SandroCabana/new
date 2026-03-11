from django.apps import AppConfig


class InteractionsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'lti_recommender_project.apps.interactions'
    verbose_name = 'User Interactions'

    def ready(self):
        """Connect signal for cache invalidation on new interactions."""
        import lti_recommender_project.apps.interactions.signals  # noqa: F401
