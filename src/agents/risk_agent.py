"""
Risk Agent - Contract Risk Analysis

This agent specializes in identifying and analyzing risks in contract documents.
It can assess legal, financial, operational, and compliance risks.
"""

from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm

from src.config import settings
from src.tools.search_tool import search_contracts_tool, get_contract_context_tool
from src.tools.analysis_tool import identify_risks_tool, analyze_clause_tool
from src.templates import get_prompt, get_template
from src.observability.logger import get_logger

logger = get_logger(__name__, agent="risk")


def create_risk_agent(model_name: str | None = None) -> Agent:
    """
    Create the Risk Analysis agent.

    This agent is responsible for:
    - Identifying risks across multiple categories
    - Assessing risk severity and impact
    - Providing mitigation recommendations

    Args:
        model_name: Optional model override (defaults to settings.gemini_model)

    Returns:
        Configured Google ADK Agent for risk analysis
    """
    logger.info("Creating Risk agent")

    # Load template data
    template = get_template("risk_agent")
    instruction = get_prompt("risk_agent", "instruction")
    description = template.get("description", "Risk analysis agent for contract review")

    # Configure the model
    model = LiteLlm(model=f"gemini/{model_name or settings.gemini_model}")

    # Create the agent with analysis tools
    agent = Agent(
        name="risk_agent",
        model=model,
        description=description,
        instruction=instruction,
        tools=[search_contracts_tool, get_contract_context_tool, identify_risks_tool, analyze_clause_tool],
    )

    logger.info("Risk agent created successfully")
    return agent
