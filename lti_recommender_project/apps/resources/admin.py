from django.contrib import admin
from .models import EducationalResource


@admin.register(EducationalResource)
class EducationalResourceAdmin(admin.ModelAdmin):
    """
    Configuración del panel de administración para EducationalResource.
    """
    list_display = ('title', 'resource_type', 'difficulty_level', 'lti_context_id', 'created_at')
    list_filter = ('resource_type', 'difficulty_level', 'created_at')
    search_fields = ('title', 'description', 'tags', 'author')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Información Básica', {
            'fields': ('resource_id', 'title', 'description', 'url')
        }),
        ('Metadatos', {
            'fields': ('author', 'resource_type', 'tags', 'difficulty_level')
        }),
        ('Contexto LTI', {
            'fields': ('lti_context_id',)
        }),
        ('Fechas', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
