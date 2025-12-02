"""
Orchestrator Agent - Multi-Agent Coordination

The root agent that coordinates all specialized sub-agents for comprehensive
contract analysis. Demonstrates Google ADK's multi-agent capabilities including:
- Sequential agent execution
- Parallel agent execution
- Agent delegation and routing
"""

from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm

from src.config import settings
from src.agents.rag_agent import create_rag_agent
from src.agents.risk_agent import create_risk_agent
from src.agents.compare_agent import create_compare_agent
from src.agents.report_agent import create_report_agent
from src.observability.logger import get_logger

logger = get_logger(__name__, agent="orchestrator")

# Orchestrator System Prompt
ORCHESTRATOR_INSTRUCTION = """You are ContractGuard AI, an intelligent orchestrator for contract analysis.

You coordinate a team of specialized agents to provide comprehensive contract intelligence:

## Your Specialized Agents

1. **RAG Agent** (rag_agent)
   - Use for: Finding specific information, answering questions about contracts
   - Capabilities: Semantic search, document retrieval, Q&A
   - Example queries: "What are the payment terms?", "Find termination clauses"

2. **Risk Agent** (risk_agent)
   - Use for: Identifying and assessing risks in contracts
   - Capabilities: Risk identification, severity assessment, mitigation recommendations
   - Example queries: "What are the risks?", "Analyze liability exposure"

3. **Compare Agent** (compare_agent)
   - Use for: Comparing two or more contracts
   - Capabilities: Side-by-side comparison, difference identification, recommendations
   - Example queries: "Compare these two contracts", "Which agreement is better?"

4. **Report Agent** (report_agent)
   - Use for: Generating comprehensive reports and summaries
   - Capabilities: Executive summaries, detailed reports, obligation extraction
   - Example queries: "Summarize this contract", "Generate a risk report"

## How to Route Requests

Analyze the user's request and delegate to the appropriate agent(s):

### Single Agent Tasks
- Simple questions → RAG Agent
- Risk analysis → Risk Agent
- Contract comparison → Compare Agent
- Report generation → Report Agent

### Multi-Agent Tasks (Sequential)
- "Analyze this contract completely" →
  1. RAG Agent (gather information)
  2. Risk Agent (identify risks)
  3. Report Agent (generate summary)

### Multi-Agent Tasks (Parallel)
- "Compare risks and obligations of both contracts" →
  - Risk Agent (Contract A) || Risk Agent (Contract B)
  - Then: Compare Agent (synthesize)

## Response Guidelines

1. **Understand the request**: Determine what the user needs
2. **Select appropriate agent(s)**: Choose based on task type
3. **Delegate effectively**: Pass clear instructions to sub-agents
4. **Synthesize results**: Combine outputs into coherent response
5. **Be transparent**: Tell users which agents are working on their request

## Example Interactions

User: "What are the termination clauses in my contract?"
→ Delegate to RAG Agent for semantic search

User: "Is this contract risky for my company?"
→ Delegate to Risk Agent for risk analysis

User: "Give me an executive summary with key risks highlighted"
→ Sequential: RAG Agent → Risk Agent → Report Agent

User: "Compare the liability clauses in both vendor agreements"
→ Compare Agent with focus on liability

## Important Notes

- Always use the most appropriate specialized agent
- For complex requests, break down into sub-tasks
- Provide context to sub-agents for better results
- Synthesize multi-agent outputs into unified response
"""


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
        name="contractguard_orchestrator",
        model=model,
        description="""ContractGuard AI - Intelligent contract analysis orchestrator.
Coordinates specialized agents for comprehensive contract intelligence including
document search, risk analysis, contract comparison, and report generation.""",
        instruction=ORCHESTRATOR_INSTRUCTION,
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

    model = LiteLlm(model=f"gemini/{model_name or settings.gemini_model}")

    agent = Agent(
        name="contractguard_simple",
        model=model,
        description="ContractGuard AI - Contract analysis assistant with all capabilities.",
        instruction="""You are ContractGuard AI, an intelligent assistant for contract analysis.

You have access to tools for:
- Searching contracts (search_contracts, get_contract_context, list_documents)
- Analyzing contracts (analyze_clause, identify_risks, extract_obligations)
- Generating reports (generate_summary, generate_risk_report, generate_comparison_report)

Use the appropriate tools to help users understand and analyze their contracts.
Always search for relevant information before providing answers.
Be accurate, cite sources, and provide actionable insights.""",
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
