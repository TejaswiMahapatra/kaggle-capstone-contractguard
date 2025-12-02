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
        mock_weaviate_client = MagicMock()
        mock_weaviate_client.is_ready.return_value = True

        with patch("src.services.vector_service.weaviate") as mock_weaviate:
            mock_weaviate.connect_to_custom.return_value = mock_weaviate_client

            from src.services.vector_service import VectorService

            service = VectorService.__new__(VectorService)
            service._client = mock_weaviate_client
            service.url = "http://localhost:8080"

            # Mock health check
            service.health_check = AsyncMock(return_value=True)
            result = await service.health_check()

            assert result is True

    @pytest.mark.asyncio
    async def test_search_returns_results(self, sample_chunks):
        """Test vector search returns formatted results."""
        mock_weaviate_client = MagicMock()

        with patch("src.services.vector_service.weaviate") as mock_weaviate:
            mock_weaviate.connect_to_custom.return_value = mock_weaviate_client

            from src.services.vector_service import VectorService, SearchResult

            service = VectorService.__new__(VectorService)
            service._client = mock_weaviate_client
            service.url = "http://localhost:8080"

            # Mock search to return SearchResult objects
            service.search = AsyncMock(return_value=[
                SearchResult(
                    id=f"id-{i}",
                    text=chunk["content"],
                    score=0.9,
                    metadata=chunk["metadata"]
                )
                for i, chunk in enumerate(sample_chunks)
            ])

            results = await service.search(
                collection_name="contracts",
                query_vector=[0.1] * 384,
                top_k=3,
            )

            assert len(results) == len(sample_chunks)
            assert all(hasattr(r, "text") for r in results)

    @pytest.mark.asyncio
    async def test_insert_documents(self, sample_chunks):
        """Test inserting document chunks."""
        mock_weaviate_client = MagicMock()

        with patch("src.services.vector_service.weaviate") as mock_weaviate:
            mock_weaviate.connect_to_custom.return_value = mock_weaviate_client

            from src.services.vector_service import VectorService

            service = VectorService.__new__(VectorService)
            service._client = mock_weaviate_client
            service.url = "http://localhost:8080"

            # Mock insert_documents
            service.insert_documents = AsyncMock(return_value=["id-1", "id-2"])

            texts = [chunk["content"] for chunk in sample_chunks]
            vectors = [[0.1] * 384 for _ in sample_chunks]
            metadata_list = [chunk["metadata"] for chunk in sample_chunks]

            result = await service.insert_documents(
                collection_name="contracts",
                texts=texts,
                vectors=vectors,
                metadata_list=metadata_list,
            )

            assert len(result) == 2


class TestStorageService:
    """Tests for StorageService."""

    @pytest.mark.asyncio
    async def test_health_check(self):
        """Test storage service health check."""
        mock_minio_client = MagicMock()
        mock_minio_client.list_buckets.return_value = []

        with patch("src.services.storage_service.Minio", return_value=mock_minio_client):
            from src.services.storage_service import StorageService

            service = StorageService.__new__(StorageService)
            service._client = mock_minio_client
            service.endpoint = "localhost:9000"
            service.access_key = "minioadmin"
            service.secret_key = "minioadmin"
            service.secure = False

            # Mock health check
            service.health_check = AsyncMock(return_value=True)
            result = await service.health_check()

            assert result is True

    @pytest.mark.asyncio
    async def test_upload_document(self):
        """Test document upload to storage."""
        mock_minio_client = MagicMock()
        mock_minio_client.bucket_exists.return_value = True
        mock_minio_client.put_object.return_value = MagicMock(etag="abc123")

        with patch("src.services.storage_service.Minio", return_value=mock_minio_client):
            from src.services.storage_service import StorageService, StoredDocument

            service = StorageService.__new__(StorageService)
            service._client = mock_minio_client
            service.endpoint = "localhost:9000"
            service.access_key = "minioadmin"
            service.secret_key = "minioadmin"
            service.secure = False

            # Mock upload_document
            service.upload_document = AsyncMock(return_value=StoredDocument(
                object_name="doc-123.pdf",
                bucket="contracts",
                size=1024,
                content_type="application/pdf",
                etag="abc123",
                metadata={"document_id": "doc-123", "original_filename": "test.pdf"},
            ))

            result = await service.upload_document(
                file_data=b"PDF content",
                filename="test.pdf",
                document_id="doc-123",
            )

            assert result.object_name == "doc-123.pdf"
            assert result.bucket == "contracts"

    @pytest.mark.asyncio
    async def test_ensure_bucket_creates_if_missing(self):
        """Test bucket creation when missing."""
        mock_minio_client = MagicMock()
        mock_minio_client.bucket_exists.return_value = False

        with patch("src.services.storage_service.Minio", return_value=mock_minio_client):
            from src.services.storage_service import StorageService

            service = StorageService.__new__(StorageService)
            service._client = mock_minio_client
            service.endpoint = "localhost:9000"
            service.access_key = "minioadmin"
            service.secret_key = "minioadmin"
            service.secure = False

            # Mock ensure_bucket
            service.ensure_bucket = AsyncMock(return_value=True)

            result = await service.ensure_bucket()

            assert result is True


