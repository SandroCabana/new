from django.db import models
try:
    from pgvector.django import VectorField, HnswIndex
    PGVECTOR_AVAILABLE = True
except ImportError:
    PGVECTOR_AVAILABLE = False
    VectorField = None
    HnswIndex = None


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
    
    # Embedding vectorial del recurso
    # Usa pgvector VectorField si está disponible, sino JSONField como fallback
    if PGVECTOR_AVAILABLE:
        embedding = VectorField(
            dimensions=768,  # paraphrase-multilingual-mpnet-base-v2
            null=True,
            blank=True,
            help_text="Vector de embedding semántico (pgvector, 768 dims)."
        )
    else:
        embedding = models.JSONField(
            blank=True,
            null=True,
            help_text="Vector de embedding semántico (JSON fallback)."
        )
    
    # Versión del modelo usado para generar el embedding
    embedding_model_version = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Versión del modelo de embedding (ej. 'paraphrase-multilingual-mpnet-base-v2')."
    )
    
    # Timestamp para actualizaciones incrementales
    embedding_updated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Última vez que se actualizó el embedding."
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def get_embedding_text(self) -> str:
        """
        Retorna texto estructurado para generar embeddings semánticos.
        Estrategia optimizada para español:
        - Título repetido 3x para mayor peso semántico
        - Descripción truncada a 300 palabras (chunking)
        - Tags como frase natural
        - Dificultad en lenguaje descriptivo
        """
        # Título con mayor peso (repetido 3 veces)
        title_weighted = f"{self.title}. {self.title}. {self.title}."
        parts = [title_weighted]
        
        if self.description:
            # Chunking: máximo 300 palabras de descripción
            desc_words = self.description.split()[:300]
            parts.append(" ".join(desc_words))
        
        if self.tags:
            # Tags como frase natural para mejor embeddings
            tag_phrase = f"Este recurso educativo cubre los temas: {self.tags}."
            parts.append(tag_phrase)
        
        if self.difficulty_level:
            difficulty_map = {
                'beginner': 'nivel básico para principiantes',
                'intermediate': 'nivel intermedio',
                'advanced': 'nivel avanzado para expertos',
            }
            diff_desc = difficulty_map.get(self.difficulty_level, self.difficulty_level)
            parts.append(f"Dificultad: {diff_desc}.")
        
        if self.resource_type:
            type_map = {
                'video': 'recurso en formato video',
                'pdf': 'documento PDF',
                'article': 'artículo de lectura',
                'quiz': 'cuestionario de evaluación',
                'tool': 'herramienta interactiva',
            }
            type_desc = type_map.get(self.resource_type, self.resource_type)
            parts.append(f"Formato: {type_desc}.")
        
        return " ".join(parts)

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "Recurso Educativo"
        verbose_name_plural = "Recursos Educativos"
        db_table = 'recommender_app_educationalresource'
        # No duplicates by resource_id + context
        unique_together = ('resource_id', 'lti_context_id')
        indexes = [
            models.Index(fields=['resource_type']),
            models.Index(fields=['difficulty_level']),
            models.Index(fields=['lti_context_id']),
            models.Index(fields=['embedding_updated_at']),
        ]
        # HNSW index for vector similarity search (only if pgvector is available)
        if PGVECTOR_AVAILABLE and HnswIndex:
            indexes += [
                HnswIndex(
                    name='resource_embedding_hnsw',
                    fields=['embedding'],
                    m=16,             # Edges per node (balance speed/memory)
                    ef_construction=64,  # Graph quality (higher = better but slower)
                    opclasses=['vector_cosine_ops'],
                ),
            ]
