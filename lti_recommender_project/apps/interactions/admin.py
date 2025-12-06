from django.contrib import admin
from .models import UserInteraction


@admin.register(UserInteraction)
class UserInteractionAdmin(admin.ModelAdmin):
    """
    Configuración del panel de administración para UserInteraction.
    """
    list_display = (
        'lti_user_id', 'resource', 'interaction_type', 
        'rating', 'completion_percentage', 'time_spent', 'timestamp'
    )
    list_filter = ('interaction_type', 'rating', 'downloaded', 'shared', 'timestamp', 'lti_context_id')
    search_fields = ('lti_user_id', 'lti_context_id', 'resource__title')
    readonly_fields = ('timestamp',)
    date_hierarchy = 'timestamp'
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('lti_user_id', 'lti_context_id', 'resource', 'interaction_type', 'timestamp')
        }),
        ('Métricas de Engagement', {
            'fields': ('time_spent', 'completion_percentage', 'scroll_depth')
        }),
        ('Feedback del Usuario', {
            'fields': ('rating',)
        }),
        ('Acciones', {
            'fields': ('downloaded', 'shared')
        }),
        ('Otros Datos', {
            'fields': ('value', 'metadata'),
            'classes': ('collapse',)
        }),
    )

