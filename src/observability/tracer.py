"""
OpenTelemetry tracing configuration for ContractGuard AI.

Provides distributed tracing for agent operations, tool calls,
and service interactions.
"""

from contextlib import contextmanager
from typing import Any, Generator

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.trace import Tracer, Span, Status, StatusCode

from src.config import settings

# Global tracer instance
_tracer: Tracer | None = None


def setup_tracing() -> None:
    """
    Configure OpenTelemetry tracing.

    Sets up:
    - TracerProvider with service resource
    - OTLP exporter for production
    - Console exporter for development
    """
    global _tracer

    if not settings.enable_tracing:
        return

    # Create resource with service information
    resource = Resource.create({
        "service.name": settings.otel_service_name,
        "service.version": "0.1.0",
        "deployment.environment": settings.app_env,
    })

    # Create and configure TracerProvider
    provider = TracerProvider(resource=resource)

    # Use OTLP exporter if endpoint is configured, otherwise console
    if settings.otel_exporter_otlp_endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

            otlp_exporter = OTLPSpanExporter(
                endpoint=settings.otel_exporter_otlp_endpoint,
            )
            provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
        except ImportError:
            # Fall back to console if OTLP not available
            provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    else:
        # No endpoint configured: Console output
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    # Set global tracer provider
    trace.set_tracer_provider(provider)
    _tracer = trace.get_tracer(__name__)


def get_tracer(name: str = __name__) -> Tracer:
    """
    Get a tracer instance.

    Args:
        name: Tracer name (typically __name__)

    Returns:
        OpenTelemetry Tracer
    """
    return trace.get_tracer(name)


@contextmanager
def trace_operation(
    name: str,
    attributes: dict[str, Any] | None = None,
) -> Generator[Span, None, None]:
    """
    Context manager for tracing operations.

    Args:
        name: Operation name for the span
        attributes: Optional attributes to add to span

    Example:
        with trace_operation("search_contracts", {"query": "termination"}) as span:
            results = search_contracts(query)
            span.set_attribute("result_count", len(results))
    """
    tracer = get_tracer()
    with tracer.start_as_current_span(name) as span:
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, str(value))
        try:
            yield span
            span.set_status(Status(StatusCode.OK))
        except Exception as e:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
            raise


def trace_agent_call(agent_name: str, query: str) -> Any:
    """
    Decorator for tracing agent calls.

    Args:
        agent_name: Name of the agent being called
        query: User query being processed
    """
    def decorator(func: Any) -> Any:
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            with trace_operation(
                f"agent.{agent_name}",
                {"agent.name": agent_name, "agent.query": query[:100]}
            ):
                return await func(*args, **kwargs)
        return wrapper
    return decorator


def trace_tool_call(tool_name: str) -> Any:
    """
    Decorator for tracing tool calls.

    Args:
        tool_name: Name of the tool being called
    """
    def decorator(func: Any) -> Any:
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            with trace_operation(
                f"tool.{tool_name}",
                {"tool.name": tool_name}
            ) as span:
                # Add input parameters as attributes
                if args:
                    span.set_attribute("tool.args", str(args)[:200])
                if kwargs:
                    span.set_attribute("tool.kwargs", str(kwargs)[:200])

                result = await func(*args, **kwargs)

                # Add result info
                span.set_attribute("tool.success", True)
                return result
        return wrapper
    return decorator
