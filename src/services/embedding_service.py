"""
Embedding Service - Text to Vector Conversion

Supports multiple embedding providers:
- Google Gemini (text-embedding-004) - Recommended for production
- Local sentence-transformers (all-MiniLM-L6-v2) - For local development
"""

from abc import ABC, abstractmethod
from typing import Any

from src.config import settings
from src.observability.logger import get_logger
from src.observability.tracer import trace_operation

logger = get_logger(__name__, service="embedding")


class EmbeddingProvider(ABC):
    """Abstract base class for embedding providers."""

    @abstractmethod
    async def embed_text(self, text: str) -> list[float]:
        """Embed a single text string."""
        pass

    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts in batch."""
        pass

    @abstractmethod
    def get_dimension(self) -> int:
        """Get the embedding dimension."""
        pass


class GeminiEmbeddings(EmbeddingProvider):
    """
    Google Gemini embeddings using text-embedding-004.

    Produces 768-dimensional embeddings optimized for semantic similarity.
    """

    def __init__(self, model: str | None = None):
        """
        Initialize Gemini embeddings.

        Args:
            model: Model name (defaults to settings.gemini_embedding_model)
        """
        self.model = model or settings.gemini_embedding_model
        self._client: Any = None
        logger.info("GeminiEmbeddings initialized", model=self.model)

    @property
    def client(self) -> Any:
        """Lazy initialization of Gemini client."""
        if self._client is None:
            from google import genai

            self._client = genai.Client(api_key=settings.google_api_key)
        return self._client

    async def embed_text(self, text: str) -> list[float]:
        """Embed a single text using Gemini."""
        with trace_operation("embed_text_gemini"):
            try:
                result = await self.client.aio.models.embed_content(
                    model=self.model,
                    contents=text,
                )
                return result.embeddings[0].values
            except Exception as e:
                logger.error("Gemini embedding failed", error=str(e))
                raise

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts using Gemini."""
        with trace_operation("embed_batch_gemini", {"count": len(texts)}):
            try:
                # Gemini supports batch embedding
                result = await self.client.aio.models.embed_content(
                    model=self.model,
                    contents=texts,
                )
                embeddings = [e.values for e in result.embeddings]
                logger.info("Batch embedding complete", count=len(embeddings))
                return embeddings
            except Exception as e:
                logger.error("Gemini batch embedding failed", error=str(e))
                raise

    def get_dimension(self) -> int:
        """Gemini text-embedding-004 produces 768-dim vectors."""
        return 768


class LocalEmbeddings(EmbeddingProvider):
    """
    Local embeddings using sentence-transformers.

    Uses all-MiniLM-L6-v2 for 384-dimensional embeddings.
    No API calls required - runs entirely locally.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize local embeddings.

        Args:
            model_name: Sentence-transformers model name
        """
        self.model_name = model_name
        self._model: Any = None
        logger.info("LocalEmbeddings initialized", model=model_name)

    @property
    def model(self) -> Any:
        """Lazy initialization of sentence-transformers model."""
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)
            logger.info("Sentence-transformers model loaded")
        return self._model

    async def embed_text(self, text: str) -> list[float]:
        """Embed a single text locally."""
        with trace_operation("embed_text_local"):
            embedding = self.model.encode(text, convert_to_numpy=True)
            return embedding.tolist()

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts locally."""
        with trace_operation("embed_batch_local", {"count": len(texts)}):
            embeddings = self.model.encode(texts, convert_to_numpy=True)
            logger.info("Local batch embedding complete", count=len(embeddings))
            return embeddings.tolist()

    def get_dimension(self) -> int:
        """MiniLM produces 384-dim vectors."""
        return 384


class EmbeddingService:
    """
    High-level embedding service with provider abstraction.

    Automatically selects provider based on configuration:
    - Uses Gemini if GOOGLE_API_KEY is set
    - Falls back to local embeddings otherwise
    """

    def __init__(self, provider: EmbeddingProvider | None = None):
        """
        Initialize embedding service.

        Args:
            provider: Specific provider to use (auto-detected if None)
        """
        if provider:
            self.provider = provider
        elif settings.google_api_key:
            logger.info("Using Gemini embeddings (API key found)")
            self.provider = GeminiEmbeddings()
        else:
            logger.info("Using local embeddings (no API key)")
            self.provider = LocalEmbeddings()

    async def embed_query(self, query: str) -> list[float]:
        """
        Embed a search query.

        Args:
            query: User's search query

        Returns:
            Embedding vector for the query
        """
        return await self.provider.embed_text(query)

    async def embed_documents(self, documents: list[str]) -> list[list[float]]:
        """
        Embed multiple documents.

        Args:
            documents: List of document texts

        Returns:
            List of embedding vectors
        """
        if not documents:
            return []
        return await self.provider.embed_batch(documents)

    def get_dimension(self) -> int:
        """Get the embedding dimension for the current provider."""
        return self.provider.get_dimension()


# Singleton instance
_embedding_service: EmbeddingService | None = None


def get_embedding_service() -> EmbeddingService:
    """Get or create singleton EmbeddingService instance."""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service
