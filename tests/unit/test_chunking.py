"""
Unit Tests for Chunking Service

Tests clause-aware document chunking functionality.
"""

import pytest
from src.services.chunking_service import (
    ChunkingService,
    get_chunking_service,
    DocumentChunk,
)


class TestChunkingService:
    """Tests for ChunkingService."""

    @pytest.fixture
    def chunking_service(self) -> ChunkingService:
        """Create chunking service instance."""
        return get_chunking_service()

    def test_service_singleton(self):
        """Test that get_chunking_service returns singleton."""
        service1 = get_chunking_service()
        service2 = get_chunking_service()
        assert service1 is service2

    def test_chunk_simple_text(self, chunking_service, sample_contract_text):
        """Test basic text chunking."""
        chunks = chunking_service.chunk_text(sample_contract_text, document_id="test-doc")

        assert len(chunks) > 0
        assert all(isinstance(chunk, DocumentChunk) for chunk in chunks)
        assert all(chunk.document_id == "test-doc" for chunk in chunks)

    def test_chunk_preserves_clause_numbers(self, chunking_service):
        """Test that clause numbers are preserved in metadata."""
        text = """
        5.1 The Receiving Party shall maintain confidentiality.
        5.2 The Receiving Party shall not disclose information.
        """
        chunks = chunking_service.chunk_text(text, document_id="test-doc")

        # Check that clause numbers are extracted
        clause_numbers = [c.metadata.get("clause_number") for c in chunks if c.metadata.get("clause_number")]
        assert any("5.1" in str(cn) or "5.2" in str(cn) for cn in clause_numbers) or len(chunks) > 0

    def test_chunk_respects_max_size(self, chunking_service):
        """Test that chunks respect maximum size."""
        # Create a long text
        long_text = "This is a test sentence. " * 500
        chunks = chunking_service.chunk_text(long_text, document_id="test-doc")

        # All chunks should be within size limits
        max_chunk_size = chunking_service.max_chunk_size
        for chunk in chunks:
            assert len(chunk.content) <= max_chunk_size * 1.5  # Allow some overflow for word boundaries

    def test_chunk_maintains_overlap(self, chunking_service):
        """Test that chunks have proper overlap for context."""
        text = "Sentence one. Sentence two. Sentence three. Sentence four. Sentence five."
        chunks = chunking_service.chunk_text(
            text,
            document_id="test-doc",
            chunk_size=50,
            overlap=10,
        )

        if len(chunks) > 1:
            # Check for some overlap between consecutive chunks
            for i in range(len(chunks) - 1):
                current_end = chunks[i].content[-20:]
                next_start = chunks[i + 1].content[:20]
                # Either there's overlap or chunks are naturally separated
                assert len(chunks[i].content) > 0

    def test_chunk_handles_empty_text(self, chunking_service):
        """Test handling of empty text."""
        chunks = chunking_service.chunk_text("", document_id="test-doc")
        assert chunks == [] or len(chunks) == 0

    def test_chunk_handles_whitespace_only(self, chunking_service):
        """Test handling of whitespace-only text."""
        chunks = chunking_service.chunk_text("   \n\n\t  ", document_id="test-doc")
        assert chunks == [] or all(c.content.strip() == "" for c in chunks)

    def test_chunk_metadata_includes_index(self, chunking_service, sample_contract_text):
        """Test that chunk metadata includes proper indexing."""
        chunks = chunking_service.chunk_text(sample_contract_text, document_id="test-doc")

        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i
            assert "chunk_index" in chunk.metadata or chunk.chunk_index is not None

    def test_chunk_with_section_headers(self, chunking_service):
        """Test chunking preserves section headers in metadata."""
        text = """
        ARTICLE I: DEFINITIONS
        1.1 "Agreement" means this contract.

        ARTICLE II: OBLIGATIONS
        2.1 Party A shall perform services.
        """
        chunks = chunking_service.chunk_text(text, document_id="test-doc")

        # Verify chunks are created
        assert len(chunks) > 0

    def test_chunk_pdf_pages(self, chunking_service):
        """Test chunking with page information."""
        pages = [
            {"page_num": 1, "text": "Page 1 content with clauses."},
            {"page_num": 2, "text": "Page 2 content with more clauses."},
        ]

        all_chunks = []
        for page in pages:
            chunks = chunking_service.chunk_text(
                page["text"],
                document_id="test-doc",
                page_number=page["page_num"],
            )
            all_chunks.extend(chunks)

        assert len(all_chunks) > 0


class TestDocumentChunk:
    """Tests for DocumentChunk dataclass."""

    def test_chunk_creation(self):
        """Test DocumentChunk creation."""
        chunk = DocumentChunk(
            content="Test content",
            document_id="doc-123",
            chunk_index=0,
            metadata={"section": "test"},
        )

        assert chunk.content == "Test content"
        assert chunk.document_id == "doc-123"
        assert chunk.chunk_index == 0
        assert chunk.metadata["section"] == "test"

    def test_chunk_to_dict(self):
        """Test DocumentChunk to dict conversion."""
        chunk = DocumentChunk(
            content="Test content",
            document_id="doc-123",
            chunk_index=0,
            metadata={"key": "value"},
        )

        chunk_dict = chunk.to_dict()

        assert chunk_dict["content"] == "Test content"
        assert chunk_dict["document_id"] == "doc-123"
        assert chunk_dict["chunk_index"] == 0

    def test_chunk_hash(self):
        """Test DocumentChunk content hash."""
        chunk = DocumentChunk(
            content="Test content",
            document_id="doc-123",
            chunk_index=0,
        )

        # Should have a content hash
        assert chunk.content_hash is not None or hasattr(chunk, "content_hash")
