"""
Long-Running Operations - Pause/Resume Agent Tasks

Implements long-running task management for agent operations that:
- Can be paused and resumed
- Support human-in-the-loop intervention
- Provide progress tracking via WebSocket
- Allow task cancellation

This fulfills the "Long-running operations" requirement for
the Kaggle Agents Intensive capstone.
"""

import asyncio
import uuid
from datetime import datetime, timezone
from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable

from src.core.redis_client import RedisPubSub, RedisCache, get_redis_pubsub
from src.observability.logger import get_logger

logger = get_logger(__name__, component="long_running")


class TaskStatus(str, Enum):
    """Status of a long-running task."""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    WAITING_INPUT = "waiting_input"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TaskProgress:
    """Progress information for a task."""
    current_step: int = 0
    total_steps: int = 0
    percentage: float = 0.0
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class LongRunningTask:
    """
    Represents a long-running agent task.

    Tasks support:
    - Pause/Resume: Stop and continue execution
    - Human-in-the-loop: Wait for user input
    - Progress tracking: Real-time updates
    - Cancellation: Stop task at any point
    """
    id: str
    name: str
    status: TaskStatus = TaskStatus.PENDING
    progress: TaskProgress = field(default_factory=TaskProgress)
    input_data: dict[str, Any] = field(default_factory=dict)
    output_data: Any = None
    error: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    user_id: str | None = None
    session_id: str | None = None
    # For human-in-the-loop
    pending_input_prompt: str | None = None
    pending_input_schema: dict[str, Any] | None = None
    user_input: Any = None
    # Checkpointing
    checkpoint_data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status.value,
            "progress": {
                "current_step": self.progress.current_step,
                "total_steps": self.progress.total_steps,
                "percentage": self.progress.percentage,
                "message": self.progress.message,
            },
            "error": self.error,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "pending_input_prompt": self.pending_input_prompt,
            "pending_input_schema": self.pending_input_schema,
        }


