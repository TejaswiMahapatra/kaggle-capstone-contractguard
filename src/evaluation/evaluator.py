"""
Agent Evaluator - Comprehensive Agent Evaluation

Provides evaluation capabilities for measuring agent performance:
- Response quality (accuracy, relevance, completeness)
- Performance metrics (latency, token usage)
- Cost tracking
- Comparison across models/configurations

This fulfills the "Agent Evaluation" requirement for the
Kaggle Agents Intensive capstone.
"""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Awaitable
import statistics

from src.config import settings
from src.observability.logger import get_logger
from src.agents import run_agent

logger = get_logger(__name__, component="evaluator")


@dataclass
class EvaluationMetrics:
    """Metrics from a single evaluation run."""
    # Timing
    latency_ms: float = 0.0
    first_token_ms: float | None = None

    # Tokens
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0

    # Quality scores (0-1)
    accuracy_score: float | None = None
    relevance_score: float | None = None
    completeness_score: float | None = None
    factuality_score: float | None = None

    # Cost (USD)
    estimated_cost: float = 0.0

    # Agent-specific
    tools_used: list[str] = field(default_factory=list)
    sub_agents_invoked: list[str] = field(default_factory=list)
    retrieval_count: int = 0


@dataclass
class EvaluationResult:
    """Result of evaluating an agent on a test case."""
    test_case_id: str
    input_prompt: str
    expected_output: str | None
    actual_output: str
    metrics: EvaluationMetrics
    passed: bool = False
    error: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "test_case_id": self.test_case_id,
            "input_prompt": self.input_prompt,
            "expected_output": self.expected_output,
            "actual_output": self.actual_output,
            "passed": self.passed,
            "error": self.error,
            "timestamp": self.timestamp.isoformat(),
            "metrics": {
                "latency_ms": self.metrics.latency_ms,
                "input_tokens": self.metrics.input_tokens,
                "output_tokens": self.metrics.output_tokens,
                "total_tokens": self.metrics.total_tokens,
                "accuracy_score": self.metrics.accuracy_score,
                "relevance_score": self.metrics.relevance_score,
                "completeness_score": self.metrics.completeness_score,
                "estimated_cost": self.metrics.estimated_cost,
                "tools_used": self.metrics.tools_used,
            },
            "metadata": self.metadata,
        }


@dataclass
class AggregateMetrics:
    """Aggregated metrics across multiple evaluations."""
    total_runs: int = 0
    passed_runs: int = 0
    failed_runs: int = 0
    pass_rate: float = 0.0

    # Latency stats
    avg_latency_ms: float = 0.0
    min_latency_ms: float = 0.0
    max_latency_ms: float = 0.0
    p50_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0

    # Token stats
    total_tokens: int = 0
    avg_tokens_per_run: float = 0.0

    # Quality stats
    avg_accuracy: float | None = None
    avg_relevance: float | None = None

    # Cost
    total_cost: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_runs": self.total_runs,
            "passed_runs": self.passed_runs,
            "failed_runs": self.failed_runs,
            "pass_rate": self.pass_rate,
            "latency": {
                "avg_ms": self.avg_latency_ms,
                "min_ms": self.min_latency_ms,
                "max_ms": self.max_latency_ms,
                "p50_ms": self.p50_latency_ms,
                "p95_ms": self.p95_latency_ms,
            },
            "tokens": {
                "total": self.total_tokens,
                "avg_per_run": self.avg_tokens_per_run,
            },
            "quality": {
                "avg_accuracy": self.avg_accuracy,
                "avg_relevance": self.avg_relevance,
            },
            "total_cost_usd": self.total_cost,
        }


