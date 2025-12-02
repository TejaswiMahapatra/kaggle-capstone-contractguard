"""
Memory Bank - Long-term Memory with Mem0

Implements persistent, semantic memory storage using Mem0.
Mem0 is designed specifically for AI agent memory management with:
- Automatic memory extraction from conversations
- Semantic search across memories
- Memory deduplication and updating
- User and session scoping
"""

from typing import Any
from dataclasses import dataclass

from src.config import settings
from src.observability.logger import get_logger

logger = get_logger(__name__, service="memory_bank")


@dataclass
class MemorySearchResult:
    """Result from memory search."""

    id: str
    memory: str
    score: float
    metadata: dict[str, Any]


class MemoryBank:
    """
    Long-term memory storage using Mem0.

    Mem0 provides:
    - Automatic memory extraction from conversations
    - Semantic similarity search
    - Memory deduplication
    - User/agent/session scoping

    Usage:
        memory_bank = MemoryBank()

        # Add memories
        await memory_bank.add("User prefers detailed risk analysis", user_id="user123")

        # Search memories
        results = await memory_bank.search("risk preferences", user_id="user123")

        # Get all memories for context
        memories = await memory_bank.get_all(user_id="user123")
    """

    def __init__(self):
        """
        Initialize Mem0 memory bank.

        Uses Google Gemini as the LLM for memory operations.
        """
        self._client = None
        logger.info("MemoryBank initialized (lazy loading Mem0)")

    @property
    def client(self):
        """Lazy initialization of Mem0 client."""
        if self._client is None:
            try:
                from mem0 import Memory

                # Configure Mem0 with Gemini
                config = {
                    "llm": {
                        "provider": "google",
                        "config": {
                            "model": settings.gemini_model,
                            "api_key": settings.google_api_key,
                        },
                    },
                    "embedder": {
                        "provider": "google",
                        "config": {
                            "model": settings.gemini_embedding_model,
                            "api_key": settings.google_api_key,
                        },
                    },
                    # Use in-memory vector store for simplicity
                    # Can be configured to use Weaviate, Qdrant, etc.
                    "vector_store": {
                        "provider": "chroma",
                        "config": {
                            "collection_name": "contractguard_memories",
                            "path": "./data/memories",  # Persist to disk
                        },
                    },
                }

                self._client = Memory.from_config(config)
                logger.info("Mem0 client initialized with Gemini")

            except ImportError:
                logger.warning("Mem0 not installed, using fallback memory")
                self._client = FallbackMemory()

        return self._client

    async def add(
        self,
        content: str,
        user_id: str | None = None,
        agent_id: str | None = None,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Add a memory.

        Mem0 automatically extracts and deduplicates memories.

        Args:
            content: Memory content or conversation to extract from
            user_id: User scope for this memory
            agent_id: Agent scope for this memory
            session_id: Session scope for this memory
            metadata: Additional metadata

        Returns:
            Result from Mem0 including extracted memories
        """
        try:
            result = self.client.add(
                content,
                user_id=user_id,
                agent_id=agent_id or "contractguard",
                run_id=session_id,
                metadata=metadata or {},
            )

            logger.info(
                "Memory added",
                user_id=user_id,
                memories_extracted=len(result.get("results", [])),
            )

            return result

        except Exception as e:
            logger.error("Failed to add memory", error=str(e))
            return {"error": str(e)}

    async def search(
        self,
        query: str,
        user_id: str | None = None,
        agent_id: str | None = None,
        limit: int = 10,
    ) -> list[MemorySearchResult]:
        """
        Search memories semantically.

        Args:
            query: Search query
            user_id: Filter by user
            agent_id: Filter by agent
            limit: Maximum results

        Returns:
            List of matching memories with scores
        """
        try:
            results = self.client.search(
                query,
                user_id=user_id,
                agent_id=agent_id or "contractguard",
                limit=limit,
            )

            memories = []
            for item in results.get("results", []):
                memories.append(
                    MemorySearchResult(
                        id=item.get("id", ""),
                        memory=item.get("memory", ""),
                        score=item.get("score", 0.0),
                        metadata=item.get("metadata", {}),
                    )
                )

            logger.debug(
                "Memory search completed",
                query=query[:50],
                results=len(memories),
            )

            return memories

        except Exception as e:
            logger.error("Memory search failed", error=str(e))
            return []

    async def get_all(
        self,
        user_id: str | None = None,
        agent_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Get all memories for a user/agent.

        Args:
            user_id: Filter by user
            agent_id: Filter by agent
            limit: Maximum results

        Returns:
            List of all memories
        """
        try:
            result = self.client.get_all(
                user_id=user_id,
                agent_id=agent_id or "contractguard",
                limit=limit,
            )

            memories = result.get("results", [])
            logger.debug("Retrieved all memories", count=len(memories))

            return memories

        except Exception as e:
            logger.error("Failed to get memories", error=str(e))
            return []

    async def get_context_for_agent(
        self,
        user_id: str | None = None,
        query: str | None = None,
        limit: int = 5,
    ) -> str:
        """
        Get memory context formatted for agent prompts.

        If a query is provided, returns relevant memories.
        Otherwise returns recent memories.

        Args:
            user_id: User to get memories for
            query: Optional query for semantic search
            limit: Maximum memories to include

        Returns:
            Formatted string of relevant memories
        """
        if query:
            memories = await self.search(query, user_id=user_id, limit=limit)
            memory_texts = [m.memory for m in memories]
        else:
            all_memories = await self.get_all(user_id=user_id, limit=limit)
            memory_texts = [m.get("memory", "") for m in all_memories]

        if not memory_texts:
            return ""

        context = "## Relevant Memories\n"
        for i, memory in enumerate(memory_texts, 1):
            context += f"{i}. {memory}\n"

        return context

    async def update(
        self,
        memory_id: str,
        content: str,
    ) -> dict[str, Any]:
        """
        Update an existing memory.

        Args:
            memory_id: ID of memory to update
            content: New content

        Returns:
            Update result
        """
        try:
            result = self.client.update(memory_id, content)
            logger.info("Memory updated", memory_id=memory_id)
            return result

        except Exception as e:
            logger.error("Failed to update memory", error=str(e))
            return {"error": str(e)}

    async def delete(self, memory_id: str) -> bool:
        """
        Delete a memory.

        Args:
            memory_id: ID of memory to delete

        Returns:
            True if successful
        """
        try:
            self.client.delete(memory_id)
            logger.info("Memory deleted", memory_id=memory_id)
            return True

        except Exception as e:
            logger.error("Failed to delete memory", error=str(e))
            return False

    async def add_from_conversation(
        self,
        messages: list[dict[str, str]],
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Extract and store memories from a conversation.

        Mem0 automatically identifies important information to remember.

        Args:
            messages: List of {"role": "user/assistant", "content": "..."}
            user_id: User scope

        Returns:
            Extraction results
        """
        try:
            result = self.client.add(
                messages,
                user_id=user_id,
                agent_id="contractguard",
            )

            logger.info(
                "Memories extracted from conversation",
                message_count=len(messages),
                memories_extracted=len(result.get("results", [])),
            )

            return result

        except Exception as e:
            logger.error("Failed to extract memories", error=str(e))
            return {"error": str(e)}


class FallbackMemory:
    """
    Simple in-memory fallback when Mem0 is not available.

    Stores memories in a dictionary - not persistent!
    """

    def __init__(self):
        self._memories: dict[str, list[dict]] = {}

    def add(
        self,
        content: str,
        user_id: str | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        key = user_id or "global"
        if key not in self._memories:
            self._memories[key] = []

        import uuid
        memory_id = str(uuid.uuid4())

        self._memories[key].append({
            "id": memory_id,
            "memory": content if isinstance(content, str) else str(content),
            "metadata": kwargs.get("metadata", {}),
        })

        return {"results": [{"id": memory_id, "memory": content}]}

    def search(
        self,
        query: str,
        user_id: str | None = None,
        limit: int = 10,
        **kwargs,
    ) -> dict[str, Any]:
        key = user_id or "global"
        memories = self._memories.get(key, [])

        # Simple substring matching
        query_lower = query.lower()
        matches = [
            {**m, "score": 0.5}
            for m in memories
            if query_lower in m.get("memory", "").lower()
        ]

        return {"results": matches[:limit]}

    def get_all(
        self,
        user_id: str | None = None,
        limit: int = 100,
        **kwargs,
    ) -> dict[str, Any]:
        key = user_id or "global"
        memories = self._memories.get(key, [])
        return {"results": memories[:limit]}

    def update(self, memory_id: str, content: str) -> dict[str, Any]:
        for memories in self._memories.values():
            for m in memories:
                if m.get("id") == memory_id:
                    m["memory"] = content
                    return {"success": True}
        return {"error": "Memory not found"}

    def delete(self, memory_id: str) -> None:
        for memories in self._memories.values():
            memories[:] = [m for m in memories if m.get("id") != memory_id]


# Singleton instance
_memory_bank: MemoryBank | None = None


def get_memory_bank() -> MemoryBank:
    """Get or create singleton MemoryBank instance."""
    global _memory_bank
    if _memory_bank is None:
        _memory_bank = MemoryBank()
    return _memory_bank
