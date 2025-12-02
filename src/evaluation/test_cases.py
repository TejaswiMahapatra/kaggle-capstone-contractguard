"""
Test Cases and Test Suites for Agent Evaluation

Provides structured test cases for evaluating ContractGuard agents:
- Contract search tests
- Risk analysis tests
- Comparison tests
- Report generation tests
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TestCase:
    """A single test case for agent evaluation."""
    id: str
    name: str
    input_prompt: str
    expected_output: str | None = None
    category: str = "general"
    difficulty: str = "medium"  # easy, medium, hard
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "input_prompt": self.input_prompt,
            "expected_output": self.expected_output,
            "category": self.category,
            "difficulty": self.difficulty,
            "tags": self.tags,
            "metadata": self.metadata,
        }


@dataclass
class TestSuite:
    """Collection of test cases."""
    name: str
    description: str
    test_cases: list[TestCase] = field(default_factory=list)
    version: str = "1.0.0"

    def add_case(self, test_case: TestCase):
        """Add a test case to the suite."""
        self.test_cases.append(test_case)

    def get_by_category(self, category: str) -> list[TestCase]:
        """Get test cases by category."""
        return [tc for tc in self.test_cases if tc.category == category]

    def get_by_difficulty(self, difficulty: str) -> list[TestCase]:
        """Get test cases by difficulty."""
        return [tc for tc in self.test_cases if tc.difficulty == difficulty]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "test_cases": [tc.to_dict() for tc in self.test_cases],
            "total_cases": len(self.test_cases),
        }


def create_contract_test_suite() -> TestSuite:
    """
    Create the standard ContractGuard test suite.

    Returns a comprehensive test suite covering:
    - Basic search queries
    - Risk identification
    - Clause extraction
    - Contract comparison
    - Report generation
    """
    suite = TestSuite(
        name="ContractGuard Standard Tests",
        description="Comprehensive test suite for contract analysis agents",
        version="1.0.0",
    )

    # ==========================================================================
    # Search Tests
    # ==========================================================================
    suite.add_case(TestCase(
        id="search_001",
        name="Basic Payment Terms Search",
        input_prompt="What are the payment terms in the contract?",
        expected_output="Payment terms typically include Net 30, Net 60, or specific due dates",
        category="search",
        difficulty="easy",
        tags=["payment", "terms", "basic"],
    ))

    suite.add_case(TestCase(
        id="search_002",
        name="Termination Clause Search",
        input_prompt="Find all termination clauses and conditions",
        expected_output="Termination clauses should include notice periods, causes for termination, and effects",
        category="search",
        difficulty="medium",
        tags=["termination", "clauses"],
    ))

    suite.add_case(TestCase(
        id="search_003",
        name="Confidentiality Provisions",
        input_prompt="What are the confidentiality and NDA provisions?",
        expected_output="Confidentiality provisions should cover definition of confidential information, obligations, and duration",
        category="search",
        difficulty="medium",
        tags=["confidentiality", "nda"],
    ))

    suite.add_case(TestCase(
        id="search_004",
        name="Liability Limits Search",
        input_prompt="What are the liability limitations and caps?",
        expected_output="Liability limitations should include caps, exclusions, and indemnification",
        category="search",
        difficulty="hard",
        tags=["liability", "indemnification", "legal"],
    ))

    # ==========================================================================
    # Risk Analysis Tests
    # ==========================================================================
    suite.add_case(TestCase(
        id="risk_001",
        name="General Risk Assessment",
        input_prompt="What are the main risks in this contract?",
        expected_output="Risk assessment should identify legal, financial, and operational risks",
        category="risk",
        difficulty="medium",
        tags=["risk", "assessment"],
    ))

    suite.add_case(TestCase(
        id="risk_002",
        name="Financial Risk Analysis",
        input_prompt="Analyze the financial risks and payment-related concerns",
        expected_output="Financial risks include payment delays, unclear terms, penalties",
        category="risk",
        difficulty="medium",
        tags=["financial", "risk", "payment"],
    ))

    suite.add_case(TestCase(
        id="risk_003",
        name="Compliance Risk",
        input_prompt="Are there any compliance risks or regulatory concerns?",
        expected_output="Compliance risks relate to data protection, industry regulations, and legal requirements",
        category="risk",
        difficulty="hard",
        tags=["compliance", "regulatory", "legal"],
    ))

    suite.add_case(TestCase(
        id="risk_004",
        name="One-Sided Terms Detection",
        input_prompt="Identify any one-sided or unfair terms that favor one party",
        expected_output="One-sided terms include asymmetric obligations, broad indemnification, or unlimited liability",
        category="risk",
        difficulty="hard",
        tags=["fairness", "one-sided", "negotiation"],
    ))

    # ==========================================================================
    # Clause Extraction Tests
    # ==========================================================================
    suite.add_case(TestCase(
        id="extract_001",
        name="Key Dates Extraction",
        input_prompt="Extract all important dates from the contract",
        expected_output="Key dates include effective date, expiration date, renewal dates, and deadlines",
        category="extraction",
        difficulty="easy",
        tags=["dates", "extraction"],
    ))

    suite.add_case(TestCase(
        id="extract_002",
        name="Parties Identification",
        input_prompt="Who are the parties to this agreement?",
        expected_output="Parties should be clearly identified with full legal names and addresses",
        category="extraction",
        difficulty="easy",
        tags=["parties", "identification"],
    ))

    suite.add_case(TestCase(
        id="extract_003",
        name="Obligations Extraction",
        input_prompt="What are the key obligations of each party?",
        expected_output="Obligations should be listed for each party with specific requirements and timelines",
        category="extraction",
        difficulty="medium",
        tags=["obligations", "requirements"],
    ))

    # ==========================================================================
    # Comparison Tests
    # ==========================================================================
    suite.add_case(TestCase(
        id="compare_001",
        name="Basic Contract Comparison",
        input_prompt="Compare these two contracts and highlight the differences",
        expected_output="Comparison should identify differences in terms, pricing, and conditions",
        category="comparison",
        difficulty="medium",
        tags=["comparison", "differences"],
    ))

    suite.add_case(TestCase(
        id="compare_002",
        name="Payment Terms Comparison",
        input_prompt="Compare the payment terms between these contracts",
        expected_output="Payment comparison should cover timing, amounts, and conditions",
        category="comparison",
        difficulty="medium",
        tags=["payment", "comparison"],
    ))

    # ==========================================================================
    # Report Generation Tests
    # ==========================================================================
    suite.add_case(TestCase(
        id="report_001",
        name="Executive Summary",
        input_prompt="Generate an executive summary of this contract",
        expected_output="Executive summary should include key terms, parties, value, and important dates",
        category="report",
        difficulty="medium",
        tags=["summary", "executive"],
    ))

    suite.add_case(TestCase(
        id="report_002",
        name="Risk Report",
        input_prompt="Generate a comprehensive risk report",
        expected_output="Risk report should categorize risks, assess severity, and provide recommendations",
        category="report",
        difficulty="hard",
        tags=["risk", "report"],
    ))

    suite.add_case(TestCase(
        id="report_003",
        name="Obligations Checklist",
        input_prompt="Create a checklist of all obligations with deadlines",
        expected_output="Checklist should include all obligations, responsible parties, and due dates",
        category="report",
        difficulty="medium",
        tags=["obligations", "checklist"],
    ))

    # ==========================================================================
    # Edge Cases and Complex Queries
    # ==========================================================================
    suite.add_case(TestCase(
        id="edge_001",
        name="Ambiguous Query Handling",
        input_prompt="Tell me about the contract",
        expected_output="Should ask for clarification or provide general overview",
        category="edge",
        difficulty="easy",
        tags=["ambiguous", "clarification"],
    ))

    suite.add_case(TestCase(
        id="edge_002",
        name="Off-Topic Query",
        input_prompt="What's the weather like today?",
        expected_output="Should redirect to contract-related queries",
        category="edge",
        difficulty="easy",
        tags=["off-topic", "redirect"],
    ))

    suite.add_case(TestCase(
        id="edge_003",
        name="Complex Multi-Part Query",
        input_prompt="Find the termination clauses, assess their risk, and compare with standard market terms",
        expected_output="Should address all parts: find clauses, assess risk, and provide market context",
        category="edge",
        difficulty="hard",
        tags=["complex", "multi-part"],
    ))

    return suite


# Pre-built test suites
STANDARD_TEST_SUITE = create_contract_test_suite()

# Quick test suite for rapid testing
QUICK_TEST_SUITE = TestSuite(
    name="Quick Tests",
    description="Fast test suite for rapid validation",
    test_cases=[
        TestCase(
            id="quick_001",
            name="Simple Search",
            input_prompt="What is this contract about?",
            category="search",
            difficulty="easy",
        ),
        TestCase(
            id="quick_002",
            name="Risk Check",
            input_prompt="Are there any major risks?",
            category="risk",
            difficulty="medium",
        ),
        TestCase(
            id="quick_003",
            name="Summary Request",
            input_prompt="Summarize the key points",
            category="report",
            difficulty="medium",
        ),
    ],
)
