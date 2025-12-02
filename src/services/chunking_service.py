"""
Chunking Service - Clause-Aware Document Chunking

Specialized chunking for legal contracts that preserves:
- Clause boundaries and numbering
- Section hierarchy
- Context relationships
"""

import re
from dataclasses import dataclass, field, asdict
from typing import Any

from src.observability.logger import get_logger

logger = get_logger(__name__, service="chunking")


@dataclass
class Chunk:
    """Represents a document chunk with metadata."""

    text: str
    document_id: str
    chunk_index: int
    document_name: str = ""
    clause_number: str = ""
    section_title: str = ""
    parent_section: str = ""
    hierarchy_level: int = 0
    page_number: int = 0
    chunk_type: str = "text"  # text, clause, section_header

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ChunkingService:
    """
    Clause-aware document chunking service.

    Features:
    - Detects clause numbers (1.1, 1.1.1, etc.)
    - Identifies section headers
    - Preserves hierarchy relationships
    - Maintains context across chunks
    """

    # Regex patterns for legal document structure
    CLAUSE_PATTERN = re.compile(
        r'^(\d+\.(?:\d+\.)*)\s*(.+?)(?:\n|$)',
        re.MULTILINE
    )

    SECTION_PATTERN = re.compile(
        r'^(?:ARTICLE|SECTION|Part)\s+(\d+|[IVX]+)[:\.]?\s*(.+?)(?:\n|$)',
        re.MULTILINE | re.IGNORECASE
    )

    HEADER_PATTERN = re.compile(
        r'^([A-Z][A-Z\s]{2,}[A-Z])(?:\n|$)',
        re.MULTILINE
    )

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        min_chunk_size: int = 100,
    ):
        """
        Initialize chunking service.

        Args:
            chunk_size: Target chunk size in characters
            chunk_overlap: Overlap between chunks for context
            min_chunk_size: Minimum chunk size (avoid tiny chunks)
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size

        logger.info(
            "ChunkingService initialized",
            chunk_size=chunk_size,
            overlap=chunk_overlap,
        )

    def chunk_text(
        self,
        text: str,
        document_id: str,
        document_name: str = "",
    ) -> list[dict[str, Any]]:
        """
        Chunk a document with clause awareness.

        Args:
            text: Full document text
            document_id: Unique document identifier
            document_name: Original filename

        Returns:
            List of chunk dictionaries with metadata
        """
        logger.info("Chunking document", document_id=document_id)

        # First, try clause-aware chunking
        chunks = self._chunk_by_clauses(text, document_id, document_name)

        # If no clauses found, fall back to simple chunking
        if len(chunks) <= 1:
            logger.info("No clauses found, using simple chunking")
            chunks = self._simple_chunk(text, document_id, document_name)

        logger.info("Chunking complete", chunks=len(chunks))

        return [chunk.to_dict() for chunk in chunks]

    def _chunk_by_clauses(
        self,
        text: str,
        document_id: str,
        document_name: str,
    ) -> list[Chunk]:
        """
        Chunk by clause boundaries.

        Attempts to keep clauses together while respecting size limits.
        """
        chunks: list[Chunk] = []
        current_section = ""
        current_section_title = ""
        chunk_index = 0

        # Find all clause positions
        clause_matches = list(self.CLAUSE_PATTERN.finditer(text))
        section_matches = list(self.SECTION_PATTERN.finditer(text))

        if not clause_matches:
            return []

        # Combine and sort all structural elements
        elements: list[tuple[int, str, str, str]] = []

        for match in section_matches:
            elements.append((
                match.start(),
                "section",
                match.group(1),
                match.group(2).strip(),
            ))

        for match in clause_matches:
            elements.append((
                match.start(),
                "clause",
                match.group(1).rstrip("."),
                match.group(2).strip(),
            ))

        elements.sort(key=lambda x: x[0])

        # Process elements into chunks
        current_text = ""
        current_clause = ""

        for i, (pos, elem_type, number, title) in enumerate(elements):
            # Determine end position
            if i + 1 < len(elements):
                end_pos = elements[i + 1][0]
            else:
                end_pos = len(text)

            # Get text for this element
            element_text = text[pos:end_pos].strip()

            if elem_type == "section":
                # Flush current chunk if any
                if current_text:
                    chunks.append(Chunk(
                        text=current_text.strip(),
                        document_id=document_id,
                        chunk_index=chunk_index,
                        document_name=document_name,
                        clause_number=current_clause,
                        section_title=current_section_title,
                        parent_section=current_section,
                        hierarchy_level=self._get_hierarchy_level(current_clause),
                        chunk_type="clause" if current_clause else "text",
                    ))
                    chunk_index += 1
                    current_text = ""

                current_section = number
                current_section_title = title
                current_clause = ""

            elif elem_type == "clause":
                # Check if we need to start a new chunk
                if len(current_text) + len(element_text) > self.chunk_size:
                    if current_text:
                        chunks.append(Chunk(
                            text=current_text.strip(),
                            document_id=document_id,
                            chunk_index=chunk_index,
                            document_name=document_name,
                            clause_number=current_clause,
                            section_title=current_section_title,
                            parent_section=current_section,
                            hierarchy_level=self._get_hierarchy_level(current_clause),
                            chunk_type="clause",
                        ))
                        chunk_index += 1

                    # Start new chunk with overlap
                    overlap_text = current_text[-self.chunk_overlap:] if current_text else ""
                    current_text = overlap_text + "\n\n" + element_text
                else:
                    current_text += "\n\n" + element_text

                current_clause = number

        # Don't forget the last chunk
        if current_text.strip():
            chunks.append(Chunk(
                text=current_text.strip(),
                document_id=document_id,
                chunk_index=chunk_index,
                document_name=document_name,
                clause_number=current_clause,
                section_title=current_section_title,
                parent_section=current_section,
                hierarchy_level=self._get_hierarchy_level(current_clause),
                chunk_type="clause" if current_clause else "text",
            ))

        return chunks

    def _simple_chunk(
        self,
        text: str,
        document_id: str,
        document_name: str,
    ) -> list[Chunk]:
        """
        Simple chunking by size with overlap.

        Used as fallback when clause structure isn't detected.
        """
        chunks: list[Chunk] = []

        # Split into paragraphs first
        paragraphs = text.split("\n\n")

        current_text = ""
        chunk_index = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            if len(current_text) + len(para) > self.chunk_size:
                if current_text:
                    chunks.append(Chunk(
                        text=current_text.strip(),
                        document_id=document_id,
                        chunk_index=chunk_index,
                        document_name=document_name,
                        chunk_type="text",
                    ))
                    chunk_index += 1

                # Start new chunk with overlap
                overlap = current_text[-self.chunk_overlap:] if current_text else ""
                current_text = overlap + "\n\n" + para
            else:
                if current_text:
                    current_text += "\n\n" + para
                else:
                    current_text = para

        # Last chunk
        if current_text.strip() and len(current_text.strip()) >= self.min_chunk_size:
            chunks.append(Chunk(
                text=current_text.strip(),
                document_id=document_id,
                chunk_index=chunk_index,
                document_name=document_name,
                chunk_type="text",
            ))

        return chunks

    def _get_hierarchy_level(self, clause_number: str) -> int:
        """
        Determine hierarchy level from clause number.

        Examples:
        - "1" -> level 1
        - "1.1" -> level 2
        - "1.1.1" -> level 3
        """
        if not clause_number:
            return 0

        parts = clause_number.rstrip(".").split(".")
        return len(parts)


# Singleton instance
_chunking_service: ChunkingService | None = None


def get_chunking_service() -> ChunkingService:
    """Get or create singleton ChunkingService instance."""
    global _chunking_service
    if _chunking_service is None:
        _chunking_service = ChunkingService()
    return _chunking_service
