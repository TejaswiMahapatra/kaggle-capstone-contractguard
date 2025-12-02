"""
User Model for PostgreSQL

Stores user account information for:
- Authentication
- User-specific sessions
- Document ownership
- Audit tracking
"""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from sqlalchemy import String, DateTime, Boolean, Enum as SQLEnum, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base


class UserRole(str, Enum):
    """User role types."""
    USER = "user"
    ADMIN = "admin"
    ANALYST = "analyst"


class User(Base):
    """
    User account model.

    Stores user information for:
    - Session management (user-wise sessions)
    - Document ownership
    - Access control
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )

    # Authentication
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    hashed_password: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,  # Nullable for OAuth users
    )

    # Profile
    full_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    organization: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    # Role and permissions
    role: Mapped[UserRole] = mapped_column(
        SQLEnum(UserRole),
        default=UserRole.USER,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # OAuth
    oauth_provider: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    oauth_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    # Settings and preferences
    settings: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )  # JSON string

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
    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email}, role={self.role})>"

    def to_dict(self) -> dict:
        """Convert to dictionary (excluding sensitive fields)."""
        return {
            "id": str(self.id),
            "email": self.email,
            "full_name": self.full_name,
            "organization": self.organization,
            "role": self.role.value,
            "is_active": self.is_active,
            "is_verified": self.is_verified,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_login_at": self.last_login_at.isoformat() if self.last_login_at else None,
        }

    @property
    def is_admin(self) -> bool:
        """Check if user is admin."""
        return self.role == UserRole.ADMIN
