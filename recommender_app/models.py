from django.db import models

class EducationalResource(models.Model):
    """
    Representa un recurso educativo que puede ser recomendado.
    """
    # Identificador único del recurso (ej. un ID de una base de datos externa, o autogenerado)
    resource_id = models.CharField(max_length=255, unique=True, help_text="ID único del recurso, puede ser externo si aplica.")
    
    title = models.CharField(max_length=255, help_text="Título del recurso.")
    description = models.TextField(blank=True, null=True, help_text="Breve descripción del recurso.")
    
    # URL donde se encuentra el recurso
    url = models.URLField(max_length=500, help_text="URL donde el recurso está disponible.")
    
    # Metadatos del recurso (ejemplos, puedes añadir más según tu necesidad)
    author = models.CharField(max_length=255, blank=True, null=True, help_text="Autor o creador del recurso.")
    resource_type = models.CharField(
        max_length=50,
        choices=[
            ('video', 'Video'),
            ('pdf', 'PDF'),
            ('article', 'Artículo'),
            ('quiz', 'Cuestionario'),
            ('tool', 'Herramienta Interactiva'),
            ('other', 'Otro'),
        ],
        default='other',
        help_text="Tipo de recurso (video, PDF, artículo, etc.)."
    )
    
    # Etiquetas o palabras clave para categorizar el recurso
    tags = models.CharField(max_length=500, blank=True, null=True, help_text="Palabras clave separadas por comas (ej. 'matemáticas, álgebra, ecuaciones').")
    
    # Nivel de dificultad, si aplica
    difficulty_level = models.CharField(
        max_length=50,
        choices=[
            ('beginner', 'Principiante'),
            ('intermediate', 'Intermedio'),
            ('advanced', 'Avanzado'),
        ],
        blank=True,
        null=True,
        help_text="Nivel de dificultad del recurso."
    )

    # Contexto LTI opcional al que este recurso está fuertemente asociado (ej. un curso específico)
    lti_context_id = models.CharField(max_length=255, blank=True, null=True, help_text="ID del contexto LTI (curso) al que pertenece el recurso, si es específico.")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "Recurso Educativo"
        verbose_name_plural = "Recursos Educativos"
        # Asegura que no haya recursos duplicados por ID y contexto LTI
        unique_together = ('resource_id', 'lti_context_id')


class UserInteraction(models.Model):
    """
    Registra una interacción de un usuario con un recurso educativo.
    """
    # Usamos CharField para lti_user_id y lti_context_id para que coincidan con los IDs que vienen de LTI.
    lti_user_id = models.CharField(max_length=255, help_text="ID del usuario LTI.")
    lti_context_id = models.CharField(max_length=255, help_text="ID del contexto LTI (curso).")
    
    # Relación con el recurso educativo que fue interactuado.
    # Si un recurso se elimina, las interacciones con él también se eliminan (CASCADE).
    resource = models.ForeignKey(EducationalResource, on_delete=models.CASCADE, related_name='interactions', help_text="Recurso educativo con el que el usuario interactuó.")
    
    # Tipo de interacción (ej. 'viewed', 'completed', 'downloaded', 'scored')
    interaction_type = models.CharField(max_length=50, help_text="Tipo de interacción (ej. 'viewed', 'completed', 'downloaded').")
    
    # Campo para almacenar datos adicionales sobre la interacción (ej. tiempo de vista, puntuación)
    value = models.FloatField(blank=True, null=True, help_text="Valor asociado a la interacción (ej. tiempo en segundos, puntuación de un quiz).")
    
    timestamp = models.DateTimeField(auto_now_add=True, help_text="Marca de tiempo de la interacción.")

    def __str__(self):
        return f"{self.lti_user_id} - {self.interaction_type} - {self.resource.title}"

    class Meta:
        verbose_name = "Interacción de Usuario"
        verbose_name_plural = "Interacciones de Usuarios"
        # Indexar por usuario y recurso para búsquedas rápidas
        indexes = [
            models.Index(fields=['lti_user_id', 'resource']),
            models.Index(fields=['lti_context_id']),
        ]