class LongRunningTaskManager:
    """
    Manages long-running agent tasks with pause/resume capabilities.

    Features:
    - Task creation and lifecycle management
    - Pause/Resume/Cancel operations
    - Progress tracking with WebSocket pub/sub
    - Human-in-the-loop input handling
    - Checkpointing for resumability

    Example:
        manager = LongRunningTaskManager()

        # Create and start a task
        task = await manager.create_task(
            name="contract_analysis",
            input_data={"document_id": "123"},
        )

        # Execute with progress callbacks
        await manager.execute_task(
            task.id,
            executor=my_analysis_function,
        )

        # Pause if needed
        await manager.pause_task(task.id)

        # Resume later
        await manager.resume_task(task.id)
    """

    def __init__(self):
        """Initialize the task manager."""
        self.tasks: dict[str, LongRunningTask] = {}
        self.pubsub = get_redis_pubsub()
        self.cache = RedisCache(prefix="tasks")
        self._executors: dict[str, asyncio.Task] = {}
        self._pause_events: dict[str, asyncio.Event] = {}
        logger.info("Long-running task manager initialized")

    async def create_task(
        self,
        name: str,
        input_data: dict[str, Any] | None = None,
        user_id: str | None = None,
        session_id: str | None = None,
    ) -> LongRunningTask:
        """
        Create a new long-running task.

        Args:
            name: Task name/type
            input_data: Input parameters for the task
            user_id: Optional user ID
            session_id: Optional session ID

        Returns:
            Created task instance
        """
        task_id = str(uuid.uuid4())

        task = LongRunningTask(
            id=task_id,
            name=name,
            input_data=input_data or {},
            user_id=user_id,
            session_id=session_id,
        )

        self.tasks[task_id] = task
        self._pause_events[task_id] = asyncio.Event()
        self._pause_events[task_id].set()  # Not paused initially

        # Persist to Redis
        await self.cache.set(f"task:{task_id}", task.to_dict(), ttl=86400)

        logger.info("Task created", task_id=task_id, name=name)
        await self._publish_update(task)

        return task

    async def get_task(self, task_id: str) -> LongRunningTask | None:
        """Get task by ID."""
        return self.tasks.get(task_id)

    async def execute_task(
        self,
        task_id: str,
        executor: Callable[[LongRunningTask, "TaskContext"], Awaitable[Any]],
    ) -> None:
        """
        Execute a task using the provided executor.

        Args:
            task_id: Task to execute
            executor: Async function that performs the task

        The executor receives:
            - task: The LongRunningTask instance
            - context: TaskContext with helper methods
        """
        task = self.tasks.get(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")

        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now(timezone.utc)
        task.updated_at = datetime.now(timezone.utc)
        await self._publish_update(task)

        context = TaskContext(self, task)

        try:
            # Create asyncio task for execution
            async_task = asyncio.create_task(
                self._run_executor(task, executor, context)
            )
            self._executors[task_id] = async_task

            # Wait for completion
            result = await async_task

            task.output_data = result
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now(timezone.utc)

            logger.info("Task completed", task_id=task_id)

        except asyncio.CancelledError:
            task.status = TaskStatus.CANCELLED
            logger.info("Task cancelled", task_id=task_id)

        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            logger.error("Task failed", task_id=task_id, error=str(e))

        finally:
            task.updated_at = datetime.now(timezone.utc)
            await self._publish_update(task)
            self._executors.pop(task_id, None)

    async def _run_executor(
        self,
        task: LongRunningTask,
        executor: Callable,
        context: "TaskContext",
    ) -> Any:
        """Run the executor with pause point checking."""
        return await executor(task, context)

    async def pause_task(self, task_id: str) -> bool:
        """
        Pause a running task.

        The task will pause at the next checkpoint/yield point.

        Returns:
            True if pause was successful
        """
        task = self.tasks.get(task_id)
        if not task or task.status != TaskStatus.RUNNING:
            return False

        # Clear pause event to block at next checkpoint
        if task_id in self._pause_events:
            self._pause_events[task_id].clear()

        task.status = TaskStatus.PAUSED
        task.updated_at = datetime.now(timezone.utc)
        await self._publish_update(task)

        logger.info("Task paused", task_id=task_id)
        return True

    async def resume_task(self, task_id: str) -> bool:
        """
        Resume a paused task.

        Returns:
            True if resume was successful
        """
        task = self.tasks.get(task_id)
        if not task or task.status != TaskStatus.PAUSED:
            return False

        # Set pause event to allow continuation
        if task_id in self._pause_events:
            self._pause_events[task_id].set()

        task.status = TaskStatus.RUNNING
        task.updated_at = datetime.now(timezone.utc)
        await self._publish_update(task)

        logger.info("Task resumed", task_id=task_id)
        return True

    async def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a running or paused task.

        Returns:
            True if cancellation was successful
        """
        task = self.tasks.get(task_id)
        if not task or task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
            return False

        # Cancel the asyncio task if running
        if task_id in self._executors:
            self._executors[task_id].cancel()

        # Release any pause
        if task_id in self._pause_events:
            self._pause_events[task_id].set()

        task.status = TaskStatus.CANCELLED
        task.updated_at = datetime.now(timezone.utc)
        await self._publish_update(task)

        logger.info("Task cancelled", task_id=task_id)
        return True

    async def request_input(
        self,
        task_id: str,
        prompt: str,
        schema: dict[str, Any] | None = None,
    ) -> None:
        """
        Request input from the user (human-in-the-loop).

        The task will pause until input is provided.

        Args:
            task_id: Task ID
            prompt: Message to show user
            schema: JSON schema for expected input
        """
        task = self.tasks.get(task_id)
        if not task:
            return

        task.status = TaskStatus.WAITING_INPUT
        task.pending_input_prompt = prompt
        task.pending_input_schema = schema
        task.user_input = None
        task.updated_at = datetime.now(timezone.utc)

        # Pause execution
        if task_id in self._pause_events:
            self._pause_events[task_id].clear()

        await self._publish_update(task)
        logger.info("Task waiting for input", task_id=task_id, prompt=prompt)

    async def provide_input(
        self,
        task_id: str,
        input_data: Any,
    ) -> bool:
        """
        Provide user input for a waiting task.

        Args:
            task_id: Task ID
            input_data: User-provided input

        Returns:
            True if input was accepted
        """
        task = self.tasks.get(task_id)
        if not task or task.status != TaskStatus.WAITING_INPUT:
            return False

        task.user_input = input_data
        task.pending_input_prompt = None
        task.pending_input_schema = None
        task.status = TaskStatus.RUNNING
        task.updated_at = datetime.now(timezone.utc)

        # Resume execution
        if task_id in self._pause_events:
            self._pause_events[task_id].set()

        await self._publish_update(task)
        logger.info("Input provided", task_id=task_id)
        return True

    async def update_progress(
        self,
        task_id: str,
        current_step: int | None = None,
        total_steps: int | None = None,
        message: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Update task progress and publish to subscribers."""
        task = self.tasks.get(task_id)
        if not task:
            return

        if current_step is not None:
            task.progress.current_step = current_step
        if total_steps is not None:
            task.progress.total_steps = total_steps
        if message is not None:
            task.progress.message = message
        if details is not None:
            task.progress.details = details

        # Calculate percentage
        if task.progress.total_steps > 0:
            task.progress.percentage = (
                task.progress.current_step / task.progress.total_steps * 100
            )

        task.updated_at = datetime.now(timezone.utc)
        await self._publish_update(task)

    async def checkpoint(
        self,
        task_id: str,
        data: dict[str, Any],
    ) -> None:
        """
        Save checkpoint data for task resumability.

        Args:
            task_id: Task ID
            data: Checkpoint data to save
        """
        task = self.tasks.get(task_id)
        if not task:
            return

        task.checkpoint_data = data
        await self.cache.set(f"checkpoint:{task_id}", data, ttl=86400)
        logger.debug("Checkpoint saved", task_id=task_id)

    async def _publish_update(self, task: LongRunningTask) -> None:
        """Publish task update via pub/sub."""
        channel = f"task:{task.id}:updates"
        await self.pubsub.publish(channel, task.to_dict())

    def list_tasks(
        self,
        status: TaskStatus | None = None,
        user_id: str | None = None,
    ) -> list[LongRunningTask]:
        """List tasks, optionally filtered."""
        tasks = list(self.tasks.values())

        if status:
            tasks = [t for t in tasks if t.status == status]
        if user_id:
            tasks = [t for t in tasks if t.user_id == user_id]

        return sorted(tasks, key=lambda t: t.created_at, reverse=True)


class TaskContext:
    """
    Context object passed to task executors.

    Provides helper methods for:
    - Progress updates
    - Pause point checking
    - User input requests
    - Checkpointing
    """

    def __init__(self, manager: LongRunningTaskManager, task: LongRunningTask):
        self.manager = manager
        self.task = task

    async def update_progress(
        self,
        current_step: int | None = None,
        total_steps: int | None = None,
        message: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Update task progress."""
        await self.manager.update_progress(
            self.task.id,
            current_step=current_step,
            total_steps=total_steps,
            message=message,
            details=details,
        )

    async def check_pause(self) -> None:
        """
        Check if task should pause.

        Call this at natural break points in your executor.
        Will block if task is paused.
        """
        event = self.manager._pause_events.get(self.task.id)
        if event:
            await event.wait()

    async def request_input(
        self,
        prompt: str,
        schema: dict[str, Any] | None = None,
    ) -> Any:
        """
        Request input from user.

        Blocks until user provides input.

        Returns:
            User-provided input data
        """
        await self.manager.request_input(self.task.id, prompt, schema)

        # Wait for input
        event = self.manager._pause_events.get(self.task.id)
        if event:
            await event.wait()

        return self.task.user_input

    async def checkpoint(self, data: dict[str, Any]) -> None:
        """Save checkpoint for resumability."""
        await self.manager.checkpoint(self.task.id, data)

    def get_checkpoint(self) -> dict[str, Any]:
        """Get saved checkpoint data."""
        return self.task.checkpoint_data


# Singleton instance
_task_manager: LongRunningTaskManager | None = None


def get_task_manager() -> LongRunningTaskManager:
    """Get the singleton task manager."""
    global _task_manager
    if _task_manager is None:
        _task_manager = LongRunningTaskManager()
    return _task_manager
