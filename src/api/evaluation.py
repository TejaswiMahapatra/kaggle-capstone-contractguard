"""
Evaluation API

REST endpoints for agent evaluation:
- Run evaluations
- Get evaluation results
- Run test suites
- Export metrics
"""

from typing import Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.evaluation import (
    get_evaluator,
    create_contract_test_suite,
    TestSuite,
    QUICK_TEST_SUITE,
)
from src.observability.logger import get_logger

logger = get_logger(__name__, component="evaluation_api")

router = APIRouter(prefix="/api/v1/evaluation", tags=["evaluation"])


class EvaluateRequest(BaseModel):
    """Request to evaluate a single prompt."""
    prompt: str = Field(..., description="Prompt to evaluate")
    expected_output: str | None = Field(None, description="Expected output for comparison")
    evaluate_quality: bool = Field(True, description="Whether to run quality scoring")


class RunSuiteRequest(BaseModel):
    """Request to run a test suite."""
    suite_name: str = Field("standard", description="Test suite: 'standard' or 'quick'")
    parallel: bool = Field(False, description="Run tests in parallel")
    max_concurrency: int = Field(5, description="Max parallel tests")


class EvaluationResponse(BaseModel):
    """Response containing evaluation results."""
    test_case_id: str
    passed: bool
    metrics: dict[str, Any]
    error: str | None = None


@router.post("/evaluate", response_model=EvaluationResponse)
async def evaluate_prompt(request: EvaluateRequest):
    """
    Evaluate a single prompt against the agent.

    Returns metrics including latency, token usage, and quality scores.
    """
    from src.agents import create_orchestrator_agent, create_runner

    evaluator = get_evaluator()

    agent = create_orchestrator_agent()
    runner = create_runner(agent, app_name="contractguard-eval")

    result = await evaluator.evaluate(
        agent_runner=runner,
        prompt=request.prompt,
        expected_output=request.expected_output,
        evaluate_quality=request.evaluate_quality,
    )

    return EvaluationResponse(
        test_case_id=result.test_case_id,
        passed=result.passed,
        metrics={
            "latency_ms": result.metrics.latency_ms,
            "input_tokens": result.metrics.input_tokens,
            "output_tokens": result.metrics.output_tokens,
            "accuracy_score": result.metrics.accuracy_score,
            "relevance_score": result.metrics.relevance_score,
            "estimated_cost": result.metrics.estimated_cost,
        },
        error=result.error,
    )


@router.post("/suite")
async def run_test_suite(request: RunSuiteRequest):
    """
    Run a complete test suite.

    Available suites:
    - 'standard': Full test suite with 20+ test cases
    - 'quick': Quick validation with 3 test cases
    """
    from src.agents import create_orchestrator_agent, create_runner

    evaluator = get_evaluator()

    # Select test suite
    if request.suite_name == "standard":
        suite = create_contract_test_suite()
    elif request.suite_name == "quick":
        suite = QUICK_TEST_SUITE
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown suite: {request.suite_name}. Use 'standard' or 'quick'",
        )

    agent = create_orchestrator_agent()
    runner = create_runner(agent, app_name="contractguard-eval")

    results = await evaluator.run_test_suite(
        agent_runner=runner,
        test_suite=suite,
        parallel=request.parallel,
        max_concurrency=request.max_concurrency,
    )

    # Calculate aggregate metrics
    aggregate = evaluator.get_aggregate_metrics(results)

    return {
        "suite_name": suite.name,
        "total_tests": len(results),
        "passed": sum(1 for r in results if r.passed),
        "failed": sum(1 for r in results if not r.passed),
        "pass_rate": aggregate.pass_rate,
        "aggregate_metrics": aggregate.to_dict(),
        "results": [
            {
                "test_case_id": r.test_case_id,
                "passed": r.passed,
                "latency_ms": r.metrics.latency_ms,
                "error": r.error,
            }
            for r in results
        ],
    }


@router.get("/metrics")
async def get_evaluation_metrics():
    """
    Get aggregate metrics from all evaluations.

    Returns summary statistics including:
    - Pass rate
    - Latency distribution
    - Token usage
    - Cost estimates
    """
    evaluator = get_evaluator()
    metrics = evaluator.get_aggregate_metrics()

    return {
        "total_evaluations": metrics.total_runs,
        "metrics": metrics.to_dict(),
    }


@router.get("/results")
async def get_evaluation_results(
    limit: int = 50,
    format: str = "json",
):
    """
    Get stored evaluation results.

    Args:
        limit: Maximum results to return
        format: Output format ('json')
    """
    evaluator = get_evaluator()

    if format == "json":
        results = evaluator.results[-limit:]
        return {
            "results": [r.to_dict() for r in results],
            "total": len(results),
        }
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown format: {format}",
        )


@router.delete("/results")
async def clear_results():
    """Clear all stored evaluation results."""
    evaluator = get_evaluator()
    count = len(evaluator.results)
    evaluator.clear_results()

    return {
        "message": "Results cleared",
        "cleared_count": count,
    }


@router.get("/suites")
async def list_test_suites():
    """List available test suites."""
    standard = create_contract_test_suite()

    return {
        "suites": [
            {
                "name": "standard",
                "description": standard.description,
                "test_count": len(standard.test_cases),
                "categories": list(set(tc.category for tc in standard.test_cases)),
            },
            {
                "name": "quick",
                "description": QUICK_TEST_SUITE.description,
                "test_count": len(QUICK_TEST_SUITE.test_cases),
                "categories": list(set(tc.category for tc in QUICK_TEST_SUITE.test_cases)),
            },
        ],
    }


@router.get("/suites/{suite_name}")
async def get_test_suite(suite_name: str):
    """Get details of a specific test suite."""
    if suite_name == "standard":
        suite = create_contract_test_suite()
    elif suite_name == "quick":
        suite = QUICK_TEST_SUITE
    else:
        raise HTTPException(status_code=404, detail="Suite not found")

    return suite.to_dict()
