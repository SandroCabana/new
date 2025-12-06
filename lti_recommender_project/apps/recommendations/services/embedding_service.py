"""
Servicio de Embeddings Semánticos
Usa Sentence Transformers para generar y gestionar embeddings de recursos educativos.
"""

import logging
import numpy as np
from typing import List, Dict, Optional, Tuple
from django.conf import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Servicio para generar embeddings semánticos de recursos educativos
    usando el modelo all-MiniLM-L6-v2 (384 dimensiones).
    """
    
    def __init__(self):
        """Inicializa el servicio y carga el modelo de embeddings."""
        self.model_name = getattr(
            settings, 
            'EMBEDDING_MODEL', 
            'sentence-transformers/all-MiniLM-L6-v2'
        )
        self.model = None
        self._load_model()
    
    def _load_model(self):
        """Carga el modelo de Sentence Transformers de forma lazy."""
        if self.model is None:
            try:
                from sentence_transformers import SentenceTransformer
                logger.info(f"Cargando modelo de embeddings: {self.model_name}")
                self.model = SentenceTransformer(self.model_name)
                logger.info("Modelo cargado exitosamente")
            except ImportError:
                logger.error(
                    "sentence-transformers no está instalado. "
                    "Ejecuta: pip install sentence-transformers"
                )
                raise
            except Exception as e:
                logger.error(f"Error al cargar el modelo de embeddings: {e}")
                raise
    
    def generate_embedding(self, text: str) -> List[float]:
        """
        Genera un embedding para un texto dado.
        
        Args:
            text: Texto para generar embedding
            
        Returns:
            Lista de floats representando el vector de embedding
        """
        if not text or not text.strip():
            logger.warning("Texto vacío recibido para embedding")
            return []
        
        try:
            embedding = self.model.encode(text, convert_to_numpy=True)
            return embedding.tolist()
        except Exception as e:
            logger.error(f"Error al generar embedding: {e}")
            return []
    
    def update_resource_embeddings(self, force_update: bool = False):
        """
        Actualiza los embeddings de todos los recursos en la base de datos.
        
        Args:
            force_update: Si es True, regenera embeddings incluso si ya existen
            
        Returns:
            Tuple de (recursos_actualizados, recursos_fallidos)
        """
        from lti_recommender_project.apps.resources.models import EducationalResource
        
        updated_count = 0
        failed_count = 0
        
        # Filtrar recursos que necesitan embeddings
        if force_update:
            resources = EducationalResource.objects.all()
        else:
            resources = EducationalResource.objects.filter(embedding__isnull=True)
        
        total = resources.count()
        logger.info(f"Procesando {total} recursos para generar embeddings...")
        
        for idx, resource in enumerate(resources, 1):
            try:
                # Obtener texto combinado del recurso
                text = resource.get_embedding_text()
                
                # Generar embedding
                embedding = self.generate_embedding(text)
                
                if embedding:
                    # Guardar embedding en el recurso
                    resource.embedding = embedding
                    resource.embedding_model_version = self.model_name
                    resource.save(update_fields=['embedding', 'embedding_model_version'])
                    updated_count += 1
                    
                    if idx % 10 == 0:
                        logger.info(f"Progreso: {idx}/{total} recursos procesados")
                else:
                    logger.warning(f"No se pudo generar embedding para recurso {resource.id}")
                    failed_count += 1
                    
            except Exception as e:
                logger.error(f"Error procesando recurso {resource.id}: {e}")
                failed_count += 1
        
        logger.info(
            f"Actualización completada. "
            f"Actualizados: {updated_count}, Fallidos: {failed_count}"
        )
        return updated_count, failed_count
    
    def get_similar_resources(
        self, 
        resource_id: int, 
        limit: int = 5,
        min_similarity: float = 0.3
    ) -> List[Dict]:
        """
        Encuentra recursos similares basándose en similitud de embeddings.
        
        Args:
            resource_id: ID del recurso de referencia
            limit: Número máximo de recursos similares a retornar
            min_similarity: Umbral mínimo de similitud (0-1)
            
        Returns:
            Lista de diccionarios con recursos similares y sus scores
        """
        from lti_recommender_project.apps.resources.models import EducationalResource
        
        try:
            # Obtener el recurso de referencia
            source_resource = EducationalResource.objects.get(id=resource_id)
            
            if not source_resource.embedding:
                logger.warning(f"Recurso {resource_id} no tiene embedding")
                return []
            
            source_embedding = np.array(source_resource.embedding)
            
            # Obtener todos los recursos con embeddings (excepto el source)
            candidates = EducationalResource.objects.filter(
                embedding__isnull=False
            ).exclude(id=resource_id)
            
            similarities = []
            
            for candidate in candidates:
                try:
                    candidate_embedding = np.array(candidate.embedding)
                    
                    # Calcular similitud coseno
                    similarity = self._cosine_similarity(
                        source_embedding, 
                        candidate_embedding
                    )
                    
                    if similarity >= min_similarity:
                        similarities.append({
                            'resource': candidate,
                            'similarity': float(similarity)
                        })
                        
                except Exception as e:
                    logger.error(f"Error comparando con recurso {candidate.id}: {e}")
                    continue
            
            # Ordenar por similitud descendente
            similarities.sort(key=lambda x: x['similarity'], reverse=True)
            
            # Retornar los top N
            return similarities[:limit]
            
        except EducationalResource.DoesNotExist:
            logger.error(f"Recurso {resource_id} no encontrado")
            return []
        except Exception as e:
            logger.error(f"Error en get_similar_resources: {e}")
            return []
    
    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """
        Calcula la similitud coseno entre dos vectores.
        
        Args:
            vec1: Primer vector
            vec2: Segundo vector
            
        Returns:
            Similitud coseno (0-1)
        """
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)
    
    def find_similar_by_text(
        self, 
        query_text: str, 
        limit: int = 5,
        context_id: Optional[str] = None
    ) -> List[Dict]:
        """
        Encuentra recursos similares a un texto de búsqueda.
        
        Args:
            query_text: Texto de búsqueda
            limit: Número máximo de resultados
            context_id: Filtrar por contexto LTI (opcional)
            
        Returns:
            Lista de recursos similares con sus scores
        """
        from lti_recommender_project.apps.resources.models import EducationalResource
        
        try:
            # Generar embedding del query
            query_embedding = np.array(self.generate_embedding(query_text))
            
            if len(query_embedding) == 0:
                return []
            
            # Obtener candidatos
            candidates = EducationalResource.objects.filter(embedding__isnull=False)
            
            if context_id:
                candidates = candidates.filter(lti_context_id=context_id)
            
            similarities = []
            
            for candidate in candidates:
                try:
                    candidate_embedding = np.array(candidate.embedding)
                    similarity = self._cosine_similarity(query_embedding, candidate_embedding)
                    
                    similarities.append({
                        'resource': candidate,
                        'similarity': float(similarity)
                    })
                    
                except Exception as e:
                    logger.error(f"Error comparando query con recurso {candidate.id}: {e}")
                    continue
            
            # Ordenar y retornar top N
            similarities.sort(key=lambda x: x['similarity'], reverse=True)
            return similarities[:limit]
            
        except Exception as e:
            logger.error(f"Error en find_similar_by_text: {e}")
            return []


# Instancia global singleton del servicio
_embedding_service_instance = None


def get_embedding_service() -> EmbeddingService:
    """
    Obtiene la instancia singleton del servicio de embeddings.
    
    Returns:
        Instancia de EmbeddingService
    """
    global _embedding_service_instance
    
    if _embedding_service_instance is None:
        _embedding_service_instance = EmbeddingService()
    
    return _embedding_service_instance
