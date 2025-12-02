"""
ContractGuard AI - Agent Tools

Custom tools for contract analysis operations:
- Search Tool: Vector search across contract documents
- Analysis Tool: Deep analysis of contract clauses
- Report Tool: Structured report generation
"""

from src.tools.search_tool import search_contracts, get_contract_context
from src.tools.analysis_tool import analyze_clause, identify_risks, extract_obligations
from src.tools.report_tool import generate_summary, generate_risk_report, generate_comparison_report

__all__ = [
    # Search tools
    "search_contracts",
    "get_contract_context",
    # Analysis tools
    "analyze_clause",
    "identify_risks",
    "extract_obligations",
    # Report tools
    "generate_summary",
    "generate_risk_report",
    "generate_comparison_report",
]
