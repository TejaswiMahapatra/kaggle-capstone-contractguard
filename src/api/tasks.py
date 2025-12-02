"""
Task Management API

REST endpoints for managing long-running tasks.
"""

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.agents import create_orchestrator_agent, create_runner, run_agent
from src.core.long_running import (
    LongRunningTask,
    TaskContext,
    TaskStatus,
    get_task_manager,
)
from src.observability.logger import get_logger

logger = get_logger(__name__, component="tasks_api")

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])


class CreateTaskRequest(BaseModel):
    """Request to create a new long-running task."""
    name: str = Field(..., description="Task name/type")
    input_data: dict[str, Any] = Field(default_factory=dict, description="Task input parameters")
    user_id: str | None = Field(None, description="Optional user ID")
    session_id: str | None = Field(None, description="Optional session ID")


class TaskResponse(BaseModel):
    """Response containing task information."""
    id: str
    name: str
    status: str
    progress: dict[str, Any]
    error: str | None = None
    created_at: str
    updated_at: str
    pending_input_prompt: str | None = None
    pending_input_schema: dict[str, Any] | None = None


class ProvideInputRequest(BaseModel):
    """Request to provide user input for a waiting task."""
    input_data: Any = Field(..., description="User-provided input data")


@router.post("", response_model=TaskResponse)
async def create_task(request: CreateTaskRequest):
    """Create a new long-running task."""
    manager = get_task_manager()

    task = await manager.create_task(
        name=request.name,
        input_data=request.input_data,
        user_id=request.user_id,
        session_id=request.session_id,
    )

    return TaskResponse(**task.to_dict())


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str):
    """Get task status and information."""
    manager = get_task_manager()
    task = await manager.get_task(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return TaskResponse(**task.to_dict())


@router.get("")
async def list_tasks(
    status: str | None = None,
    user_id: str | None = None,
    limit: int = 50,
):
    """List tasks, optionally filtered by status or user."""
    manager = get_task_manager()

    task_status = TaskStatus(status) if status else None
    tasks = manager.list_tasks(status=task_status, user_id=user_id)[:limit]

    return {
        "tasks": [TaskResponse(**t.to_dict()) for t in tasks],
        "total": len(tasks),
    }


@router.post("/{task_id}/execute")
async def execute_task(task_id: str):
    """Start executing a task."""
    manager = get_task_manager()
    task = await manager.get_task(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status not in [TaskStatus.PENDING, TaskStatus.PAUSED]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot execute task in status: {task.status}",
        )

    async def contract_analysis_executor(task: LongRunningTask, ctx: TaskContext):
        """Execute contract analysis with progress updates."""
        await ctx.update_progress(
            current_step=1,
            total_steps=4,
            message="Loading document...",
        )
        await ctx.check_pause()

        document_id = task.input_data.get("document_id")
        query = task.input_data.get("query", "Analyze this contract")

        await ctx.update_progress(
            current_step=2,
            total_steps=4,
            message="Creating analysis agent...",
        )
        await ctx.check_pause()

        agent = create_orchestrator_agent()
        runner = create_runner(agent)

        await ctx.update_progress(
            current_step=3,
            total_steps=4,
            message="Running analysis...",
        )
        await ctx.check_pause()

        prompt = f"""Analyze document {document_id}: {query}"""
        result = await run_agent(runner, prompt)

        await ctx.update_progress(
            current_step=4,
            total_steps=4,
            message="Analysis complete!",
        )

        return {"analysis": str(result)}

    asyncio.create_task(manager.execute_task(task_id, contract_analysis_executor))

    return {
        "message": "Task execution started",
        "task_id": task_id,
        "websocket_url": f"/ws/task/{task_id}",
    }


@router.post("/{task_id}/pause")
async def pause_task(task_id: str):
    """Pause a running task."""
    manager = get_task_manager()

    success = await manager.pause_task(task_id)
    if not success:
        raise HTTPException(
            status_code=400,
            detail="Cannot pause task (may not be running)",
        )

    return {"message": "Task paused", "task_id": task_id}


@router.post("/{task_id}/resume")
async def resume_task(task_id: str):
    """Resume a paused task."""
    manager = get_task_manager()

    success = await manager.resume_task(task_id)
    if not success:
        raise HTTPException(
            status_code=400,
            detail="Cannot resume task (may not be paused)",
        )

    return {"message": "Task resumed", "task_id": task_id}


@router.post("/{task_id}/cancel")
async def cancel_task(task_id: str):
    """Cancel a running or paused task."""
    manager = get_task_manager()

    success = await manager.cancel_task(task_id)
    if not success:
        raise HTTPException(
            status_code=400,
            detail="Cannot cancel task (may already be completed)",
        )

    return {"message": "Task cancelled", "task_id": task_id}


@router.post("/{task_id}/input")
async def provide_input(task_id: str, request: ProvideInputRequest):
    """Provide user input for a task waiting for input."""
    manager = get_task_manager()

    success = await manager.provide_input(task_id, request.input_data)
    if not success:
        raise HTTPException(
            status_code=400,
            detail="Cannot provide input (task may not be waiting for input)",
        )

    return {"message": "Input provided", "task_id": task_id}


@router.delete("/{task_id}")
async def delete_task(task_id: str):
    """Delete a completed or failed task."""
    manager = get_task_manager()
    task = await manager.get_task(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status not in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
        raise HTTPException(
            status_code=400,
            detail="Can only delete completed, failed, or cancelled tasks",
        )

    del manager.tasks[task_id]
    return {"message": "Task deleted", "task_id": task_id}
