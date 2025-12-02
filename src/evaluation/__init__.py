"""
ContractGuard AI - Agent Evaluation Framework

Provides comprehensive evaluation capabilities for agent systems:
- Accuracy metrics
- Latency tracking
- Token usage
- Cost estimation
- Comparison benchmarks

Required for Kaggle Agents Intensive Capstone.
"""

from src.evaluation.evaluator import (
    AgentEvaluator,
    EvaluationResult,
    EvaluationMetrics,
    get_evaluator,
)
from src.evaluation.test_cases import (
    TestCase,
    TestSuite,
    create_contract_test_suite,
    QUICK_TEST_SUITE,
)

__all__ = [
    "AgentEvaluator",
    "EvaluationResult",
    "EvaluationMetrics",
    "get_evaluator",
    "TestCase",
    "TestSuite",
    "create_contract_test_suite",
    "QUICK_TEST_SUITE",
]
