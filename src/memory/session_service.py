"""
Session Service - Redis-backed Conversation Session Management

Implements conversation session management using Redis for persistence.
Supports both Google ADK's session interface and extended context management.
"""

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any

import redis.asyncio as redis

from src.config import settings
from src.observability.logger import get_logger

logger = get_logger(__name__, service="session")

# Redis key prefixes
SESSION_PREFIX = "session:"
HISTORY_PREFIX = "history:"
CONTEXT_PREFIX = "context:"

# Session TTL (24 hours default)
SESSION_TTL = 86400


@dataclass
class ConversationTurn:
    """Represents a single turn in the conversation."""

    role: str  # "user" or "assistant"
    content: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ConversationTurn":
        return cls(**data)


@dataclass
class SessionContext:
    """Session context with conversation history and metadata."""

    session_id: str
    user_id: str | None = None
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    last_activity: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    active_documents: list[str] = field(default_factory=list)
    context_data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SessionContext":
        return cls(**data)


class SessionManager:
    """
    Redis-backed session manager for conversation state.

    Features:
    - Persistent session storage in Redis
    - Conversation history tracking
    - Active document management
    - Context preservation across turns
    - Automatic TTL for session cleanup

    Works with Google ADK agents by providing session context
    that can be injected into agent prompts.
    """

    def __init__(
        self,
        redis_url: str | None = None,
        session_ttl: int = SESSION_TTL,
    ):
        """
        Initialize Redis-backed session manager.

        Args:
            redis_url: Redis connection URL (defaults to settings)
            session_ttl: Session time-to-live in seconds (default: 24 hours)
        """
        self.redis_url = redis_url or getattr(settings, "redis_url", "redis://localhost:6379")
        self.session_ttl = session_ttl
        self._redis: redis.Redis | None = None
        logger.info("SessionManager initialized", redis_url=self.redis_url)

    async def _get_redis(self) -> redis.Redis:
        """Get or create Redis connection."""
        if self._redis is None:
            self._redis = await redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
        return self._redis

    async def create_session(
        self,
        user_id: str | None = None,
        initial_documents: list[str] | None = None,
        initial_context: dict[str, Any] | None = None,
    ) -> SessionContext:
        """
        Create a new conversation session in Redis.

        Args:
            user_id: Optional user identifier
            initial_documents: Optional list of document IDs to associate
            initial_context: Optional initial context data

        Returns:
            New SessionContext with unique session_id
        """
        r = await self._get_redis()

        session_id = str(uuid.uuid4())

        context = SessionContext(
            session_id=session_id,
            user_id=user_id,
            active_documents=initial_documents or [],
            context_data=initial_context or {},
        )

        # Store session in Redis
        session_key = f"{SESSION_PREFIX}{session_id}"
        await r.setex(
            session_key,
            self.session_ttl,
            json.dumps(context.to_dict()),
        )

        # Initialize empty history list
        history_key = f"{HISTORY_PREFIX}{session_id}"
        await r.expire(history_key, self.session_ttl)

        logger.info(
            "Session created",
            session_id=session_id,
            user_id=user_id,
            documents=len(initial_documents or []),
        )

        return context

    async def get_session(self, session_id: str) -> SessionContext | None:
        """
        Retrieve an existing session from Redis.

        Args:
            session_id: The session identifier

        Returns:
            SessionContext if found, None otherwise
        """
        r = await self._get_redis()

        session_key = f"{SESSION_PREFIX}{session_id}"
        data = await r.get(session_key)

        if not data:
            logger.warning("Session not found", session_id=session_id)
            return None

        # Refresh TTL on access
        await r.expire(session_key, self.session_ttl)

        context = SessionContext.from_dict(json.loads(data))
        logger.debug("Session retrieved", session_id=session_id)

        return context

    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """
        Add a message to session history in Redis.

        Args:
            session_id: Session to update
            role: Message role ("user" or "assistant")
            content: Message content
            metadata: Optional additional metadata

        Returns:
            True if successful, False if session not found
        """
        r = await self._get_redis()

        # Check session exists
        session_key = f"{SESSION_PREFIX}{session_id}"
        if not await r.exists(session_key):
            logger.warning("Cannot add message - session not found", session_id=session_id)
            return False

        # Create turn
        turn = ConversationTurn(
            role=role,
            content=content,
            metadata=metadata or {},
        )

        # Add to history list
        history_key = f"{HISTORY_PREFIX}{session_id}"
        await r.rpush(history_key, json.dumps(turn.to_dict()))
        await r.expire(history_key, self.session_ttl)

        # Update last activity
        await self._update_last_activity(session_id)

        logger.debug(
            "Message added to session",
            session_id=session_id,
            role=role,
        )

        return True

    async def get_history(
        self,
        session_id: str,
        max_turns: int = 20,
    ) -> list[ConversationTurn]:
        """
        Get conversation history for a session.

        Args:
            session_id: Session to get history for
            max_turns: Maximum number of turns to retrieve

        Returns:
            List of ConversationTurn objects (most recent last)
        """
        r = await self._get_redis()

        history_key = f"{HISTORY_PREFIX}{session_id}"

        # Get last N items
        data = await r.lrange(history_key, -max_turns, -1)

        turns = [ConversationTurn.from_dict(json.loads(item)) for item in data]

        return turns

    async def get_history_text(
        self,
        session_id: str,
        max_turns: int = 10,
    ) -> str:
        """
        Get conversation history formatted as text.

        Args:
            session_id: Session to get history for
            max_turns: Maximum turns to include

        Returns:
            Formatted conversation history string
        """
        turns = await self.get_history(session_id, max_turns)

        lines = []
        for turn in turns:
            prefix = "User" if turn.role == "user" else "Assistant"
            lines.append(f"{prefix}: {turn.content}")

        return "\n\n".join(lines)

    async def set_active_documents(
        self,
        session_id: str,
        document_ids: list[str],
    ) -> bool:
        """
        Set the active documents for a session.

        Args:
            session_id: Session to update
            document_ids: List of document IDs being analyzed

        Returns:
            True if successful
        """
        context = await self.get_session(session_id)
        if not context:
            return False

        context.active_documents = document_ids
        await self._save_session(context)

        logger.debug(
            "Active documents updated",
            session_id=session_id,
            document_count=len(document_ids),
        )

        return True

    async def update_context(
        self,
        session_id: str,
        key: str,
        value: Any,
    ) -> bool:
        """
        Update session context data.

        Args:
            session_id: Session to update
            key: Context key
            value: Context value

        Returns:
            True if successful
        """
        context = await self.get_session(session_id)
        if not context:
            return False

        context.context_data[key] = value
        await self._save_session(context)

        return True

    async def get_context_for_agent(
        self,
        session_id: str,
        include_history: bool = True,
        max_history_turns: int = 10,
    ) -> dict[str, Any]:
        """
        Get session context formatted for agent consumption.

        Provides the agent with relevant context including:
        - Recent conversation history
        - Active documents
        - Any stored context data

        Args:
            session_id: Session to get context for
            include_history: Whether to include conversation history
            max_history_turns: Max history turns to include

        Returns:
            Dictionary of context data for the agent
        """
        context = await self.get_session(session_id)
        if not context:
            return {}

        result = {
            "session_id": context.session_id,
            "user_id": context.user_id,
            "active_documents": context.active_documents,
            "context": context.context_data,
        }

        if include_history:
            result["conversation_history"] = await self.get_history_text(
                session_id, max_history_turns
            )
            turns = await self.get_history(session_id, max_history_turns)
            result["turn_count"] = len(turns)

        return result

    async def delete_session(self, session_id: str) -> bool:
        """
        Delete a session and its history from Redis.

        Args:
            session_id: Session to delete

        Returns:
            True if deleted, False if not found
        """
        r = await self._get_redis()

        session_key = f"{SESSION_PREFIX}{session_id}"
        history_key = f"{HISTORY_PREFIX}{session_id}"

        deleted = await r.delete(session_key, history_key)

        if deleted:
            logger.info("Session deleted", session_id=session_id)
            return True

        return False

    async def _save_session(self, context: SessionContext) -> None:
        """Save session context to Redis."""
        r = await self._get_redis()

        context.last_activity = datetime.utcnow().isoformat()

        session_key = f"{SESSION_PREFIX}{context.session_id}"
        await r.setex(
            session_key,
            self.session_ttl,
            json.dumps(context.to_dict()),
        )

    async def _update_last_activity(self, session_id: str) -> None:
        """Update the last activity timestamp."""
        context = await self.get_session(session_id)
        if context:
            await self._save_session(context)

    async def close(self) -> None:
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()
            self._redis = None
            logger.info("Redis connection closed")


# Singleton instance
_session_manager: SessionManager | None = None


def get_session_manager() -> SessionManager:
    """Get or create singleton SessionManager instance."""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager
