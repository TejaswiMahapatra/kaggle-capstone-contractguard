"""
ContractGuard AI - API Routes

FastAPI router modules for the ContractGuard API:
- WebSocket: Real-time progress updates
- A2A: Agent-to-agent protocol endpoints
- MCP: Model Context Protocol endpoints
- Tasks: Long-running task management
- Evaluation: Agent evaluation endpoints
"""

from src.api.websocket import router as websocket_router
from src.api.tasks import router as tasks_router
from src.api.evaluation import router as evaluation_router

__all__ = [
    "websocket_router",
    "tasks_router",
    "evaluation_router",
]
