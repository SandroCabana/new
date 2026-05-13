from django.contrib import admin
from lti_recommender_project.apps.users.models import GlobalUser, LTIIdentity

@admin.register(GlobalUser)
class GlobalUserAdmin(admin.ModelAdmin):
    """Admin interface for global users."""
    list_display = ('id', 'email', 'display_name', 'inferred_level', 'total_interactions', 'last_active')
    list_filter = ('inferred_level',)
    search_fields = ('email', 'display_name', 'id')
    readonly_fields = ('id', 'first_interaction', 'last_active', 'total_interactions', 'average_completion', 'average_rating')


@admin.register(LTIIdentity)
class LTIIdentityAdmin(admin.ModelAdmin):
    """Admin interface for LTI identities."""
    list_display = ('sub', 'issuer', 'global_user', 'role', 'platform_id')
    list_filter = ('issuer', 'role')
    search_fields = ('sub', 'issuer', 'global_user__email')
    autocomplete_fields = ('global_user',)
