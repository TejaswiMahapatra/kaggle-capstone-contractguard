"""
Report Agent - Structured Report Generation

This agent specializes in generating comprehensive reports including
executive summaries, risk assessments, and detailed analyses.
"""

from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm

from src.config import settings
from src.tools.search_tool import search_contracts_tool, get_contract_context_tool
from src.tools.analysis_tool import extract_obligations_tool
from src.tools.report_tool import generate_summary_tool, generate_risk_report_tool
from src.templates import get_prompt, get_template
from src.observability.logger import get_logger

logger = get_logger(__name__, agent="report")


def create_report_agent(model_name: str | None = None) -> Agent:
    """
    Create the Report Generation agent.

    This agent is responsible for:
    - Generating executive summaries
    - Creating detailed analysis reports
    - Producing risk assessment reports
    - Extracting and summarizing obligations

    Args:
        model_name: Optional model override (defaults to settings.gemini_model)

    Returns:
        Configured Google ADK Agent for report generation
    """
    logger.info("Creating Report agent")

    # Load template data
    template = get_template("report_agent")
    instruction = get_prompt("report_agent", "instruction")
    description = template.get("description", "Report generation agent for contract analysis")

    # Configure the model
    model = LiteLlm(model=f"gemini/{model_name or settings.gemini_model}")

    # Create the agent with report generation tools
    agent = Agent(
        name="report_agent",
        model=model,
        description=description,
        instruction=instruction,
        tools=[
            search_contracts_tool,
            get_contract_context_tool,
            extract_obligations_tool,
            generate_summary_tool,
            generate_risk_report_tool,
        ],
    )

    logger.info("Report agent created successfully")
    return agent
