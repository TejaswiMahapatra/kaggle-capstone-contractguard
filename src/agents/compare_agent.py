"""
Compare Agent - Contract Comparison

This agent specializes in comparing two or more contracts to identify
differences, similarities, and relative advantages.
"""

from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm

from src.config import settings
from src.tools.search_tool import search_contracts_tool, get_contract_context_tool
from src.tools.report_tool import generate_comparison_report_tool
from src.templates import get_prompt, get_template
from src.observability.logger import get_logger

logger = get_logger(__name__, agent="compare")


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

    # Load template data
    template = get_template("compare_agent")
    instruction = get_prompt("compare_agent", "instruction")
    description = template.get("description", "Contract comparison agent")

    # Configure the model
    model = LiteLlm(model=f"gemini/{model_name or settings.gemini_model}")

    # Create the agent with comparison tools
    agent = Agent(
        name="compare_agent",
        model=model,
        description=description,
        instruction=instruction,
        tools=[search_contracts_tool, get_contract_context_tool, generate_comparison_report_tool],
    )

    logger.info("Compare agent created successfully")
    return agent
