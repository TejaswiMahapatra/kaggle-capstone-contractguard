"""
A2A Client - Consume Remote A2A Agents

This module implements an A2A client for connecting to remote agents
and delegating tasks to them. Enables ContractGuard to interact with
external A2A-compatible agents.

Features:
- Agent discovery via Agent Cards
- Task submission and tracking
- Streaming response handling
- Retry and error handling
"""

import asyncio
from dataclasses import dataclass
from typing import Any, AsyncIterator

import httpx

from src.a2a.agent_card import AgentCard
from src.observability.logger import get_logger

logger = get_logger(__name__, component="a2a_client")


@dataclass
class RemoteTask:
    """Represents a task submitted to a remote agent."""
    id: str
    skill_id: str
    state: str
    output: Any = None
    error: str | None = None


class A2AClient:
    """
    A2A Protocol Client for consuming remote agents.

    Allows ContractGuard to:
    - Discover remote agent capabilities
    - Submit tasks to remote agents
    - Track task progress
    - Handle streaming responses

    Example:
        client = A2AClient("https://remote-agent.example.com")
        card = await client.discover()

        task = await client.submit_task(
            skill_id="some_skill",
            input_data={"query": "..."}
        )

        result = await client.wait_for_completion(task.id)
    """

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        timeout: float = 30.0,
    ):
        """
        Initialize A2A client.

        Args:
            base_url: Base URL of the remote A2A agent
            api_key: Optional API key for authentication
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._agent_card: AgentCard | None = None

        # Configure HTTP client
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        self.http_client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=headers,
            timeout=timeout,
        )

        logger.info("A2A Client initialized", base_url=base_url)

    async def close(self):
        """Close HTTP client."""
        await self.http_client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()

    async def discover(self, force_refresh: bool = False) -> AgentCard:
        """
        Discover remote agent's capabilities.

        Fetches the Agent Card from the remote agent's
        well-known endpoint.

        Args:
            force_refresh: Force refetch even if cached

        Returns:
            AgentCard describing the remote agent
        """
        if self._agent_card and not force_refresh:
            return self._agent_card

        try:
            response = await self.http_client.get("/a2a/.well-known/agent.json")
            response.raise_for_status()

            data = response.json()
            self._agent_card = AgentCard.from_dict(data)

            logger.info(
                "Agent discovered",
                name=self._agent_card.name,
                skills=len(self._agent_card.skills),
            )

            return self._agent_card

        except httpx.HTTPError as e:
            logger.error("Discovery failed", error=str(e))
            raise ConnectionError(f"Failed to discover agent: {e}")

    @property
    def agent_card(self) -> AgentCard | None:
        """Get cached agent card (call discover() first)."""
        return self._agent_card

    async def list_skills(self) -> list[dict[str, Any]]:
        """
        List available skills from remote agent.

        Returns:
            List of skill definitions
        """
        card = await self.discover()
        return [skill.to_dict() for skill in card.skills]

    async def submit_task(
        self,
        skill_id: str,
        input_data: dict[str, Any],
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> RemoteTask:
        """
        Submit a task to the remote agent.

        Args:
            skill_id: ID of the skill to invoke
            input_data: Input parameters for the skill
            session_id: Optional session for continuity
            metadata: Optional metadata

        Returns:
            RemoteTask with task ID for tracking
        """
        payload = {
            "skillId": skill_id,
            "input": input_data,
        }
        if session_id:
            payload["sessionId"] = session_id
        if metadata:
            payload["metadata"] = metadata

        try:
            response = await self.http_client.post("/a2a/tasks", json=payload)
            response.raise_for_status()

            data = response.json()
            task = RemoteTask(
                id=data["id"],
                skill_id=data["skillId"],
                state=data["state"],
                output=data.get("output"),
                error=data.get("error"),
            )

            logger.info("Task submitted", task_id=task.id, skill=skill_id)
            return task

        except httpx.HTTPError as e:
            logger.error("Task submission failed", error=str(e))
            raise

    async def get_task(self, task_id: str) -> RemoteTask:
        """
        Get task status.

        Args:
            task_id: Task ID to check

        Returns:
            RemoteTask with current state
        """
        response = await self.http_client.get(f"/a2a/tasks/{task_id}")
        response.raise_for_status()

        data = response.json()
        return RemoteTask(
            id=data["id"],
            skill_id=data["skillId"],
            state=data["state"],
            output=data.get("output"),
            error=data.get("error"),
        )

    async def wait_for_completion(
        self,
        task_id: str,
        poll_interval: float = 1.0,
        timeout: float | None = None,
    ) -> RemoteTask:
        """
        Wait for task to complete.

        Polls the task status until it reaches a terminal state.

        Args:
            task_id: Task to wait for
            poll_interval: Seconds between polls
            timeout: Maximum time to wait (None = forever)

        Returns:
            Completed RemoteTask

        Raises:
            TimeoutError: If timeout exceeded
        """
        start_time = asyncio.get_event_loop().time()

        while True:
            task = await self.get_task(task_id)

            if task.state in ["completed", "failed", "cancelled"]:
                return task

            if timeout:
                elapsed = asyncio.get_event_loop().time() - start_time
                if elapsed > timeout:
                    raise TimeoutError(f"Task {task_id} did not complete within {timeout}s")

            await asyncio.sleep(poll_interval)

    async def stream_task(self, task_id: str) -> AsyncIterator[dict[str, Any]]:
        """
        Stream task events.

        Yields Server-Sent Events from the remote agent
        as the task progresses.

        Args:
            task_id: Task to stream

        Yields:
            Event dictionaries with type and data
        """
        async with self.http_client.stream(
            "GET",
            f"/a2a/tasks/{task_id}/stream",
        ) as response:
            response.raise_for_status()

            event_type = None
            event_data = ""

            async for line in response.aiter_lines():
                line = line.strip()

                if line.startswith("event:"):
                    event_type = line[6:].strip()
                elif line.startswith("data:"):
                    event_data = line[5:].strip()
                elif line == "" and event_type:
                    # End of event
                    import json
                    try:
                        data = json.loads(event_data) if event_data else {}
                    except json.JSONDecodeError:
                        data = {"raw": event_data}

                    yield {"event": event_type, "data": data}

                    if event_type == "done":
                        return

                    event_type = None
                    event_data = ""

    async def cancel_task(self, task_id: str) -> RemoteTask:
        """
        Cancel a running task.

        Args:
            task_id: Task to cancel

        Returns:
            Updated RemoteTask
        """
        response = await self.http_client.post(f"/a2a/tasks/{task_id}/cancel")
        response.raise_for_status()

        data = response.json()
        return RemoteTask(
            id=data["id"],
            skill_id=data["skillId"],
            state=data["state"],
            output=data.get("output"),
            error=data.get("error"),
        )

    async def run_skill(
        self,
        skill_id: str,
        input_data: dict[str, Any],
        wait: bool = True,
        timeout: float = 60.0,
    ) -> Any:
        """
        Convenience method to run a skill and get results.

        Combines submit_task and wait_for_completion.

        Args:
            skill_id: Skill to invoke
            input_data: Input parameters
            wait: Whether to wait for completion
            timeout: Maximum time to wait

        Returns:
            Task output if wait=True, else RemoteTask
        """
        task = await self.submit_task(skill_id, input_data)

        if not wait:
            return task

        completed = await self.wait_for_completion(task.id, timeout=timeout)

        if completed.state == "failed":
            raise RuntimeError(f"Task failed: {completed.error}")

        return completed.output
