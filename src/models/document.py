"""
Document Model for PostgreSQL

Stores contract document metadata for:
- Document tracking and status
- Processing state management
- MinIO storage references
- Weaviate collection mapping
"""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from sqlalchemy import String, Integer, DateTime, Enum as SQLEnum, Text, BigInteger, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base


class DocumentStatus(str, Enum):
    """Document processing status."""
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Document(Base):
    """
    Document metadata model.

    Stores metadata about uploaded contracts and their processing status.
    The actual PDF is stored in MinIO, and embeddings are in Weaviate.
    """

    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )

    # File information
    filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    original_filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    file_size: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )
    mime_type: Mapped[str] = mapped_column(
        String(100),
        default="application/pdf",
    )

    # Storage references
    minio_path: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    minio_bucket: Mapped[str] = mapped_column(
        String(100),
        default="contracts",
    )

    # Processing status
    status: Mapped[DocumentStatus] = mapped_column(
        SQLEnum(DocumentStatus),
        default=DocumentStatus.QUEUED,
        nullable=False,
        index=True,
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Processing results
    num_pages: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    num_chunks: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    total_tokens: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    # Vector database reference
    weaviate_collection: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    # Ownership
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Document metadata
    title: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    contract_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )  # NDA, MSA, SLA, etc.
    parties: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )  # JSON array of parties
    effective_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    expiration_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    processed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"<Document(id={self.id}, filename={self.filename}, status={self.status})>"

    def to_dict(self) -> dict:
        """Convert model to dictionary."""
        return {
            "id": str(self.id),
            "filename": self.filename,
            "original_filename": self.original_filename,
            "file_size": self.file_size,
            "mime_type": self.mime_type,
            "status": self.status.value,
            "error_message": self.error_message,
            "num_pages": self.num_pages,
            "num_chunks": self.num_chunks,
            "total_tokens": self.total_tokens,
            "title": self.title,
            "contract_type": self.contract_type,
            "user_id": str(self.user_id) if self.user_id else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
        }
