from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator


class UserInteraction(models.Model):
    """
    Registra una interacción de un usuario con un recurso educativo.
    Incluye tracking avanzado de engagement y comportamiento.
    """
    # Usamos CharField para lti_user_id y lti_context_id para que coincidan con los IDs que vienen de LTI.
    lti_user_id = models.CharField(max_length=255, help_text="ID del usuario LTI.")
    lti_context_id = models.CharField(max_length=255, help_text="ID del contexto LTI (curso).")
    
    # Relación con el recurso educativo que fue interactuado.
    # Si un recurso se elimina, las interacciones con él también se eliminan (CASCADE).
    resource = models.ForeignKey(
        'resources.EducationalResource', 
        on_delete=models.CASCADE, 
        related_name='interactions', 
        help_text="Recurso educativo con el que el usuario interactuó."
    )
    
    # Tipo de interacción (ej. 'viewed', 'completed', 'downloaded', 'scored')
    interaction_type = models.CharField(max_length=50, help_text="Tipo de interacción (ej. 'viewed', 'completed', 'downloaded').")
    
    # Campo para almacenar datos adicionales sobre la interacción (ej. tiempo de vista, puntuación)
    value = models.FloatField(blank=True, null=True, help_text="Valor asociado a la interacción (ej. tiempo en segundos, puntuación de un quiz).")
    
    # --- CAMPOS AVANZADOS DE TRACKING ---
    
    # Tiempo que el usuario pasó con el recurso (en segundos)
    time_spent = models.FloatField(
        blank=True, 
        null=True, 
        validators=[MinValueValidator(0.0)],
        help_text="Tiempo en segundos que el usuario pasó con el recurso."
    )
    
    # Porcentaje de completitud del recurso (0-100)
    completion_percentage = models.FloatField(
        blank=True,
        null=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(100.0)],
        help_text="Porcentaje de completitud del recurso (0-100)."
    )
    
    # Rating/Valoración del usuario (1-5 estrellas)
    rating = models.IntegerField(
        blank=True,
        null=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Valoración del usuario (1-5 estrellas)."
    )
    
    # Profundidad de scroll para artículos/PDFs (0-100%)
    scroll_depth = models.FloatField(
        blank=True,
        null=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(100.0)],
        help_text="Profundidad de scroll alcanzada (0-100%)."
    )
    
    # Flags para acciones específicas
    downloaded = models.BooleanField(
        default=False,
        help_text="Indica si el usuario descargó el recurso."
    )
    
    shared = models.BooleanField(
        default=False,
        help_text="Indica si el usuario compartió el recurso."
    )
    
    # Metadata adicional flexible (JSON)
    metadata = models.JSONField(
        blank=True,
        null=True,
        help_text="Datos adicionales sobre la interacción (formato JSON)."
    )
    
    timestamp = models.DateTimeField(auto_now_add=True, help_text="Marca de tiempo de la interacción.")

    def __str__(self):
        return f"{self.lti_user_id} - {self.interaction_type} - {self.resource.title}"

    class Meta:
        verbose_name = "Interacción de Usuario"
        verbose_name_plural = "Interacciones de Usuarios"
        db_table = 'recommender_app_userinteraction'  # Mantener nombre de tabla existente
        # Indexar por usuario y recurso para búsquedas rápidas
        indexes = [
            models.Index(fields=['lti_user_id', 'resource']),
            models.Index(fields=['lti_context_id']),
            models.Index(fields=['rating']),  # Para queries de recursos mejor valorados
            models.Index(fields=['timestamp']),  # Para análisis temporales
        ]
