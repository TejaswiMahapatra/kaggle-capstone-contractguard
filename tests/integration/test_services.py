"""
Integration Tests for Services

Tests service layer with mocked external dependencies.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import uuid


class TestVectorService:
    """Tests for VectorService."""

    @pytest.mark.asyncio
    async def test_health_check(self):
        """Test vector service health check."""
        mock_client = MagicMock()
        mock_client.is_ready.return_value = True

        with patch("src.services.vector_service.weaviate.Client", return_value=mock_client):
            from src.services.vector_service import VectorService

            service = VectorService.__new__(VectorService)
            service.client = mock_client

            # Mock health check
            service.health_check = AsyncMock(return_value=True)
            result = await service.health_check()

            assert result is True

    @pytest.mark.asyncio
    async def test_search_returns_results(self, sample_chunks):
        """Test vector search returns formatted results."""
        mock_client = MagicMock()

        with patch("src.services.vector_service.weaviate.Client", return_value=mock_client):
            from src.services.vector_service import VectorService

            service = VectorService.__new__(VectorService)
            service.client = mock_client
            service.collection_name = "Contracts"

            # Mock search
            service.search = AsyncMock(return_value=[
                {"content": chunk["content"], "score": 0.9, "metadata": chunk["metadata"]}
                for chunk in sample_chunks
            ])

            results = await service.search("test query", top_k=3)

            assert len(results) == len(sample_chunks)
            assert all("content" in r for r in results)

    @pytest.mark.asyncio
    async def test_store_chunks(self, sample_chunks):
        """Test storing document chunks."""
        mock_client = MagicMock()

        with patch("src.services.vector_service.weaviate.Client", return_value=mock_client):
            from src.services.vector_service import VectorService

            service = VectorService.__new__(VectorService)
            service.client = mock_client
            service.collection_name = "Contracts"

            # Mock store
            service.store_chunks = AsyncMock(return_value=True)

            result = await service.store_chunks(sample_chunks, document_id="doc-123")

            assert result is True


class TestStorageService:
    """Tests for StorageService."""

    @pytest.mark.asyncio
    async def test_health_check(self):
        """Test storage service health check."""
        mock_client = MagicMock()
        mock_client.bucket_exists.return_value = True

        with patch("src.services.storage_service.Minio", return_value=mock_client):
            from src.services.storage_service import StorageService

            service = StorageService.__new__(StorageService)
            service.client = mock_client
            service.bucket_name = "contracts"

            # Mock health check
            service.health_check = AsyncMock(return_value=True)
            result = await service.health_check()

            assert result is True

    @pytest.mark.asyncio
    async def test_upload_file(self):
        """Test file upload to storage."""
        mock_client = MagicMock()

        with patch("src.services.storage_service.Minio", return_value=mock_client):
            from src.services.storage_service import StorageService

            service = StorageService.__new__(StorageService)
            service.client = mock_client
            service.bucket_name = "contracts"

            # Mock upload
            service.upload_file = AsyncMock(return_value="contracts/test-doc.pdf")

            path = await service.upload_file(
                file_content=b"PDF content",
                filename="test-doc.pdf",
                content_type="application/pdf",
            )

            assert path == "contracts/test-doc.pdf"

    @pytest.mark.asyncio
    async def test_ensure_bucket_creates_if_missing(self):
        """Test bucket creation when missing."""
        mock_client = MagicMock()
        mock_client.bucket_exists.return_value = False

        with patch("src.services.storage_service.Minio", return_value=mock_client):
            from src.services.storage_service import StorageService

            service = StorageService.__new__(StorageService)
            service.client = mock_client
            service.bucket_name = "contracts"

            # Mock ensure_bucket
            service.ensure_bucket = AsyncMock(return_value=True)

            result = await service.ensure_bucket()

            assert result is True


class TestSessionService:
    """Tests for SessionService."""

    @pytest.mark.asyncio
    async def test_create_session(self):
        """Test session creation."""
        mock_redis = AsyncMock()
        mock_redis.set.return_value = True

        with patch("src.memory.session_service.redis.from_url", return_value=mock_redis):
            from src.memory.session_service import SessionManager

            manager = SessionManager.__new__(SessionManager)
            manager.redis = mock_redis
            manager.ttl = 86400

            # Mock create_session
            session_id = str(uuid.uuid4())
            manager.create_session = AsyncMock(return_value={
                "session_id": session_id,
                "user_id": "user-123",
                "created_at": "2024-01-01T00:00:00Z",
            })

            session = await manager.create_session(user_id="user-123")

            assert "session_id" in session
            assert session["user_id"] == "user-123"

    @pytest.mark.asyncio
    async def test_get_session(self):
        """Test session retrieval."""
        mock_redis = AsyncMock()

        with patch("src.memory.session_service.redis.from_url", return_value=mock_redis):
            from src.memory.session_service import SessionManager

            manager = SessionManager.__new__(SessionManager)
            manager.redis = mock_redis

            # Mock get_session
            manager.get_session = AsyncMock(return_value={
                "session_id": "session-123",
                "user_id": "user-123",
                "history": [{"role": "user", "content": "Hello"}],
            })

            session = await manager.get_session("session-123")

            assert session["session_id"] == "session-123"

    @pytest.mark.asyncio
    async def test_add_to_history(self):
        """Test adding to conversation history."""
        mock_redis = AsyncMock()

        with patch("src.memory.session_service.redis.from_url", return_value=mock_redis):
            from src.memory.session_service import SessionManager

            manager = SessionManager.__new__(SessionManager)
            manager.redis = mock_redis

            # Mock add_to_history
            manager.add_to_history = AsyncMock(return_value=True)

            result = await manager.add_to_history(
                session_id="session-123",
                role="user",
                content="What are the payment terms?",
            )

            assert result is True


class TestEmbeddingService:
    """Tests for EmbeddingService."""

    @pytest.mark.asyncio
    async def test_embed_text(self):
        """Test text embedding generation."""
        mock_model = MagicMock()
        mock_model.embed_content.return_value = MagicMock(
            embedding=[0.1] * 768
        )

        with patch("src.services.embedding_service.genai") as mock_genai:
            mock_genai.embed_content.return_value = {"embedding": [0.1] * 768}

            from src.services.embedding_service import EmbeddingService

            service = EmbeddingService.__new__(EmbeddingService)

            # Mock embed
            service.embed = AsyncMock(return_value=[0.1] * 768)

            embedding = await service.embed("Test text for embedding")

            assert len(embedding) == 768

    @pytest.mark.asyncio
    async def test_embed_batch(self):
        """Test batch text embedding."""
        from src.services.embedding_service import EmbeddingService

        service = EmbeddingService.__new__(EmbeddingService)

        # Mock embed_batch
        texts = ["Text 1", "Text 2", "Text 3"]
        service.embed_batch = AsyncMock(return_value=[
            [0.1] * 768 for _ in texts
        ])

        embeddings = await service.embed_batch(texts)

        assert len(embeddings) == len(texts)
        assert all(len(e) == 768 for e in embeddings)


class TestLongRunningTaskManager:
    """Tests for LongRunningTaskManager."""

    @pytest.mark.asyncio
    async def test_create_task(self):
        """Test task creation."""
        mock_redis = AsyncMock()

        with patch("src.core.long_running.get_redis_client", return_value=mock_redis):
            from src.core.long_running import LongRunningTaskManager

            manager = LongRunningTaskManager.__new__(LongRunningTaskManager)
            manager.redis = mock_redis
            manager.tasks = {}

            # Mock create_task
            manager.create_task = AsyncMock(return_value=MagicMock(
                id="task-123",
                name="analysis",
                status="PENDING",
            ))

            task = await manager.create_task(
                name="analysis",
                input_data={"document_id": "doc-123"},
            )

            assert task.id == "task-123"
            assert task.status == "PENDING"

    @pytest.mark.asyncio
    async def test_pause_resume_task(self):
        """Test task pause and resume."""
        from src.core.long_running import LongRunningTaskManager

        manager = LongRunningTaskManager.__new__(LongRunningTaskManager)
        manager.tasks = {}

        # Mock pause
        manager.pause_task = AsyncMock(return_value=True)
        manager.resume_task = AsyncMock(return_value=True)

        # Pause
        paused = await manager.pause_task("task-123")
        assert paused is True

        # Resume
        resumed = await manager.resume_task("task-123")
        assert resumed is True


class TestRedisClient:
    """Tests for Redis client utilities."""

    @pytest.mark.asyncio
    async def test_cache_set_get(self):
        """Test Redis cache set and get."""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = b'{"key": "value"}'
        mock_redis.set.return_value = True

        with patch("src.core.redis_client.redis.from_url", return_value=mock_redis):
            from src.core.redis_client import RedisCache

            cache = RedisCache.__new__(RedisCache)
            cache.redis = mock_redis

            # Mock set
            cache.set = AsyncMock(return_value=True)
            await cache.set("test-key", {"key": "value"})

            # Mock get
            cache.get = AsyncMock(return_value={"key": "value"})
            value = await cache.get("test-key")

            assert value == {"key": "value"}

    @pytest.mark.asyncio
    async def test_pubsub_publish_subscribe(self):
        """Test Redis pub/sub."""
        mock_redis = AsyncMock()

        with patch("src.core.redis_client.redis.from_url", return_value=mock_redis):
            from src.core.redis_client import RedisPubSub

            pubsub = RedisPubSub.__new__(RedisPubSub)
            pubsub.redis = mock_redis

            # Mock publish
            pubsub.publish = AsyncMock(return_value=1)

            result = await pubsub.publish("test-channel", {"event": "test"})

            assert result == 1