class TestSessionService:
    """Tests for SessionManager."""

    @pytest.mark.asyncio
    async def test_create_session(self):
        """Test session creation."""
        mock_redis = AsyncMock()
        mock_redis.setex.return_value = True
        mock_redis.expire.return_value = True

        from src.memory.session_service import SessionManager, SessionContext

        manager = SessionManager.__new__(SessionManager)
        manager._redis = mock_redis
        manager.session_ttl = 86400
        manager.redis_url = "redis://localhost:6379"

        # Mock create_session to return a SessionContext
        session_id = str(uuid.uuid4())
        manager.create_session = AsyncMock(return_value=SessionContext(
            session_id=session_id,
            user_id="user-123",
            active_documents=[],
        ))

        session = await manager.create_session(user_id="user-123")

        assert session.session_id == session_id
        assert session.user_id == "user-123"

    @pytest.mark.asyncio
    async def test_get_session(self):
        """Test session retrieval."""
        mock_redis = AsyncMock()

        from src.memory.session_service import SessionManager, SessionContext

        manager = SessionManager.__new__(SessionManager)
        manager._redis = mock_redis
        manager.session_ttl = 86400
        manager.redis_url = "redis://localhost:6379"

        # Mock get_session to return a SessionContext
        manager.get_session = AsyncMock(return_value=SessionContext(
            session_id="session-123",
            user_id="user-123",
            active_documents=[],
        ))

        session = await manager.get_session("session-123")

        assert session.session_id == "session-123"

    @pytest.mark.asyncio
    async def test_add_message(self):
        """Test adding message to conversation history."""
        mock_redis = AsyncMock()
        mock_redis.exists.return_value = True
        mock_redis.rpush.return_value = 1
        mock_redis.expire.return_value = True

        from src.memory.session_service import SessionManager

        manager = SessionManager.__new__(SessionManager)
        manager._redis = mock_redis
        manager.session_ttl = 86400
        manager.redis_url = "redis://localhost:6379"

        # Mock add_message
        manager.add_message = AsyncMock(return_value=True)

        result = await manager.add_message(
            session_id="session-123",
            role="user",
            content="What are the payment terms?",
        )

        assert result is True


