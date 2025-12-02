"""
Pytest Configuration and Fixtures

Shared fixtures for ContractGuard AI tests.
"""

import asyncio
import os
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport

# Set test environment before importing app
os.environ["APP_ENV"] = "development"
os.environ["GOOGLE_API_KEY"] = "test-api-key"
os.environ["DEBUG"] = "true"


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_settings():
    """Mock settings for testing."""
    from src.config import Settings

    return Settings(
        app_env="development",
        google_api_key="test-api-key",
        weaviate_url="http://localhost:8080",
        redis_url="redis://localhost:6379",
        minio_endpoint="localhost:9000",
        minio_access_key="minioadmin",
        minio_secret_key="minioadmin",
        postgres_host="localhost",
        postgres_port=5432,
        postgres_user="postgres",
        postgres_password="postgres",
        postgres_db="contractguard_test",
    )


@pytest.fixture
def mock_vector_service():
    """Mock vector service for testing."""
    mock = AsyncMock()
    mock.health_check.return_value = True
    mock.search.return_value = [
        {
            "content": "Test clause content about termination.",
            "metadata": {"clause_number": "5.1", "document_id": "test-doc-1"},
            "score": 0.95,
        }
    ]
    mock.store_chunks.return_value = True
    mock.close.return_value = None
    return mock


@pytest.fixture
def mock_storage_service():
    """Mock storage service for testing."""
    mock = AsyncMock()
    mock.health_check.return_value = True
    mock.ensure_bucket.return_value = True
    mock.upload_file.return_value = "contracts/test-doc-1.pdf"
    mock.get_file.return_value = b"PDF content"
    return mock


@pytest.fixture
def mock_session_manager():
    """Mock session manager for testing."""
    mock = AsyncMock()
    mock.create_session.return_value = {
        "session_id": "test-session-123",
        "user_id": "test-user-1",
        "created_at": "2024-01-01T00:00:00Z",
    }
    mock.get_session.return_value = {
        "session_id": "test-session-123",
        "user_id": "test-user-1",
        "history": [],
    }
    mock.close.return_value = None
    return mock


@pytest.fixture
def mock_redis():
    """Mock Redis client for testing."""
    mock = AsyncMock()
    mock.ping.return_value = True
    mock.get.return_value = None
    mock.set.return_value = True
    mock.delete.return_value = True
    return mock


@pytest.fixture
def mock_gemini():
    """Mock Gemini LLM responses."""
    mock = MagicMock()
    mock.generate_content.return_value = MagicMock(
        text="This is a test response about contract analysis."
    )
    return mock


@pytest.fixture
def sample_contract_text() -> str:
    """Sample contract text for testing."""
    return """
    NON-DISCLOSURE AGREEMENT

    1. DEFINITIONS
    1.1 "Confidential Information" means any non-public information disclosed by either party.

    2. OBLIGATIONS
    2.1 The Receiving Party agrees to hold all Confidential Information in strict confidence.
    2.2 The Receiving Party shall not disclose Confidential Information to third parties.

    3. TERM AND TERMINATION
    3.1 This Agreement shall remain in effect for three (3) years.
    3.2 Either party may terminate with thirty (30) days written notice.

    4. LIABILITY
    4.1 The total liability shall not exceed $500,000.
    """


@pytest.fixture
def sample_chunks() -> list[dict]:
    """Sample document chunks for testing."""
    return [
        {
            "content": "1. DEFINITIONS\n1.1 \"Confidential Information\" means any non-public information.",
            "metadata": {
                "chunk_index": 0,
                "clause_number": "1.1",
                "section": "DEFINITIONS",
                "page": 1,
            },
        },
        {
            "content": "2. OBLIGATIONS\n2.1 The Receiving Party agrees to hold all Confidential Information in strict confidence.",
            "metadata": {
                "chunk_index": 1,
                "clause_number": "2.1",
                "section": "OBLIGATIONS",
                "page": 1,
            },
        },
        {
            "content": "3. TERM AND TERMINATION\n3.1 This Agreement shall remain in effect for three (3) years.",
            "metadata": {
                "chunk_index": 2,
                "clause_number": "3.1",
                "section": "TERM AND TERMINATION",
                "page": 2,
            },
        },
    ]


@pytest.fixture
def app_with_mocks(mock_vector_service, mock_storage_service, mock_session_manager, mock_redis):
    """Create FastAPI app with mocked services."""
    with patch("src.services.vector_service.get_vector_service", return_value=mock_vector_service), \
         patch("src.services.storage_service.get_storage_service", return_value=mock_storage_service), \
         patch("src.memory.session_service.get_session_manager", return_value=mock_session_manager), \
         patch("src.core.redis_client.check_redis_health", return_value=True), \
         patch("src.core.redis_client.close_redis", return_value=None), \
         patch("src.core.database.check_db_health", return_value=False):
        from src.main import app
        yield app


@pytest.fixture
def test_client(app_with_mocks) -> TestClient:
    """Create test client for sync tests."""
    return TestClient(app_with_mocks)


@pytest_asyncio.fixture
async def async_client(app_with_mocks) -> AsyncGenerator[AsyncClient, None]:
    """Create async test client."""
    transport = ASGITransport(app=app_with_mocks)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


# Test data fixtures
@pytest.fixture
def test_query_request() -> dict:
    """Sample query request."""
    return {
        "question": "What are the termination conditions?",
        "session_id": "test-session-123",
    }


@pytest.fixture
def test_upload_file() -> bytes:
    """Sample PDF-like content for upload testing."""
    # Minimal PDF header for testing
    return b"%PDF-1.4\nTest PDF content\n%%EOF"


@pytest.fixture
def test_document_metadata() -> dict:
    """Sample document metadata."""
    return {
        "id": "test-doc-123",
        "filename": "test_contract.pdf",
        "original_filename": "Test Contract.pdf",
        "content_type": "application/pdf",
        "file_size": 1024,
        "status": "COMPLETED",
        "chunk_count": 10,
        "page_count": 5,
    }
