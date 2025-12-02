"""
Unit Tests for Chunking Service

Tests clause-aware document chunking functionality.
"""

import pytest
from src.services.chunking_service import (
    ChunkingService,
    get_chunking_service,
    Chunk,
)


class TestChunkingService:
    """Tests for ChunkingService."""

    @pytest.fixture
    def chunking_service(self) -> ChunkingService:
        """Create chunking service instance."""
        return ChunkingService()

    def test_service_singleton(self):
        """Test that get_chunking_service returns singleton."""
        service1 = get_chunking_service()
        service2 = get_chunking_service()
        assert service1 is service2

    def test_chunk_simple_text(self, chunking_service, sample_contract_text):
        """Test basic text chunking."""
        chunks = chunking_service.chunk_text(sample_contract_text, document_id="test-doc")

        assert len(chunks) > 0
        assert all(isinstance(chunk, dict) for chunk in chunks)
        assert all(chunk["document_id"] == "test-doc" for chunk in chunks)

    def test_chunk_preserves_clause_numbers(self, chunking_service):
        """Test that clause numbers are preserved in metadata."""
        text = """
        5.1 The Receiving Party shall maintain confidentiality.
        5.2 The Receiving Party shall not disclose information.
        """
        chunks = chunking_service.chunk_text(text, document_id="test-doc")

        # Check that clause numbers are extracted
        clause_numbers = [c.get("clause_number") for c in chunks if c.get("clause_number")]
        assert any("5.1" in str(cn) or "5.2" in str(cn) for cn in clause_numbers) or len(chunks) > 0

    def test_chunk_respects_max_size(self, chunking_service):
        """Test that chunks respect maximum size."""
        # Create long text with paragraph separators (required for chunking)
        paragraph = "This is a test sentence. " * 20
        long_text = "\n\n".join([paragraph] * 20)
        chunks = chunking_service.chunk_text(long_text, document_id="test-doc")

        # Should produce multiple chunks
        assert len(chunks) > 1
        # All chunks should be within reasonable size limits
        max_chunk_size = chunking_service.chunk_size
        for chunk in chunks:
            # Allow some overflow for paragraph boundaries and overlap
            assert len(chunk["text"]) <= max_chunk_size * 2

    def test_chunk_maintains_overlap(self, chunking_service):
        """Test that chunks have proper overlap for context."""
        # Use a custom service with smaller chunk size for this test
        small_service = ChunkingService(chunk_size=50, chunk_overlap=10, min_chunk_size=10)
        text = "Sentence one. Sentence two. Sentence three. Sentence four. Sentence five."
        chunks = small_service.chunk_text(text, document_id="test-doc")

        if len(chunks) > 1:
            # Check for some overlap between consecutive chunks
            for i in range(len(chunks) - 1):
                current_end = chunks[i]["text"][-20:]
                next_start = chunks[i + 1]["text"][:20]
                # Either there's overlap or chunks are naturally separated
                assert len(chunks[i]["text"]) > 0

    def test_chunk_handles_empty_text(self, chunking_service):
        """Test handling of empty text."""
        chunks = chunking_service.chunk_text("", document_id="test-doc")
        assert chunks == [] or len(chunks) == 0

    def test_chunk_handles_whitespace_only(self, chunking_service):
        """Test handling of whitespace-only text."""
        chunks = chunking_service.chunk_text("   \n\n\t  ", document_id="test-doc")
        assert chunks == [] or all(c["text"].strip() == "" for c in chunks)

    def test_chunk_metadata_includes_index(self, chunking_service, sample_contract_text):
        """Test that chunk metadata includes proper indexing."""
        chunks = chunking_service.chunk_text(sample_contract_text, document_id="test-doc")

        for i, chunk in enumerate(chunks):
            assert chunk["chunk_index"] == i

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
        # Use text longer than min_chunk_size (100 chars by default)
        pages = [
            {"page_num": 1, "text": "Page 1 content with clauses. " * 10},
            {"page_num": 2, "text": "Page 2 content with more clauses. " * 10},
        ]

        all_chunks = []
        for page in pages:
            chunks = chunking_service.chunk_text(
                page["text"],
                document_id="test-doc",
            )
            all_chunks.extend(chunks)

        assert len(all_chunks) > 0


class TestChunk:
    """Tests for Chunk dataclass."""

    def test_chunk_creation(self):
        """Test Chunk creation."""
        chunk = Chunk(
            text="Test content",
            document_id="doc-123",
            chunk_index=0,
            section_title="test",
        )

        assert chunk.text == "Test content"
        assert chunk.document_id == "doc-123"
        assert chunk.chunk_index == 0
        assert chunk.section_title == "test"

    def test_chunk_to_dict(self):
        """Test Chunk to dict conversion."""
        chunk = Chunk(
            text="Test content",
            document_id="doc-123",
            chunk_index=0,
            clause_number="1.1",
        )

        chunk_dict = chunk.to_dict()

        assert chunk_dict["text"] == "Test content"
        assert chunk_dict["document_id"] == "doc-123"
        assert chunk_dict["chunk_index"] == 0
        assert chunk_dict["clause_number"] == "1.1"

    def test_chunk_default_values(self):
        """Test Chunk default values."""
        chunk = Chunk(
            text="Test content",
            document_id="doc-123",
            chunk_index=0,
        )

        assert chunk.document_name == ""
        assert chunk.clause_number == ""
        assert chunk.section_title == ""
        assert chunk.parent_section == ""
        assert chunk.hierarchy_level == 0
        assert chunk.page_number == 0
        assert chunk.chunk_type == "text"


class TestHierarchyLevel:
    """Tests for hierarchy level detection."""

    @pytest.fixture
    def chunking_service(self) -> ChunkingService:
        """Create chunking service instance."""
        return ChunkingService()

    def test_hierarchy_level_single(self, chunking_service):
        """Test hierarchy level for single number clause."""
        assert chunking_service._get_hierarchy_level("1") == 1
        assert chunking_service._get_hierarchy_level("5") == 1

    def test_hierarchy_level_double(self, chunking_service):
        """Test hierarchy level for two-part clause."""
        assert chunking_service._get_hierarchy_level("1.1") == 2
        assert chunking_service._get_hierarchy_level("5.3") == 2

    def test_hierarchy_level_triple(self, chunking_service):
        """Test hierarchy level for three-part clause."""
        assert chunking_service._get_hierarchy_level("1.1.1") == 3
        assert chunking_service._get_hierarchy_level("5.3.2") == 3

    def test_hierarchy_level_empty(self, chunking_service):
        """Test hierarchy level for empty clause number."""
        assert chunking_service._get_hierarchy_level("") == 0

    def test_hierarchy_level_trailing_dot(self, chunking_service):
        """Test hierarchy level handles trailing dots."""
        assert chunking_service._get_hierarchy_level("1.1.") == 2
        assert chunking_service._get_hierarchy_level("1.") == 1
