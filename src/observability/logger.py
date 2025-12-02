"""
Structured logging configuration for ContractGuard AI.

Uses structlog for structured, context-rich logging that integrates
with OpenTelemetry tracing.
"""

import logging
import sys
from typing import Any

import structlog
from structlog.typing import Processor

from src.config import settings


def setup_logging() -> None:
    """
    Configure structured logging for the application.

    Sets up structlog with:
    - JSON formatting in production
    - Pretty console output in development
    - Automatic trace context injection
    - Log level from settings
    """
    # Determine log level
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # Configure standard logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    # Shared processors for all environments
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if settings.is_production:
        # Production: JSON output for log aggregation
        processors: list[Processor] = [
            *shared_processors,
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Development: Pretty console output
        processors = [
            *shared_processors,
            structlog.dev.ConsoleRenderer(colors=True),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None, **initial_context: Any) -> structlog.BoundLogger:
    """
    Get a structured logger instance.

    Args:
        name: Logger name (typically __name__)
        **initial_context: Initial context to bind to logger

    Returns:
        Configured structlog BoundLogger

    Example:
        logger = get_logger(__name__, agent="rag_agent")
        logger.info("Processing query", query="What are the terms?")
    """
    logger = structlog.get_logger(name)
    if initial_context:
        logger = logger.bind(**initial_context)
    return logger


class LogContext:
    """
    Context manager for temporary log context.

    Example:
        with LogContext(request_id="abc123", user_id="user1"):
            logger.info("Processing request")  # Includes request_id and user_id
    """

    def __init__(self, **context: Any) -> None:
        self.context = context
        self.token: Any = None

    def __enter__(self) -> "LogContext":
        self.token = structlog.contextvars.bind_contextvars(**self.context)
        return self

    def __exit__(self, *args: Any) -> None:
        if self.token:
            structlog.contextvars.unbind_contextvars(*self.context.keys())
