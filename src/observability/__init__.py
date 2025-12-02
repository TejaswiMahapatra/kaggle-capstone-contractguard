"""
ContractGuard AI - Observability

Monitoring and tracing capabilities:
- Tracer: OpenTelemetry tracing for agent operations
- Logger: Structured logging with context
- Metrics: Performance metrics collection
"""

from src.observability.tracer import setup_tracing, get_tracer
from src.observability.logger import setup_logging, get_logger
from src.observability.metrics import MetricsCollector

__all__ = [
    "setup_tracing",
    "get_tracer",
    "setup_logging",
    "get_logger",
    "MetricsCollector",
]
