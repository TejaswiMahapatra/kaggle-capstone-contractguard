"""
Vector Service - Weaviate Integration

Provides semantic search capabilities using Weaviate vector database.
Supports both local development and cloud deployment.
"""

import uuid
from dataclasses import dataclass
from typing import Any

import weaviate
from weaviate.classes.config import Configure, Property, DataType, VectorDistances
from weaviate.classes.query import MetadataQuery, Filter

from src.config import settings
from src.observability.logger import get_logger
from src.observability.tracer import trace_operation

logger = get_logger(__name__, service="vector")


@dataclass
class SearchResult:
    """Represents a single search result from the vector database."""

    id: str
    text: str
    score: float
    metadata: dict[str, Any]


class VectorService:
    """
    High-level service for vector database operations.

    Provides:
    - Collection management (create, delete, check existence)
    - Document insertion with vectors
    - Semantic search with metadata filtering
    - Batch operations for efficiency
    """

    def __init__(self, url: str | None = None):
        """
        Initialize Weaviate client connection.

        Args:
            url: Weaviate instance URL (defaults to settings.weaviate_url)
        """
        self.url = url or settings.weaviate_url
        self._client: weaviate.WeaviateClient | None = None
        logger.info("VectorService initialized", url=self.url)

    @property
    def client(self) -> weaviate.WeaviateClient:
        """Lazy initialization of Weaviate client."""
        if self._client is None:
            # Parse URL for connection details
            # Default to localhost for development
            self._client = weaviate.connect_to_custom(
                http_host="localhost",
                http_port=8080,
                http_secure=False,
                grpc_host="localhost",
                grpc_port=50051,
                grpc_secure=False,
                skip_init_checks=True,
            )
            logger.info("Weaviate client connected")
        return self._client

    async def create_collection(
        self,
        collection_name: str,
        vector_dimension: int = 384,
        distance_metric: str = "cosine",
    ) -> bool:
        """
        Create a new collection for storing contract documents.

        Args:
            collection_name: Name of the collection
            vector_dimension: Embedding dimension (384 for MiniLM, 768 for Gemini)
            distance_metric: Distance function (cosine, euclidean, dot)

        Returns:
            True if created successfully
        """
        with trace_operation("create_collection", {"collection": collection_name}):
            try:
                # Define schema for contract documents
                properties = [
                    Property(name="text", data_type=DataType.TEXT),
                    Property(name="document_id", data_type=DataType.TEXT),
                    Property(name="chunk_index", data_type=DataType.INT),
                    Property(name="page_number", data_type=DataType.INT),
                    Property(name="clause_number", data_type=DataType.TEXT),
                    Property(name="chunk_type", data_type=DataType.TEXT),
                    Property(name="section_title", data_type=DataType.TEXT),
                    Property(name="parent_section", data_type=DataType.TEXT),
                    Property(name="hierarchy_level", data_type=DataType.INT),
                    Property(name="document_name", data_type=DataType.TEXT),
                ]

                distance_map = {
                    "cosine": VectorDistances.COSINE,
                    "euclidean": VectorDistances.L2_SQUARED,
                    "dot": VectorDistances.DOT,
                }

                self.client.collections.create(
                    name=collection_name,
                    properties=properties,
                    vectorizer_config=Configure.Vectorizer.none(),
                    vector_index_config=Configure.VectorIndex.hnsw(
                        distance_metric=distance_map.get(
                            distance_metric, VectorDistances.COSINE
                        )
                    ),
                )

                logger.info(
                    "Collection created",
                    collection=collection_name,
                    dimension=vector_dimension,
                )
                return True

            except Exception as e:
                logger.error("Failed to create collection", error=str(e))
                return False

    async def collection_exists(self, collection_name: str) -> bool:
        """Check if a collection exists."""
        try:
            return self.client.collections.exists(collection_name)
        except Exception:
            return False

    async def insert_documents(
        self,
        collection_name: str,
        texts: list[str],
        vectors: list[list[float]],
        metadata_list: list[dict[str, Any]],
    ) -> list[str]:
        """
        Insert documents with their embeddings into the collection.

        Args:
            collection_name: Target collection
            texts: Document text chunks
            vectors: Embedding vectors (same order as texts)
            metadata_list: Metadata for each chunk

        Returns:
            List of inserted document IDs
        """
        with trace_operation("insert_documents", {"count": len(texts)}):
            if not (len(texts) == len(vectors) == len(metadata_list)):
                raise ValueError("texts, vectors, and metadata_list must have same length")

            collection = self.client.collections.get(collection_name)
            ids = []

            logger.info(
                "Inserting documents",
                collection=collection_name,
                count=len(texts),
            )

            for i, (text, vector, meta) in enumerate(zip(texts, vectors, metadata_list)):
                try:
                    object_id = str(uuid.uuid4())

                    properties = {
                        "text": text,
                        "document_id": str(meta.get("document_id", "")),
                        "chunk_index": int(meta.get("chunk_index", i)),
                        "page_number": int(meta.get("page_number", 0)),
                        "clause_number": str(meta.get("clause_number", "")),
                        "chunk_type": str(meta.get("chunk_type", "text")),
                        "section_title": str(meta.get("section_title", "")),
                        "parent_section": str(meta.get("parent_section", "")),
                        "hierarchy_level": int(meta.get("hierarchy_level", 0)),
                        "document_name": str(meta.get("document_name", "")),
                    }

                    result_uuid = collection.data.insert(
                        properties=properties,
                        vector=vector,
                        uuid=object_id,
                    )
                    ids.append(str(result_uuid))

                except Exception as e:
                    logger.error(f"Failed to insert document {i}", error=str(e))
                    continue

            logger.info("Documents inserted", count=len(ids))
            return ids

    async def search(
        self,
        collection_name: str,
        query_vector: list[float],
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """
        Semantic search for similar documents.

        Args:
            collection_name: Collection to search
            query_vector: Query embedding vector
            top_k: Number of results to return
            filters: Optional metadata filters (e.g., {"document_id": "abc"})

        Returns:
            List of SearchResult objects with text, score, and metadata
        """
        with trace_operation("vector_search", {"top_k": top_k}):
            try:
                collection = self.client.collections.get(collection_name)

                # Build filter if provided
                weaviate_filter = None
                if filters:
                    filter_conditions = []
                    for key, value in filters.items():
                        filter_conditions.append(
                            Filter.by_property(key).equal(value)
                        )
                    if len(filter_conditions) == 1:
                        weaviate_filter = filter_conditions[0]
                    else:
                        weaviate_filter = Filter.all_of(filter_conditions)

                response = collection.query.near_vector(
                    near_vector=query_vector,
                    limit=top_k,
                    filters=weaviate_filter,
                    return_metadata=MetadataQuery(distance=True),
                )

                results = []
                for obj in response.objects:
                    props = obj.properties
                    metadata = {
                        "document_id": props.get("document_id", ""),
                        "chunk_index": props.get("chunk_index", 0),
                        "page_number": props.get("page_number", 0),
                        "clause_number": props.get("clause_number", ""),
                        "chunk_type": props.get("chunk_type", ""),
                        "section_title": props.get("section_title", ""),
                        "parent_section": props.get("parent_section", ""),
                        "hierarchy_level": props.get("hierarchy_level", 0),
                        "document_name": props.get("document_name", ""),
                    }

                    # Convert distance to similarity score (1 - distance for cosine)
                    score = 1.0 - obj.metadata.distance if obj.metadata.distance else 0.0

                    results.append(
                        SearchResult(
                            id=str(obj.uuid),
                            text=props.get("text", ""),
                            score=score,
                            metadata=metadata,
                        )
                    )

                logger.info("Search completed", results=len(results))
                return results

            except Exception as e:
                logger.error("Search failed", error=str(e))
                return []

    async def get_by_document_id(
        self,
        collection_name: str,
        document_id: str,
    ) -> list[SearchResult]:
        """
        Get all chunks for a specific document.

        Args:
            collection_name: Collection to search
            document_id: ID of the document

        Returns:
            All chunks belonging to the document, ordered by chunk_index
        """
        with trace_operation("get_by_document_id", {"document_id": document_id}):
            try:
                collection = self.client.collections.get(collection_name)

                response = collection.query.fetch_objects(
                    filters=Filter.by_property("document_id").equal(document_id),
                    limit=1000,  # Get all chunks
                )

                results = []
                for obj in response.objects:
                    props = obj.properties
                    results.append(
                        SearchResult(
                            id=str(obj.uuid),
                            text=props.get("text", ""),
                            score=1.0,  # No relevance score for direct fetch
                            metadata={
                                "document_id": props.get("document_id", ""),
                                "chunk_index": props.get("chunk_index", 0),
                                "page_number": props.get("page_number", 0),
                                "clause_number": props.get("clause_number", ""),
                                "section_title": props.get("section_title", ""),
                            },
                        )
                    )

                # Sort by chunk index
                results.sort(key=lambda x: x.metadata.get("chunk_index", 0))

                logger.info(
                    "Retrieved document chunks",
                    document_id=document_id,
                    count=len(results),
                )
                return results

            except Exception as e:
                logger.error("Failed to get document", error=str(e))
                return []

    async def delete_collection(self, collection_name: str) -> bool:
        """Delete an entire collection."""
        try:
            self.client.collections.delete(collection_name)
            logger.info("Collection deleted", collection=collection_name)
            return True
        except Exception as e:
            logger.error("Failed to delete collection", error=str(e))
            return False

    async def get_collection_stats(self, collection_name: str) -> dict[str, Any]:
        """Get statistics about a collection."""
        try:
            collection = self.client.collections.get(collection_name)
            aggregate = collection.aggregate.over_all(total_count=True)

            return {
                "name": collection_name,
                "count": aggregate.total_count,
                "exists": True,
            }
        except Exception as e:
            logger.error("Failed to get stats", error=str(e))
            return {"name": collection_name, "count": 0, "exists": False}

    async def health_check(self, retries: int = 3, delay: float = 1.0) -> bool:
        """Check if Weaviate is healthy with retries."""
        import asyncio

        for attempt in range(retries):
            try:
                if self.client.is_ready():
                    return True
            except Exception:
                pass

            if attempt < retries - 1:
                await asyncio.sleep(delay)

        return False

    def close(self) -> None:
        """Close the Weaviate client connection."""
        if self._client:
            self._client.close()
            self._client = None
            logger.info("Weaviate client closed")


# Singleton instance
_vector_service: VectorService | None = None


def get_vector_service() -> VectorService:
    """Get or create singleton VectorService instance."""
    global _vector_service
    if _vector_service is None:
        _vector_service = VectorService()
    return _vector_service
