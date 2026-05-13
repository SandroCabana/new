import uuid
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator


class GlobalUser(models.Model):
    """
    Identidad centralizada del estudiante. Consolida su perfil global
    independientemente de qué plataforma Moodle (LTI) utilice.
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="ID global único del usuario."
    )
    email = models.EmailField(
        blank=True,
        null=True,
        help_text="Email principal del usuario (opcional)."
    )
    display_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Nombre global del usuario."
    )
    
    # Perfil global inferido
    inferred_level = models.CharField(
        max_length=50,
        choices=[
            ('beginner', 'Principiante'),
            ('intermediate', 'Intermedio'),
            ('advanced', 'Avanzado'),
        ],
        default='beginner',
        help_text="Nivel inferido global."
    )
    preferences_json = models.JSONField(
        default=dict,
        blank=True,
        help_text="Preferencias de tipos de recursos (ej. {'video': 10, 'pdf': 5})."
    )
    interest_tags = models.TextField(
        blank=True,
        null=True,
        help_text="Tags de interés globales, separados por comas."
    )
    
    # Estadísticas globales
    total_interactions = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)]
    )
    average_completion = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(100.0)]
    )
    average_rating = models.FloatField(
        blank=True,
        null=True,
        validators=[MinValueValidator(1.0), MaxValueValidator(5.0)]
    )
    
    first_interaction = models.DateTimeField(auto_now_add=True)
    last_active = models.DateTimeField(auto_now=True)
    metadata = models.JSONField(blank=True, null=True)

    def __str__(self):
        return f"{self.display_name or self.email or str(self.id)} ({self.inferred_level})"

    class Meta:
        verbose_name = "Usuario Global"
        verbose_name_plural = "Usuarios Globales"
        db_table = 'recommender_app_globaluser'
        indexes = [
            models.Index(fields=['inferred_level']),
            models.Index(fields=['last_active']),
        ]


class LTIIdentity(models.Model):
    """
    Identidad específica de una plataforma LTI (ej. un servidor Moodle).
    Varios LTIIdentity pueden apuntar a un mismo GlobalUser.
    """
    global_user = models.ForeignKey(
        GlobalUser,
        on_delete=models.CASCADE,
        related_name='lti_identities',
        help_text="Usuario global asociado a esta identidad LTI."
    )
    
    # Standard LTI 1.3 identifiers
    issuer = models.URLField(
        max_length=255,
        help_text="El emisor del token LTI (ej. https://moodle.example.com)."
    )
    sub = models.CharField(
        max_length=255,
        help_text="El identificador de usuario (subject) dentro de este emisor."
    )
    platform_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Tool Consumer Instance GUID."
    )
    role = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Rol del usuario en la plataforma (ej. Learner, Instructor)."
    )
    
    # Relación con contextos LTI (Cursos)
    contexts = models.ManyToManyField(
        'lti_integration.LTIContext',
        related_name='identities',
        blank=True,
        help_text="Cursos en los que esta identidad ha interactuado."
    )

    class Meta:
        verbose_name = "Identidad LTI"
        verbose_name_plural = "Identidades LTI"
        db_table = 'recommender_app_ltiidentity'
        unique_together = ('issuer', 'sub')  # La combinación emisor + usuario es única

    def __str__(self):
        return f"LTI:{self.sub} @ {self.issuer}"
