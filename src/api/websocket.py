"""
WebSocket API for Real-Time Progress Updates

Provides WebSocket endpoints for:
- Document processing progress
- Long-running task updates
- Agent execution streaming

Ported from ai-systems-starter project.
"""

import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.core.redis_client import get_redis_pubsub, get_redis
from src.observability.logger import get_logger

logger = get_logger(__name__, component="websocket")

router = APIRouter(tags=["websocket"])


class ConnectionManager:
    """
    Manage WebSocket connections.

    Tracks active connections and handles message broadcasting.
    """

    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, connection_id: str, websocket: WebSocket):
        """Accept a WebSocket connection."""
        await websocket.accept()
        self.active_connections[connection_id] = websocket
        logger.info("WebSocket connected", connection_id=connection_id[:8])

    def disconnect(self, connection_id: str):
        """Remove a WebSocket connection."""
        if connection_id in self.active_connections:
            del self.active_connections[connection_id]
            logger.info("WebSocket disconnected", connection_id=connection_id[:8])

    async def send_message(self, connection_id: str, message: dict):
        """Send a message to a specific connection."""
        if connection_id in self.active_connections:
            websocket = self.active_connections[connection_id]
            await websocket.send_json(message)

    async def broadcast(self, message: dict):
        """Broadcast message to all connections."""
        for websocket in self.active_connections.values():
            try:
                await websocket.send_json(message)
            except Exception:
                pass


manager = ConnectionManager()


@router.websocket("/ws/document/{document_id}")
async def document_progress_websocket(
    websocket: WebSocket,
    document_id: str,
):
    """
    WebSocket endpoint for document processing progress.

    Connect to receive real-time updates as your document
    is processed through the ingestion pipeline.

    Message Format:
        {
            "document_id": "123e4567-e89b-12d3-a456-426614174000",
            "status": "processing",
            "message": "Extracting text from PDF...",
            "progress": 30,
            "timestamp": "2024-01-15T10:30:00Z"
        }

    Status Values:
        - "queued": Document waiting to be processed
        - "processing": Document being processed
        - "completed": Processing finished successfully
        - "failed": Processing failed
    """
    await manager.connect(document_id, websocket)
    pubsub = get_redis_pubsub()
    channel_name = f"document:{document_id}:progress"

    try:
        # Send initial connection message
        await websocket.send_json({
            "type": "connected",
            "document_id": document_id,
            "message": f"Connected to progress updates for document {document_id}",
        })

        # Subscribe to Redis pub/sub and forward messages
        async for progress_data in pubsub.subscribe(channel_name):
            await websocket.send_json(progress_data)

            # Close on terminal states
            if progress_data.get("status") in ["completed", "failed"]:
                await asyncio.sleep(0.5)
                break

    except WebSocketDisconnect:
        logger.info("Client disconnected", document_id=document_id[:8])

    except Exception as e:
        logger.error("WebSocket error", document_id=document_id[:8], error=str(e))
        try:
            await websocket.send_json({
                "type": "error",
                "message": f"WebSocket error: {str(e)}",
            })
        except Exception:
            pass

    finally:
        manager.disconnect(document_id)


@router.websocket("/ws/task/{task_id}")
async def task_progress_websocket(
    websocket: WebSocket,
    task_id: str,
):
    """
    WebSocket endpoint for long-running task updates.

    Connect to receive real-time updates for a long-running task.

    Message Format:
        {
            "id": "task-uuid",
            "name": "contract_analysis",
            "status": "running",
            "progress": {
                "current_step": 2,
                "total_steps": 5,
                "percentage": 40.0,
                "message": "Analyzing risks..."
            }
        }

    Status Values:
        - "pending": Task not started
        - "running": Task executing
        - "paused": Task paused by user
        - "waiting_input": Task waiting for user input
        - "completed": Task finished successfully
        - "failed": Task failed
        - "cancelled": Task cancelled
    """
    await manager.connect(f"task:{task_id}", websocket)
    pubsub = get_redis_pubsub()
    channel_name = f"task:{task_id}:updates"

    try:
        await websocket.send_json({
            "type": "connected",
            "task_id": task_id,
            "message": f"Connected to task updates",
        })

        async for update in pubsub.subscribe(channel_name):
            await websocket.send_json(update)

            # Close on terminal states
            if update.get("status") in ["completed", "failed", "cancelled"]:
                await asyncio.sleep(0.5)
                break

    except WebSocketDisconnect:
        logger.info("Client disconnected", task_id=task_id[:8])

    except Exception as e:
        logger.error("WebSocket error", task_id=task_id[:8], error=str(e))

    finally:
        manager.disconnect(f"task:{task_id}")


@router.websocket("/ws/agent/{session_id}")
async def agent_stream_websocket(
    websocket: WebSocket,
    session_id: str,
):
    """
    WebSocket endpoint for streaming agent responses.

    Connect to receive real-time agent output as it's generated.

    Message Format:
        {
            "type": "token" | "tool_call" | "complete",
            "content": "...",
            "agent": "orchestrator",
            "timestamp": "2024-01-15T10:30:00Z"
        }
    """
    await manager.connect(f"agent:{session_id}", websocket)
    pubsub = get_redis_pubsub()
    channel_name = f"agent:{session_id}:stream"

    try:
        await websocket.send_json({
            "type": "connected",
            "session_id": session_id,
            "message": "Connected to agent stream",
        })

        async for event in pubsub.subscribe(channel_name):
            await websocket.send_json(event)

            if event.get("type") == "complete":
                break

    except WebSocketDisconnect:
        logger.info("Client disconnected", session_id=session_id[:8])

    except Exception as e:
        logger.error("WebSocket error", session_id=session_id[:8], error=str(e))

    finally:
        manager.disconnect(f"agent:{session_id}")


# Test endpoint for broadcasting
@router.get("/test/broadcast/{document_id}")
async def test_broadcast(document_id: str, message: str = "Test message"):
    """
    Test endpoint to broadcast a message to WebSocket clients.

    Useful for testing WebSocket connections without running
    the full ingestion worker.
    """
    import json
    from datetime import datetime, timezone

    redis = get_redis()

    test_data = {
        "document_id": document_id,
        "status": "processing",
        "message": message,
        "progress": 50,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    channel_name = f"document:{document_id}:progress"
    await redis.publish(channel_name, json.dumps(test_data))

    return {
        "status": "ok",
        "message": f"Broadcasted to channel: {channel_name}",
        "data": test_data,
    }
