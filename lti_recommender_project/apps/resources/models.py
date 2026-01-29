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
    url = models.TextField(help_text="URL donde el recurso está disponible.")
    
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

    # --- CAMPOS PARA SIMILITUD SEMÁNTICA ---
    
    # Embedding vectorial del recurso (almacenado como JSON)
    embedding = models.JSONField(
        blank=True,
        null=True,
        help_text="Vector de embedding semántico del recurso (formato JSON array)."
    )
    
    # Versión del modelo usado para generar el embedding
    embedding_model_version = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Versión del modelo de embedding usado (ej. 'all-MiniLM-L6-v2')."
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def get_embedding_text(self):
        """
        Retorna el texto combinado para generar embeddings semánticos.
        Combina título, descripción y tags.
        """
        parts = [self.title]
        if self.description:
            parts.append(self.description)
        if self.tags:
            parts.append(self.tags)
        return " ".join(parts)

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "Recurso Educativo"
        verbose_name_plural = "Recursos Educativos"
        db_table = 'recommender_app_educationalresource'  # Mantener nombre de tabla existente
        # Asegura que no haya recursos duplicados por ID y contexto LTI
        unique_together = ('resource_id', 'lti_context_id')
