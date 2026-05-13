"""
Servicio de Embeddings Semánticos — v2
- Modelo multilingual: paraphrase-multilingual-mpnet-base-v2 (768 dims)
- Batch encoding para eficiencia (~10x más rápido que individual)
- Actualización incremental (solo recursos nuevos/modificados)
- Búsqueda vectorial nativa con pgvector CosineDistance (O(log n) con HNSW)
"""

import logging
import numpy as np
from typing import List, Dict, Optional, Tuple
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

# Flag to detect if pgvector is available
try:
    from pgvector.django import CosineDistance
    PGVECTOR_AVAILABLE = True
except ImportError:
    PGVECTOR_AVAILABLE = False
    CosineDistance = None
    logger.warning("pgvector not installed — falling back to in-memory cosine similarity")


class EmbeddingService:
    """
    Servicio de embeddings para recursos educativos.
    
    Modelo: paraphrase-multilingual-mpnet-base-v2
    - 768 dimensiones
    - Soporte para 50+ idiomas incluyendo español
    - Fine-tuned para paraphrase/similitud semántica
    
    Referente: Coursera usa modelos multilingüe para catálogos globales.
    """

    def __init__(self):
        self.model_name = getattr(
            settings,
            'EMBEDDING_MODEL',
            'paraphrase-multilingual-mpnet-base-v2'
        )
        self.embedding_dim = getattr(
            settings,
            'RECOMMENDATION_CONFIG',
            {}
        ).get('EMBEDDING_DIMENSION', 768)
        self._model = None

    @property
    def model(self):
        """Getter perezoso para el modelo."""
        if self._model is None:
            self._load_model()
        return self._model

    def _load_model(self):
        """Carga el modelo de Sentence Transformers de forma diferida."""
        if self._model is not None:
            return
        try:
            from sentence_transformers import SentenceTransformer
            logger.info(f"INICIO: Cargando modelo pesado {self.model_name}...")
            self._model = SentenceTransformer(self.model_name)
            logger.info(f"ÉXITO: Modelo cargado — dim: {self.embedding_dim}")
        except ImportError:
            logger.error("sentence-transformers no está instalado.")
            raise
        except Exception as e:
            logger.error(f"Error FATAL al cargar el modelo: {e}")
            raise

    def generate_embedding(self, text: str) -> List[float]:
        """Genera un embedding para un texto dado."""
        if not text or not text.strip():
            return []
        try:
            embedding = self.model.encode(text, convert_to_numpy=True, normalize_embeddings=True)
            return embedding.tolist()
        except Exception as e:
            logger.error(f"Error al generar embedding: {e}")
            return []

    def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Genera embeddings en batch — ~10x más rápido que individual.
        Los textos vacíos retornan listas vacías.
        """
        if not texts:
            return []
        try:
            embeddings = self.model.encode(
                texts,
                batch_size=32,
                show_progress_bar=False,
                convert_to_numpy=True,
                normalize_embeddings=True,
            )
            return [e.tolist() for e in embeddings]
        except Exception as e:
            logger.error(f"Error en batch encoding: {e}")
            return [[] for _ in texts]

    def update_embeddings_incremental(self, batch_size: int = 32) -> Tuple[int, int]:
        """
        Actualización INCREMENTAL: solo procesa recursos sin embedding
        o cuyo updated_at > embedding_updated_at.
        
        Mucho más eficiente que re-generar todos los embeddings.
        """
        from lti_recommender_project.apps.resources.models import EducationalResource
        import django.db.models as db_models

        # Solo recursos que necesitan (re)generación
        needs_update = EducationalResource.objects.filter(
            db_models.Q(embedding__isnull=True) |
            db_models.Q(embedding_updated_at__isnull=True) |
            db_models.Q(updated_at__gt=db_models.F('embedding_updated_at'))
        )

        total = needs_update.count()
        logger.info(f"Embeddings a actualizar: {total} recursos")
        updated, failed = 0, 0

        # ⚠️ CRÍTICO: recoger IDs PRIMERO antes de actualizar.
        # Si iteramos con offset sobre el queryset vivo, los registros
        # actualizados salen del filtro → offset se desplaza → se saltan recursos.
        resource_ids = list(needs_update.values_list('id', flat=True))

        for i in range(0, len(resource_ids), batch_size):
            batch_ids = resource_ids[i:i + batch_size]
            batch = list(EducationalResource.objects.filter(id__in=batch_ids))
            texts = [r.get_embedding_text() for r in batch]

            try:
                embeddings = self.generate_embeddings_batch(texts)

                for resource, emb in zip(batch, embeddings):
                    if emb:
                        resource.embedding = emb
                        resource.embedding_model_version = self.model_name
                        resource.embedding_updated_at = timezone.now()

                EducationalResource.objects.bulk_update(
                    [r for r, e in zip(batch, embeddings) if e],
                    ['embedding', 'embedding_model_version', 'embedding_updated_at'],
                    batch_size=batch_size,
                )
                successful = sum(1 for e in embeddings if e)
                updated += successful
                failed += len(batch) - successful

                logger.info(f"Batch {i}–{i + batch_size}: {successful}/{len(batch)} OK")

            except Exception as e:
                logger.error(f"Error en batch {i}: {e}")
                failed += len(batch)

        logger.info(f"Embeddings: {updated} actualizados, {failed} fallidos")
        return updated, failed

    def update_resource_embeddings(self, force_update: bool = False) -> Tuple[int, int]:
        """
        Compatibilidad con código anterior.
        force_update=True re-genera todos los embeddings.
        """
        if force_update:
            from lti_recommender_project.apps.resources.models import EducationalResource
            EducationalResource.objects.all().update(embedding=None, embedding_updated_at=None)
        return self.update_embeddings_incremental()

    def get_similar_resources_pgvector(
        self,
        query_embedding: List[float],
        limit: int = 10,
        context_id: Optional[str] = None,
        exclude_ids: Optional[set] = None,
        min_similarity: float = 0.3,
    ) -> List[Dict]:
        """
        Búsqueda vectorial nativa con pgvector — O(log n) con HNSW.
        Mucho más rápido que calcular coseno en Python (O(n)).
        """
        from lti_recommender_project.apps.resources.models import EducationalResource
        from django.db.models import Q

        if not PGVECTOR_AVAILABLE:
            logger.warning("pgvector no disponible — usando búsqueda en memoria")
            return self._get_similar_resources_inmemory(
                np.array(query_embedding), limit, context_id, exclude_ids, min_similarity
            )

        qs = EducationalResource.objects.filter(embedding__isnull=False)

        if context_id:
            qs = qs.filter(
                Q(lti_context_id=context_id) | Q(lti_context_id__isnull=True)
            )

        if exclude_ids:
            qs = qs.exclude(id__in=exclude_ids)

        # Distancia coseno < (1 - min_similarity): similitud ≥ min_similarity
        max_distance = 1.0 - min_similarity

        results = (
            qs
            .annotate(distance=CosineDistance('embedding', query_embedding))
            .filter(distance__lt=max_distance)
            .order_by('distance')[:limit]
        )

        return [
            {
                'id': r.id,
                'title': r.title,
                'url': r.url,
                'description': r.description,
                'type': r.resource_type,
                'difficulty': r.difficulty_level,
                'tags': r.tags or '',
                'score': float(1.0 - r.distance),  # Convertir distancia → similitud
                'source': 'content_embedding',
            }
            for r in results
        ]

    def get_similar_resources(
        self,
        resource_id: int,
        limit: int = 5,
        min_similarity: float = 0.3,
    ) -> List[Dict]:
        """Encuentra recursos similares a un recurso dado."""
        from lti_recommender_project.apps.resources.models import EducationalResource

        try:
            source = EducationalResource.objects.get(id=resource_id)
        except EducationalResource.DoesNotExist:
            return []

        if not source.embedding:
            logger.warning(f"Recurso {resource_id} sin embedding")
            return []

        embedding = source.embedding if isinstance(source.embedding, list) else list(source.embedding)
        return self.get_similar_resources_pgvector(
            query_embedding=embedding,
            limit=limit,
            min_similarity=min_similarity,
            exclude_ids={resource_id},
        )

    def find_similar_by_text(
        self,
        query_text: str,
        limit: int = 5,
        context_id: Optional[str] = None,
        min_similarity: float = 0.2,
    ) -> List[Dict]:
        """Busca recursos similares a un texto de búsqueda."""
        query_embedding = self.generate_embedding(query_text)
        if not query_embedding:
            return []

        return self.get_similar_resources_pgvector(
            query_embedding=query_embedding,
            limit=limit,
            context_id=context_id,
            min_similarity=min_similarity,
        )

    def _get_similar_resources_inmemory(
        self,
        query_vec: np.ndarray,
        limit: int,
        context_id: Optional[str],
        exclude_ids: Optional[set],
        min_similarity: float,
    ) -> List[Dict]:
        """Fallback cuando pgvector no está disponible — O(n) en memoria."""
        from lti_recommender_project.apps.resources.models import EducationalResource
        from django.db.models import Q

        qs = EducationalResource.objects.filter(embedding__isnull=False)
        if context_id:
            qs = qs.filter(Q(lti_context_id=context_id) | Q(lti_context_id__isnull=True))
        if exclude_ids:
            qs = qs.exclude(id__in=exclude_ids)

        results = []
        for r in qs:
            try:
                candidate_vec = np.array(r.embedding)
                sim = float(np.dot(query_vec, candidate_vec))  # Already normalized
                if sim >= min_similarity:
                    results.append({
                        'id': r.id,
                        'title': r.title,
                        'url': r.url,
                        'description': r.description,
                        'type': r.resource_type,
                        'difficulty': r.difficulty_level,
                        'tags': r.tags or '',
                        'score': sim,
                        'source': 'content_embedding',
                    })
            except Exception:
                continue

        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:limit]

    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Compatibilidad con código anterior."""
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return float(np.dot(vec1, vec2) / (norm1 * norm2))


# Singleton
_embedding_service_instance: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    """Obtiene la instancia singleton del servicio de embeddings."""
    global _embedding_service_instance
    if _embedding_service_instance is None:
        _embedding_service_instance = EmbeddingService()
    return _embedding_service_instance
