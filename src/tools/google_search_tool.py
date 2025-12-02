"""
Built-in Google Search Tool

A built-in tool using Google's grounding/search capabilities for handling
generic queries. When users ask non-contract questions, this tool can
provide helpful answers while guiding them back to contract-related queries.

This demonstrates the use of built-in tools as required by the Kaggle
Agents Intensive capstone.
"""

from typing import Any
from google.adk.tools import FunctionTool

from src.config import settings
from src.observability.logger import get_logger

logger = get_logger(__name__, component="google_search_tool")


async def _google_search_impl(
    query: str,
    num_results: int = 5,
) -> dict[str, Any]:
    """
    Search the web using Google Search.

    This tool handles generic queries that are outside ContractGuard's
    contract analysis domain. It provides helpful answers while
    suggesting contract-related alternatives.

    Args:
        query: Search query
        num_results: Number of results to return

    Returns:
        Search results with helpful guidance
    """
    import httpx

    logger.info("Google search requested", query=query, num_results=num_results)

    # Check if query is contract-related (suggest using contract tools instead)
    contract_keywords = [
        "contract", "agreement", "clause", "termination", "liability",
        "indemnity", "payment", "term", "obligation", "breach", "warranty",
        "confidential", "nda", "sla", "msa", "sow", "amendment"
    ]

    query_lower = query.lower()
    is_contract_related = any(kw in query_lower for kw in contract_keywords)

    if is_contract_related:
        return {
            "suggestion": "This appears to be a contract-related query!",
            "recommendation": "For contract analysis, please use the contract search or analysis tools instead.",
            "available_tools": [
                "search_contracts - Search your uploaded contracts",
                "analyze_contract - Get detailed contract analysis",
                "compare_contracts - Compare multiple contracts",
            ],
            "query_received": query,
        }

    # For non-contract queries, use Google's search API
    try:
        # Use Google Custom Search API if available
        api_key = settings.google_api_key
        search_engine_id = getattr(settings, 'google_search_engine_id', None)

        if api_key and search_engine_id:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://www.googleapis.com/customsearch/v1",
                    params={
                        "key": api_key,
                        "cx": search_engine_id,
                        "q": query,
                        "num": min(num_results, 10),
                    },
                    timeout=10.0,
                )

                if response.status_code == 200:
                    data = response.json()
                    results = []

                    for item in data.get("items", []):
                        results.append({
                            "title": item.get("title", ""),
                            "snippet": item.get("snippet", ""),
                            "link": item.get("link", ""),
                        })

                    return {
                        "query": query,
                        "results": results,
                        "total_results": data.get("searchInformation", {}).get("totalResults", 0),
                        "note": "For contract-specific queries, consider using ContractGuard's specialized tools.",
                    }

        # Fallback: Provide helpful response without actual search
        return {
            "query": query,
            "message": "Web search is available but not configured.",
            "suggestion": "For contract-related questions, I can help you search and analyze your contracts!",
            "how_to_enable": "Set GOOGLE_SEARCH_ENGINE_ID in your environment to enable web search.",
            "contract_capabilities": [
                "Upload and analyze PDF contracts",
                "Search across all your contracts semantically",
                "Identify risks and obligations",
                "Compare multiple contracts",
                "Generate executive summaries",
            ],
        }

    except Exception as e:
        logger.error("Google search failed", error=str(e))
        return {
            "error": "Search temporarily unavailable",
            "suggestion": "Try asking a contract-related question instead!",
            "example_queries": [
                "What are the payment terms in my contract?",
                "Find termination clauses",
                "What risks are in this agreement?",
            ],
        }


async def _web_grounding_impl(
    query: str,
    context: str | None = None,
) -> dict[str, Any]:
    """
    Use Google's grounding feature to enhance responses with web data.

    This provides factual grounding for responses using Google's
    built-in search capabilities in Gemini.

    Args:
        query: Query to ground with web data
        context: Optional context to include

    Returns:
        Grounded response with citations
    """
    import google.generativeai as genai

    logger.info("Web grounding requested", query=query)

    try:
        # Configure Gemini with search grounding
        genai.configure(api_key=settings.google_api_key)

        model = genai.GenerativeModel(
            model_name=settings.gemini_model,
            tools="google_search_retrieval",  # Enable search grounding
        )

        prompt = query
        if context:
            prompt = f"Context: {context}\n\nQuestion: {query}"

        response = model.generate_content(prompt)

        # Extract grounding metadata if available
        grounding_metadata = None
        if hasattr(response, 'candidates') and response.candidates:
            candidate = response.candidates[0]
            if hasattr(candidate, 'grounding_metadata'):
                grounding_metadata = candidate.grounding_metadata

        return {
            "query": query,
            "response": response.text,
            "grounding": grounding_metadata,
            "model": settings.gemini_model,
        }

    except Exception as e:
        logger.error("Web grounding failed", error=str(e))
        return {
            "query": query,
            "error": str(e),
            "fallback": "Please try rephrasing your question or ask about contract analysis.",
        }


async def _redirect_to_contracts_impl(
    original_query: str,
) -> dict[str, Any]:
    """
    Gently redirect users from generic queries to contract-focused queries.

    This tool helps guide users back to ContractGuard's core functionality
    when they ask off-topic questions.

    Args:
        original_query: The user's original query

    Returns:
        Helpful redirection with suggestions
    """
    suggestions = [
        {
            "category": "Document Search",
            "examples": [
                "Search my contracts for payment terms",
                "Find all confidentiality clauses",
                "What contracts mention liability limits?",
            ],
        },
        {
            "category": "Risk Analysis",
            "examples": [
                "What are the risks in my NDA?",
                "Analyze the liability exposure in this contract",
                "Are there any concerning clauses?",
            ],
        },
        {
            "category": "Contract Comparison",
            "examples": [
                "Compare the payment terms between these two vendors",
                "Which contract has better termination rights?",
                "Show differences between v1 and v2 of this agreement",
            ],
        },
        {
            "category": "Report Generation",
            "examples": [
                "Generate an executive summary",
                "Create a risk report for my contract",
                "Extract all obligations from this agreement",
            ],
        },
    ]

    return {
        "message": "I'm ContractGuard AI, specialized in contract analysis!",
        "original_query": original_query,
        "what_i_can_do": [
            "Search and analyze uploaded contracts",
            "Identify risks and obligations",
            "Compare multiple contracts",
            "Generate reports and summaries",
            "Answer questions about specific clauses",
        ],
        "suggestions": suggestions,
        "tip": "Upload a contract PDF first, then ask me questions about it!",
    }


# Create FunctionTool instances for ADK - FunctionTool derives name from function name
google_search = FunctionTool(func=_google_search_impl)
web_grounding = FunctionTool(func=_web_grounding_impl)
redirect_to_contracts = FunctionTool(func=_redirect_to_contracts_impl)

# Export all tools
__all__ = [
    "google_search",
    "web_grounding",
    "redirect_to_contracts",
    "_google_search_impl",
    "_web_grounding_impl",
    "_redirect_to_contracts_impl",
]