class AgentEvaluator:
    """
    Comprehensive agent evaluation system.

    Provides:
    - Single-run evaluation
    - Batch evaluation
    - Quality scoring (using LLM-as-judge)
    - Performance benchmarking
    - Cost tracking

    Example:
        evaluator = AgentEvaluator()

        # Evaluate a single prompt
        result = await evaluator.evaluate(
            agent=my_agent,
            prompt="What are the payment terms?",
            expected="Net 30 days",
        )

        # Run a full test suite
        results = await evaluator.run_test_suite(
            agent=my_agent,
            test_suite=contract_tests,
        )

        # Get aggregate metrics
        metrics = evaluator.get_aggregate_metrics(results)
    """

    # Pricing per 1M tokens (Gemini 2.0 Flash)
    INPUT_PRICE_PER_1M = 0.075
    OUTPUT_PRICE_PER_1M = 0.30

    def __init__(self, judge_model: str | None = None):
        """
        Initialize evaluator.

        Args:
            judge_model: Model to use for LLM-as-judge evaluation
        """
        self.judge_model = judge_model or settings.gemini_model
        self.results: list[EvaluationResult] = []
        logger.info("Agent evaluator initialized", judge_model=self.judge_model)

    async def evaluate(
        self,
        agent_runner,
        prompt: str,
        expected_output: str | None = None,
        test_case_id: str | None = None,
        evaluate_quality: bool = True,
    ) -> EvaluationResult:
        """
        Evaluate an agent on a single prompt.

        Args:
            agent_runner: ADK Runner instance
            prompt: Input prompt to test
            expected_output: Expected/reference output
            test_case_id: Optional test case identifier
            evaluate_quality: Whether to run quality scoring

        Returns:
            EvaluationResult with metrics and scores
        """
        test_id = test_case_id or f"test_{int(time.time())}"
        metrics = EvaluationMetrics()

        try:
            # Time the execution
            start_time = time.perf_counter()
            result = await run_agent(agent_runner, prompt)
            end_time = time.perf_counter()

            actual_output = str(result)
            metrics.latency_ms = (end_time - start_time) * 1000

            # Estimate tokens (rough heuristic)
            metrics.input_tokens = len(prompt.split()) * 1.3
            metrics.output_tokens = len(actual_output.split()) * 1.3
            metrics.total_tokens = int(metrics.input_tokens + metrics.output_tokens)

            # Calculate cost
            metrics.estimated_cost = self._calculate_cost(
                int(metrics.input_tokens),
                int(metrics.output_tokens),
            )

            # Quality evaluation using LLM-as-judge
            if evaluate_quality and expected_output:
                quality_scores = await self._evaluate_quality(
                    prompt=prompt,
                    expected=expected_output,
                    actual=actual_output,
                )
                metrics.accuracy_score = quality_scores.get("accuracy")
                metrics.relevance_score = quality_scores.get("relevance")
                metrics.completeness_score = quality_scores.get("completeness")
                metrics.factuality_score = quality_scores.get("factuality")

            # Determine pass/fail
            passed = True
            if expected_output and metrics.accuracy_score is not None:
                passed = metrics.accuracy_score >= 0.7

            eval_result = EvaluationResult(
                test_case_id=test_id,
                input_prompt=prompt,
                expected_output=expected_output,
                actual_output=actual_output,
                metrics=metrics,
                passed=passed,
            )

        except Exception as e:
            logger.error("Evaluation failed", test_id=test_id, error=str(e))
            eval_result = EvaluationResult(
                test_case_id=test_id,
                input_prompt=prompt,
                expected_output=expected_output,
                actual_output="",
                metrics=metrics,
                passed=False,
                error=str(e),
            )

        self.results.append(eval_result)
        return eval_result

    async def run_test_suite(
        self,
        agent_runner,
        test_suite: "TestSuite",
        parallel: bool = False,
        max_concurrency: int = 5,
    ) -> list[EvaluationResult]:
        """
        Run a complete test suite.

        Args:
            agent_runner: ADK Runner instance
            test_suite: TestSuite with test cases
            parallel: Run tests in parallel
            max_concurrency: Max parallel tests

        Returns:
            List of EvaluationResults
        """
        from src.evaluation.test_cases import TestSuite

        logger.info(
            "Running test suite",
            suite=test_suite.name,
            cases=len(test_suite.test_cases),
        )

        results = []

        if parallel:
            semaphore = asyncio.Semaphore(max_concurrency)

            async def run_with_semaphore(test_case):
                async with semaphore:
                    return await self.evaluate(
                        agent_runner=agent_runner,
                        prompt=test_case.input_prompt,
                        expected_output=test_case.expected_output,
                        test_case_id=test_case.id,
                    )

            tasks = [run_with_semaphore(tc) for tc in test_suite.test_cases]
            results = await asyncio.gather(*tasks)

        else:
            for test_case in test_suite.test_cases:
                result = await self.evaluate(
                    agent_runner=agent_runner,
                    prompt=test_case.input_prompt,
                    expected_output=test_case.expected_output,
                    test_case_id=test_case.id,
                )
                results.append(result)

        logger.info(
            "Test suite completed",
            suite=test_suite.name,
            passed=sum(1 for r in results if r.passed),
            total=len(results),
        )

        return results

    def get_aggregate_metrics(
        self,
        results: list[EvaluationResult] | None = None,
    ) -> AggregateMetrics:
        """
        Calculate aggregate metrics from results.

        Args:
            results: Results to aggregate (defaults to all stored results)

        Returns:
            AggregateMetrics with summary statistics
        """
        results = results or self.results
        if not results:
            return AggregateMetrics()

        metrics = AggregateMetrics()
        metrics.total_runs = len(results)
        metrics.passed_runs = sum(1 for r in results if r.passed)
        metrics.failed_runs = metrics.total_runs - metrics.passed_runs
        metrics.pass_rate = metrics.passed_runs / metrics.total_runs

        # Latency statistics
        latencies = [r.metrics.latency_ms for r in results]
        metrics.avg_latency_ms = statistics.mean(latencies)
        metrics.min_latency_ms = min(latencies)
        metrics.max_latency_ms = max(latencies)
        metrics.p50_latency_ms = statistics.median(latencies)
        metrics.p95_latency_ms = sorted(latencies)[int(len(latencies) * 0.95)]

        # Token statistics
        metrics.total_tokens = sum(r.metrics.total_tokens for r in results)
        metrics.avg_tokens_per_run = metrics.total_tokens / metrics.total_runs

        # Quality scores
        accuracy_scores = [r.metrics.accuracy_score for r in results if r.metrics.accuracy_score is not None]
        relevance_scores = [r.metrics.relevance_score for r in results if r.metrics.relevance_score is not None]

        if accuracy_scores:
            metrics.avg_accuracy = statistics.mean(accuracy_scores)
        if relevance_scores:
            metrics.avg_relevance = statistics.mean(relevance_scores)

        # Cost
        metrics.total_cost = sum(r.metrics.estimated_cost for r in results)

        return metrics

    async def _evaluate_quality(
        self,
        prompt: str,
        expected: str,
        actual: str,
    ) -> dict[str, float]:
        """
        Use LLM-as-judge to evaluate response quality.

        Scores accuracy, relevance, completeness, and factuality.
        """
        import google.generativeai as genai

        try:
            genai.configure(api_key=settings.google_api_key)
            model = genai.GenerativeModel(self.judge_model)

            judge_prompt = f"""You are an expert evaluator. Score the AI assistant's response.

Question asked: {prompt}

Expected answer: {expected}

Actual answer: {actual}

Score each dimension from 0.0 to 1.0:
1. ACCURACY: How correct is the answer compared to expected?
2. RELEVANCE: How relevant is the answer to the question?
3. COMPLETENESS: How complete is the answer?
4. FACTUALITY: Are the facts stated accurate?

Respond ONLY with JSON in this exact format:
{{"accuracy": 0.X, "relevance": 0.X, "completeness": 0.X, "factuality": 0.X}}"""

            response = model.generate_content(judge_prompt)

            # Parse JSON from response
            import json
            import re

            text = response.text
            # Extract JSON from response
            match = re.search(r'\{[^}]+\}', text)
            if match:
                scores = json.loads(match.group())
                return {
                    "accuracy": float(scores.get("accuracy", 0)),
                    "relevance": float(scores.get("relevance", 0)),
                    "completeness": float(scores.get("completeness", 0)),
                    "factuality": float(scores.get("factuality", 0)),
                }

        except Exception as e:
            logger.error("Quality evaluation failed", error=str(e))

        return {}

    def _calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate estimated cost in USD."""
        input_cost = (input_tokens / 1_000_000) * self.INPUT_PRICE_PER_1M
        output_cost = (output_tokens / 1_000_000) * self.OUTPUT_PRICE_PER_1M
        return input_cost + output_cost

    def clear_results(self):
        """Clear stored results."""
        self.results = []

    def export_results(self, format: str = "json") -> str:
        """Export results to string format."""
        import json

        if format == "json":
            return json.dumps(
                [r.to_dict() for r in self.results],
                indent=2,
            )
        else:
            raise ValueError(f"Unknown format: {format}")


# Singleton instance
_evaluator: AgentEvaluator | None = None


def get_evaluator() -> AgentEvaluator:
    """Get the singleton evaluator."""
    global _evaluator
    if _evaluator is None:
        _evaluator = AgentEvaluator()
    return _evaluator
