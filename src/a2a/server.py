"""
A2A Server - Expose ContractGuard as A2A Remote Agent

This module implements the A2A protocol server, allowing other agents
to discover and interact with ContractGuard AI's capabilities.

The server supports:
- Agent Card discovery (/.well-known/agent.json)
- Task submission and management
- Streaming responses
- Session state management
"""

import asyncio
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, AsyncIterator
from dataclasses import dataclass, field

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field

from src.a2a.agent_card import AgentCard, create_agent_card
from src.config import settings
from src.observability.logger import get_logger

logger = get_logger(__name__, component="a2a_server")


class TaskState(str, Enum):
    """A2A Task States per protocol spec."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    INPUT_REQUIRED = "input_required"


@dataclass
class A2ATask:
    """
    Represents an A2A task being processed.

    Tasks are the primary unit of work in A2A protocol.
    They can be long-running and support streaming.
    """
    id: str
    skill_id: str
    input_data: dict[str, Any]
    state: TaskState = TaskState.PENDING
    output: Any = None
    error: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to A2A response format."""
        return {
            "id": self.id,
            "skillId": self.skill_id,
            "state": self.state.value,
            "output": self.output,
            "error": self.error,
            "createdAt": self.created_at.isoformat(),
            "updatedAt": self.updated_at.isoformat(),
            "metadata": self.metadata,
        }


class TaskRequest(BaseModel):
    """A2A Task submission request."""
    skill_id: str = Field(..., alias="skillId")
    input: dict[str, Any] = Field(default_factory=dict)
    session_id: str | None = Field(None, alias="sessionId")
    metadata: dict[str, Any] = Field(default_factory=dict)


class TaskResponse(BaseModel):
    """A2A Task response."""
    id: str
    skill_id: str = Field(..., alias="skillId")
    state: str
    output: Any = None
    error: str | None = None
    created_at: str = Field(..., alias="createdAt")
    updated_at: str = Field(..., alias="updatedAt")


