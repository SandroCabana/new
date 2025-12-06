from django.contrib import admin
from lti_recommender_project.apps.users.models import UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    """Admin interface for user profiles."""
    list_display = [
        'lti_user_id', 'display_name', 'inferred_level', 
        'total_interactions', 'average_completion', 'last_active'
    ]
    list_filter = ['inferred_level', 'last_active']
    search_fields = ['lti_user_id', 'display_name', 'email']
    readonly_fields = [
        'lti_user_id', 'first_interaction', 'last_active',
        'total_interactions', 'average_completion', 'average_rating'
    ]
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('lti_user_id', 'display_name', 'email')
        }),
        ('Perfil de Aprendizaje', {
            'fields': ('inferred_level', 'preferred_resource_types', 'interest_tags')
        }),
        ('Estadísticas', {
            'fields': ('total_interactions', 'average_completion', 'average_rating')
        }),
        ('Metadata', {
            'fields': ('first_interaction', 'last_active', 'metadata'),
            'classes': ('collapse',)
        }),
    )
