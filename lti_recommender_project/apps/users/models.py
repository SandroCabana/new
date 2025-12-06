from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator


class UserProfile(models.Model):
    """
    Perfil persistente de usuario para almacenar información y preferencias.
    Se actualiza automáticamente con cada interacción.
    """
    # ID único del usuario LTI (usamos esto como primary key ya que es único)
    lti_user_id = models.CharField(
        max_length=255, 
        primary_key=True,
        help_text="ID único del usuario LTI."
    )
    
    # Información básica del usuario
    display_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Nombre del usuario."
    )
    
    email = models.EmailField(
        blank=True,
        null=True,
        help_text="Email del usuario."
    )
    
    # Nivel inferido del usuario basado en sus interacciones
    inferred_level = models.CharField(
        max_length=50,
        choices=[
            ('beginner', 'Principiante'),
            ('intermediate', 'Intermedio'),
            ('advanced', 'Avanzado'),
        ],
        default='beginner',
        help_text="Nivel inferido del usuario basado en sus interacciones."
    )
    
    # Tipos de recursos preferidos (almacenado como JSON)
    preferred_resource_types = models.JSONField(
        default=dict,
        blank=True,
        help_text="Tipos de recursos preferidos y su frecuencia de interacción (ej. {'video': 10, 'pdf': 5})."
    )
    
    # Tags de interés extraídos de las interacciones del usuario
    interest_tags = models.TextField(
        blank=True,
        null=True,
        help_text="Tags de interés del usuario, separados por comas."
    )
    
    # Estadísticas de interacción
    total_interactions = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Número total de interacciones del usuario."
    )
    
    average_completion = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(100.0)],
        help_text="Promedio de porcentaje de completitud de los recursos interactuados."
    )
    
    average_rating = models.FloatField(
        blank=True,
        null=True,
        validators=[MinValueValidator(1.0), MaxValueValidator(5.0)],
        help_text="Promedio de ratings dados por el usuario."
    )
    
    # Timestamps
    first_interaction = models.DateTimeField(
        auto_now_add=True,
        help_text="Fecha de primera interacción del usuario."
    )
    
    last_active = models.DateTimeField(
        auto_now=True,
        help_text="Última actividad del usuario."
    )
    
    # Metadata adicional
    metadata = models.JSONField(
        blank=True,
        null=True,
        help_text="Datos adicionales del perfil (formato JSON)."
    )
    
    def __str__(self):
        return f"{self.display_name or self.lti_user_id} ({self.inferred_level})"
    
    class Meta:
        verbose_name = "Perfil de Usuario"
        verbose_name_plural = "Perfiles de Usuarios"
        db_table = 'recommender_app_userprofile'
        indexes = [
            models.Index(fields=['inferred_level']),
            models.Index(fields=['last_active']),
        ]
