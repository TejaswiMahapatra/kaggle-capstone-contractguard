"""
Orchestrator Agent - Multi-Agent Coordination

The root agent that coordinates all specialized sub-agents for comprehensive
contract analysis. Demonstrates Google ADK's multi-agent capabilities including:
- Sequential agent execution
- Parallel agent execution
- Agent delegation and routing

Prompts are loaded from YAML templates to protect against prompt injection.
"""

from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm

from src.config import settings
from src.agents.rag_agent import create_rag_agent
from src.agents.risk_agent import create_risk_agent
from src.agents.compare_agent import create_compare_agent
from src.agents.report_agent import create_report_agent
from src.templates import get_prompt, get_template
from src.observability.logger import get_logger

logger = get_logger(__name__, agent="orchestrator")


def create_orchestrator_agent(model_name: str | None = None) -> Agent:
    """
    Create the main Orchestrator agent with all sub-agents.

    This is the root agent that:
    - Receives user requests
    - Routes to appropriate specialized agents
    - Coordinates multi-agent workflows
    - Synthesizes final responses

    The orchestrator demonstrates ADK's multi-agent capabilities:
    - Sub-agent delegation
    - Sequential execution
    - Parallel execution (when appropriate)

    Args:
        model_name: Optional model override (defaults to settings.gemini_model)

    Returns:
        Configured Google ADK Agent as the main orchestrator
    """
    logger.info("Creating Orchestrator agent with sub-agents")

    # Load template data
    template = get_template("orchestrator")
    instruction = get_prompt("orchestrator", "instruction")
    description = template.get("description", "ContractGuard AI Orchestrator")

    # Configure the model for orchestrator
    model = LiteLlm(model=f"gemini/{model_name or settings.gemini_model}")

    # Create all specialized sub-agents
    rag_agent = create_rag_agent(model_name)
    risk_agent = create_risk_agent(model_name)
    compare_agent = create_compare_agent(model_name)
    report_agent = create_report_agent(model_name)

    logger.info("Sub-agents created: rag, risk, compare, report")

    # Create the orchestrator with sub-agents
    orchestrator = Agent(
        name=template.get("name", "contractguard_orchestrator"),
        model=model,
        description=description,
        instruction=instruction,
        # Sub-agents are registered here for delegation
        sub_agents=[rag_agent, risk_agent, compare_agent, report_agent],
    )

    logger.info("Orchestrator agent created successfully with 4 sub-agents")
    return orchestrator


def create_simple_agent(model_name: str | None = None) -> Agent:
    """
    Create a simplified single agent with all tools.

    Use this for simpler deployments or testing where multi-agent
    coordination is not needed.

    Args:
        model_name: Optional model override

    Returns:
        Single agent with all tools available
    """
    from src.tools.search_tool import search_contracts, get_contract_context, list_documents
    from src.tools.analysis_tool import analyze_clause, identify_risks, extract_obligations
    from src.tools.report_tool import generate_summary, generate_risk_report, generate_comparison_report

    logger.info("Creating simple single agent")

    # Load template data
    template = get_template("simple_agent")
    instruction = get_prompt("simple_agent", "instruction")
    description = template.get("description", "ContractGuard AI Simple Agent")

    model = LiteLlm(model=f"gemini/{model_name or settings.gemini_model}")

    agent = Agent(
        name=template.get("name", "contractguard_simple"),
        model=model,
        description=description,
        instruction=instruction,
        tools=[
            search_contracts,
            get_contract_context,
            list_documents,
            analyze_clause,
            identify_risks,
            extract_obligations,
            generate_summary,
            generate_risk_report,
            generate_comparison_report,
        ],
    )

    logger.info("Simple agent created successfully")
    return agent