class A2AServer:
    """
    A2A Protocol Server for ContractGuard AI.

    Implements the A2A server role, exposing ContractGuard's
    capabilities to other agents.

    Features:
    - Agent Card discovery
    - Task submission and execution
    - Streaming responses
    - Task state management
    """

    def __init__(self, agent_card: AgentCard | None = None):
        """
        Initialize A2A Server.

        Args:
            agent_card: Custom agent card (defaults to ContractGuard card)
        """
        self.agent_card = agent_card or create_agent_card()
        self.tasks: dict[str, A2ATask] = {}
        self.router = APIRouter(prefix="/a2a", tags=["a2a"])
        self._setup_routes()
        logger.info("A2A Server initialized", agent=self.agent_card.name)

    def _setup_routes(self):
        """Configure A2A protocol routes."""

        @self.router.get("/.well-known/agent.json")
        async def get_agent_card():
            """
            Agent Card discovery endpoint.

            Per A2A protocol, this endpoint returns the agent's
            capabilities for discovery by other agents.
            """
            return JSONResponse(
                content=self.agent_card.to_dict(),
                headers={"Content-Type": "application/json"},
            )

        @self.router.post("/tasks")
        async def submit_task(request: TaskRequest):
            """
            Submit a task to the agent.

            Creates a new task and begins execution.
            Returns immediately with task ID for polling/streaming.
            """
            task_id = str(uuid.uuid4())

            # Validate skill exists
            skill_ids = [s.id for s in self.agent_card.skills]
            if request.skill_id not in skill_ids:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unknown skill: {request.skill_id}. Available: {skill_ids}",
                )

            # Create task
            task = A2ATask(
                id=task_id,
                skill_id=request.skill_id,
                input_data=request.input,
                metadata=request.metadata,
            )
            self.tasks[task_id] = task

            logger.info("Task submitted", task_id=task_id, skill=request.skill_id)

            # Execute task asynchronously
            asyncio.create_task(self._execute_task(task))

            return JSONResponse(
                content=task.to_dict(),
                status_code=202,  # Accepted
            )

        @self.router.get("/tasks/{task_id}")
        async def get_task(task_id: str):
            """Get task status and results."""
            task = self.tasks.get(task_id)
            if not task:
                raise HTTPException(status_code=404, detail="Task not found")
            return JSONResponse(content=task.to_dict())

        @self.router.get("/tasks/{task_id}/stream")
        async def stream_task(task_id: str):
            """
            Stream task output.

            Returns Server-Sent Events (SSE) with task progress
            and results as they become available.
            """
            task = self.tasks.get(task_id)
            if not task:
                raise HTTPException(status_code=404, detail="Task not found")

            return StreamingResponse(
                self._stream_task_events(task),
                media_type="text/event-stream",
            )

        @self.router.post("/tasks/{task_id}/cancel")
        async def cancel_task(task_id: str):
            """Cancel a running task."""
            task = self.tasks.get(task_id)
            if not task:
                raise HTTPException(status_code=404, detail="Task not found")

            if task.state in [TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED]:
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot cancel task in state: {task.state}",
                )

            task.state = TaskState.CANCELLED
            task.updated_at = datetime.now(timezone.utc)

            logger.info("Task cancelled", task_id=task_id)
            return JSONResponse(content=task.to_dict())

        @self.router.delete("/tasks/{task_id}")
        async def delete_task(task_id: str):
            """Delete a completed task."""
            if task_id not in self.tasks:
                raise HTTPException(status_code=404, detail="Task not found")

            del self.tasks[task_id]
            return JSONResponse(content={"message": "Task deleted"})

        @self.router.get("/tasks")
        async def list_tasks(
            state: str | None = None,
            limit: int = 50,
        ):
            """List tasks, optionally filtered by state."""
            tasks = list(self.tasks.values())

            if state:
                tasks = [t for t in tasks if t.state.value == state]

            tasks = sorted(tasks, key=lambda t: t.created_at, reverse=True)[:limit]

            return JSONResponse(
                content={
                    "tasks": [t.to_dict() for t in tasks],
                    "total": len(tasks),
                }
            )

    async def _execute_task(self, task: A2ATask):
        """
        Execute a task using the appropriate agent/tool.

        Maps skill_id to actual implementation and executes.
        """
        try:
            task.state = TaskState.RUNNING
            task.updated_at = datetime.now(timezone.utc)

            logger.info("Executing task", task_id=task.id, skill=task.skill_id)

            # Route to appropriate handler based on skill
            result = await self._dispatch_skill(task.skill_id, task.input_data)

            task.output = result
            task.state = TaskState.COMPLETED
            task.updated_at = datetime.now(timezone.utc)

            logger.info("Task completed", task_id=task.id)

        except Exception as e:
            task.state = TaskState.FAILED
            task.error = str(e)
            task.updated_at = datetime.now(timezone.utc)

            logger.error("Task failed", task_id=task.id, error=str(e))

    async def _dispatch_skill(self, skill_id: str, input_data: dict[str, Any]) -> Any:
        """
        Dispatch to the appropriate skill implementation.

        This maps A2A skill IDs to actual ContractGuard agents/tools.
        """
        if skill_id == "contract_search":
            from src.tools.search_tool import _search_contracts_impl
            return await _search_contracts_impl(
                query=input_data.get("query", ""),
                top_k=input_data.get("top_k", 5),
                document_id=input_data.get("document_id"),
            )

        elif skill_id == "risk_analysis":
            from src.agents import create_risk_agent, create_runner, run_agent
            agent = create_risk_agent()
            runner = create_runner(agent, app_name="contractguard-a2a")

            prompt = f"""Analyze document {input_data.get('document_id')} for risks.
Categories: {input_data.get('risk_categories', ['all'])}
Provide structured risk assessment."""

            result = await run_agent(runner, prompt)
            return {"analysis": str(result)}

        elif skill_id == "contract_comparison":
            from src.agents import create_compare_agent, create_runner, run_agent
            agent = create_compare_agent()
            runner = create_runner(agent, app_name="contractguard-a2a")

            doc_ids = input_data.get("document_ids", [])
            prompt = f"""Compare contracts: {', '.join(doc_ids)}
Focus areas: {input_data.get('focus_areas', ['all'])}"""

            result = await run_agent(runner, prompt)
            return {"comparison": str(result)}

        elif skill_id == "report_generation":
            from src.agents import create_report_agent, create_runner, run_agent
            agent = create_report_agent()
            runner = create_runner(agent, app_name="contractguard-a2a")

            prompt = f"""Generate a {input_data.get('report_type', 'executive_summary')}
for document {input_data.get('document_id')}.
Format: {input_data.get('format', 'markdown')}"""

            result = await run_agent(runner, prompt)
            return {"report": str(result)}

        elif skill_id == "contract_qa":
            from src.agents import create_orchestrator_agent, create_runner, run_agent
            agent = create_orchestrator_agent()
            runner = create_runner(agent, app_name="contractguard-a2a")

            result = await run_agent(runner, input_data.get("question", ""))
            return {"answer": str(result)}

        elif skill_id == "document_ingestion":
            # Would need to implement URL-based document fetch
            return {"error": "URL-based ingestion not yet implemented"}

        else:
            raise ValueError(f"Unknown skill: {skill_id}")

    async def _stream_task_events(self, task: A2ATask) -> AsyncIterator[str]:
        """
        Generate Server-Sent Events for task progress.

        Yields SSE-formatted events as the task progresses.
        """
        import json

        # Send initial state
        yield f"event: state\ndata: {json.dumps({'state': task.state.value})}\n\n"

        # Poll for updates
        last_state = task.state
        while task.state in [TaskState.PENDING, TaskState.RUNNING]:
            await asyncio.sleep(0.5)

            if task.state != last_state:
                yield f"event: state\ndata: {json.dumps({'state': task.state.value})}\n\n"
                last_state = task.state

        # Send final result
        if task.state == TaskState.COMPLETED:
            yield f"event: completed\ndata: {json.dumps({'output': task.output})}\n\n"
        elif task.state == TaskState.FAILED:
            yield f"event: error\ndata: {json.dumps({'error': task.error})}\n\n"
        elif task.state == TaskState.CANCELLED:
            yield f"event: cancelled\ndata: {json.dumps({'message': 'Task cancelled'})}\n\n"

        yield "event: done\ndata: {}\n\n"


def create_a2a_server(agent_card: AgentCard | None = None) -> A2AServer:
    """
    Factory function to create A2A server.

    Args:
        agent_card: Optional custom agent card

    Returns:
        Configured A2AServer instance
    """
    return A2AServer(agent_card=agent_card)


# Default A2A server instance
default_a2a_server = create_a2a_server()
