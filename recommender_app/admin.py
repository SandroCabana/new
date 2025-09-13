from django.contrib import admin
from .models import EducationalResource, UserInteraction

@admin.register(EducationalResource)
class EducationalResourceAdmin(admin.ModelAdmin):
    list_display = ('title', 'resource_type', 'difficulty_level', 'lti_context_id', 'created_at')
    search_fields = ('title', 'description', 'tags', 'author')
    list_filter = ('resource_type', 'difficulty_level', 'lti_context_id')
    # Si quieres que 'resource_id' sea de solo lectura para evitar cambios accidentales después de crearlo
    # readonly_fields = ('resource_id',)

@admin.register(UserInteraction)
class UserInteractionAdmin(admin.ModelAdmin):
    list_display = ('lti_user_id', 'resource', 'interaction_type', 'value', 'timestamp')
    search_fields = ('lti_user_id', 'lti_context_id', 'resource__title', 'interaction_type')
    list_filter = ('interaction_type', 'lti_context_id', 'timestamp')
    raw_id_fields = ('resource',) # Utiliza un widget de búsqueda para ForeignKey
    readonly_fields = ('timestamp',)