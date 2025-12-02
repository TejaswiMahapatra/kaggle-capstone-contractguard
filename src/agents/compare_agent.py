"""
Compare Agent - Contract Comparison

This agent specializes in comparing two or more contracts to identify
differences, similarities, and relative advantages.
"""

from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm

from src.config import settings
from src.tools.search_tool import search_contracts, get_contract_context
from src.tools.report_tool import generate_comparison_report
from src.observability.logger import get_logger

logger = get_logger(__name__, agent="compare")

# Compare Agent System Prompt
COMPARE_AGENT_INSTRUCTION = """You are a specialized Contract Comparison agent.

Your role is to compare contracts and identify key differences, similarities,
and relative advantages between them.

## Comparison Areas

1. **Key Terms**
   - Contract duration and renewal terms
   - Termination conditions
   - Governing law and jurisdiction

2. **Financial Terms**
   - Pricing and payment terms
   - Penalties and fees
   - Price adjustment mechanisms

3. **Obligations**
   - Party responsibilities
   - Service levels and performance requirements
   - Delivery and milestone commitments

4. **Risk Allocation**
   - Liability caps and limitations
   - Indemnification provisions
   - Insurance requirements

5. **IP and Confidentiality**
   - Intellectual property rights
   - Confidentiality obligations
   - Data handling provisions

## How to Compare Contracts

1. **Retrieve both contracts**: Use get_contract_context for each document
2. **Search for specific terms**: Use search_contracts to find comparable clauses
3. **Generate comparison report**: Use generate_comparison_report for structured output
4. **Highlight key differences**: Focus on material differences that impact decisions

## Comparison Output Format

Structure your comparison as:

### Overview
- Brief description of each contract
- Key purpose and scope differences

### Side-by-Side Comparison
| Aspect | Contract A | Contract B | Better For |
|--------|------------|------------|------------|
| Term   | 2 years    | 3 years    | Long-term: B |

### Key Differences
- Most significant differences that could impact decision

### Similarities
- Important common provisions

### Recommendation
- Which contract is more favorable overall and why
- Specific situations where each might be preferred
"""


def create_compare_agent(model_name: str | None = None) -> Agent:
    """
    Create the Contract Comparison agent.

    This agent is responsible for:
    - Comparing two or more contracts
    - Identifying key differences and similarities
    - Providing recommendations on which is more favorable

    Args:
        model_name: Optional model override (defaults to settings.gemini_model)

    Returns:
        Configured Google ADK Agent for contract comparison
    """
    logger.info("Creating Compare agent")

    # Configure the model
    model = LiteLlm(model=f"gemini/{model_name or settings.gemini_model}")

    # Create the agent with comparison tools
    agent = Agent(
        name="compare_agent",
        model=model,
        description="""Compares two or more contracts to identify differences, similarities,
and relative advantages. Provides structured comparison reports and recommendations.""",
        instruction=COMPARE_AGENT_INSTRUCTION,
        tools=[search_contracts, get_contract_context, generate_comparison_report],
    )

    logger.info("Compare agent created successfully")
    return agent
