"""
ContractGuard AI - Core Infrastructure

Core infrastructure components shared across the application:
- Database: PostgreSQL for user/document metadata
- Redis: Caching, sessions, real-time pub/sub
- Long-running operations: Task management
"""

from src.core.database import (
    Base,
    get_db,
    init_db,
    close_db,
    check_db_health,
)
from src.core.redis_client import (
    get_redis,
    get_redis_pubsub,
    get_redis_queue,
    close_redis,
    RedisCache,
    RedisPubSub,
    RedisQueue,
)
from src.core.long_running import (
    LongRunningTaskManager,
    TaskStatus,
    get_task_manager,
)

__all__ = [
    # Database
    "Base",
    "get_db",
    "init_db",
    "close_db",
    "check_db_health",
    # Redis
    "get_redis",
    "get_redis_pubsub",
    "get_redis_queue",
    "close_redis",
    "RedisCache",
    "RedisPubSub",
    "RedisQueue",
    # Long-running
    "LongRunningTaskManager",
    "TaskStatus",
    "get_task_manager",
]
