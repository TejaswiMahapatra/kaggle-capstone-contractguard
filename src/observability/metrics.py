"""
Metrics collection for ContractGuard AI.

Provides performance metrics for monitoring agent operations,
tool usage, and system health.
"""

import time
from dataclasses import dataclass, field
from typing import Any
from collections import defaultdict

from src.observability.logger import get_logger

logger = get_logger(__name__)


@dataclass
class OperationMetrics:
    """Metrics for a single operation type."""

    count: int = 0
    total_duration_ms: float = 0.0
    min_duration_ms: float = float("inf")
    max_duration_ms: float = 0.0
    errors: int = 0

    @property
    def avg_duration_ms(self) -> float:
        """Calculate average duration."""
        return self.total_duration_ms / self.count if self.count > 0 else 0.0

    def record(self, duration_ms: float, error: bool = False) -> None:
        """Record a new operation."""
        self.count += 1
        self.total_duration_ms += duration_ms
        self.min_duration_ms = min(self.min_duration_ms, duration_ms)
        self.max_duration_ms = max(self.max_duration_ms, duration_ms)
        if error:
            self.errors += 1


@dataclass
class MetricsCollector:
    """
    Collects and exposes metrics for the application.

    Tracks:
    - Agent invocations and latency
    - Tool usage and performance
    - Query processing times
    - Error rates
    """

    agent_metrics: dict[str, OperationMetrics] = field(
        default_factory=lambda: defaultdict(OperationMetrics)
    )
    tool_metrics: dict[str, OperationMetrics] = field(
        default_factory=lambda: defaultdict(OperationMetrics)
    )
    query_metrics: OperationMetrics = field(default_factory=OperationMetrics)

    def record_agent_call(
        self,
        agent_name: str,
        duration_ms: float,
        error: bool = False,
    ) -> None:
        """Record an agent invocation."""
        self.agent_metrics[agent_name].record(duration_ms, error)
        logger.debug(
            "Agent call recorded",
            agent=agent_name,
            duration_ms=duration_ms,
            error=error,
        )

    def record_tool_call(
        self,
        tool_name: str,
        duration_ms: float,
        error: bool = False,
    ) -> None:
        """Record a tool invocation."""
        self.tool_metrics[tool_name].record(duration_ms, error)
        logger.debug(
            "Tool call recorded",
            tool=tool_name,
            duration_ms=duration_ms,
            error=error,
        )

    def record_query(self, duration_ms: float, error: bool = False) -> None:
        """Record a query processing."""
        self.query_metrics.record(duration_ms, error)

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of all metrics."""
        return {
            "agents": {
                name: {
                    "count": m.count,
                    "avg_duration_ms": round(m.avg_duration_ms, 2),
                    "min_duration_ms": round(m.min_duration_ms, 2) if m.count > 0 else 0,
                    "max_duration_ms": round(m.max_duration_ms, 2),
                    "errors": m.errors,
                    "error_rate": round(m.errors / m.count * 100, 2) if m.count > 0 else 0,
                }
                for name, m in self.agent_metrics.items()
            },
            "tools": {
                name: {
                    "count": m.count,
                    "avg_duration_ms": round(m.avg_duration_ms, 2),
                    "min_duration_ms": round(m.min_duration_ms, 2) if m.count > 0 else 0,
                    "max_duration_ms": round(m.max_duration_ms, 2),
                    "errors": m.errors,
                    "error_rate": round(m.errors / m.count * 100, 2) if m.count > 0 else 0,
                }
                for name, m in self.tool_metrics.items()
            },
            "queries": {
                "count": self.query_metrics.count,
                "avg_duration_ms": round(self.query_metrics.avg_duration_ms, 2),
                "min_duration_ms": (
                    round(self.query_metrics.min_duration_ms, 2)
                    if self.query_metrics.count > 0
                    else 0
                ),
                "max_duration_ms": round(self.query_metrics.max_duration_ms, 2),
                "errors": self.query_metrics.errors,
            },
        }

    def reset(self) -> None:
        """Reset all metrics."""
        self.agent_metrics.clear()
        self.tool_metrics.clear()
        self.query_metrics = OperationMetrics()


class MetricsTimer:
    """
    Context manager for timing operations.

    Example:
        with MetricsTimer() as timer:
            result = do_something()
        print(f"Took {timer.duration_ms}ms")
    """

    def __init__(self) -> None:
        self.start_time: float = 0
        self.end_time: float = 0

    @property
    def duration_ms(self) -> float:
        """Get duration in milliseconds."""
        return (self.end_time - self.start_time) * 1000

    def __enter__(self) -> "MetricsTimer":
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, *args: Any) -> None:
        self.end_time = time.perf_counter()


# Global metrics collector instance
metrics_collector = MetricsCollector()