class TestEmbeddingService:
    """Tests for EmbeddingService."""

    @pytest.mark.asyncio
    async def test_embed_query(self):
        """Test query embedding generation."""
        from src.services.embedding_service import EmbeddingService

        service = EmbeddingService.__new__(EmbeddingService)

        # Mock provider
        mock_provider = MagicMock()
        mock_provider.embed_text = AsyncMock(return_value=[0.1] * 768)
        mock_provider.get_dimension.return_value = 768
        service.provider = mock_provider

        embedding = await service.embed_query("Test text for embedding")

        assert len(embedding) == 768
        mock_provider.embed_text.assert_called_once_with("Test text for embedding")

    @pytest.mark.asyncio
    async def test_embed_documents(self):
        """Test batch document embedding."""
        from src.services.embedding_service import EmbeddingService

        service = EmbeddingService.__new__(EmbeddingService)

        # Mock provider
        mock_provider = MagicMock()
        texts = ["Text 1", "Text 2", "Text 3"]
        mock_provider.embed_batch = AsyncMock(return_value=[
            [0.1] * 768 for _ in texts
        ])
        mock_provider.get_dimension.return_value = 768
        service.provider = mock_provider

        embeddings = await service.embed_documents(texts)

        assert len(embeddings) == len(texts)
        assert all(len(e) == 768 for e in embeddings)
        mock_provider.embed_batch.assert_called_once_with(texts)


class TestLongRunningTaskManager:
    """Tests for LongRunningTaskManager."""

    @pytest.mark.asyncio
    async def test_create_task(self):
        """Test task creation."""
        mock_pubsub = MagicMock()
        mock_pubsub.publish = AsyncMock(return_value=1)
        mock_cache = MagicMock()
        mock_cache.set = AsyncMock(return_value=True)

        with patch("src.core.long_running.get_redis_pubsub", return_value=mock_pubsub), \
             patch("src.core.long_running.RedisCache", return_value=mock_cache):
            from src.core.long_running import LongRunningTaskManager, LongRunningTask, TaskStatus

            manager = LongRunningTaskManager.__new__(LongRunningTaskManager)
            manager.tasks = {}
            manager.pubsub = mock_pubsub
            manager.cache = mock_cache
            manager._executors = {}
            manager._pause_events = {}

            # Mock create_task to return a LongRunningTask
            manager.create_task = AsyncMock(return_value=LongRunningTask(
                id="task-123",
                name="analysis",
                status=TaskStatus.PENDING,
            ))

            task = await manager.create_task(
                name="analysis",
                input_data={"document_id": "doc-123"},
            )

            assert task.id == "task-123"
            assert task.status == TaskStatus.PENDING

    @pytest.mark.asyncio
    async def test_pause_resume_task(self):
        """Test task pause and resume."""
        mock_pubsub = MagicMock()
        mock_pubsub.publish = AsyncMock(return_value=1)
        mock_cache = MagicMock()

        with patch("src.core.long_running.get_redis_pubsub", return_value=mock_pubsub), \
             patch("src.core.long_running.RedisCache", return_value=mock_cache):
            from src.core.long_running import LongRunningTaskManager

            manager = LongRunningTaskManager.__new__(LongRunningTaskManager)
            manager.tasks = {}
            manager.pubsub = mock_pubsub
            manager.cache = mock_cache
            manager._executors = {}
            manager._pause_events = {}

            # Mock pause and resume
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
        mock_redis.get.return_value = '{"key": "value"}'
        mock_redis.set.return_value = True
        mock_redis.setex.return_value = True

        with patch("src.core.redis_client.get_redis", return_value=mock_redis):
            from src.core.redis_client import RedisCache

            cache = RedisCache.__new__(RedisCache)
            cache.redis = mock_redis
            cache.prefix = "cache"

            # Mock set
            cache.set = AsyncMock(return_value=True)
            await cache.set("test-key", {"key": "value"})

            # Mock get
            cache.get = AsyncMock(return_value={"key": "value"})
            value = await cache.get("test-key")

            assert value == {"key": "value"}

    @pytest.mark.asyncio
    async def test_pubsub_publish(self):
        """Test Redis pub/sub publish."""
        mock_redis = AsyncMock()
        mock_redis.publish.return_value = 1

        with patch("src.core.redis_client.get_redis", return_value=mock_redis):
            from src.core.redis_client import RedisPubSub

            pubsub = RedisPubSub.__new__(RedisPubSub)
            pubsub.redis = mock_redis

            # Mock publish
            pubsub.publish = AsyncMock(return_value=1)

            result = await pubsub.publish("test-channel", {"event": "test"})

            assert result == 1
