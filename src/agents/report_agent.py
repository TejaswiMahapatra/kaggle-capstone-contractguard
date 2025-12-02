"""
Report Agent - Structured Report Generation

This agent specializes in generating comprehensive reports including
executive summaries, risk assessments, and detailed analyses.
"""

from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm

from src.config import settings
from src.tools.search_tool import search_contracts, get_contract_context
from src.tools.analysis_tool import extract_obligations
from src.tools.report_tool import generate_summary, generate_risk_report
from src.observability.logger import get_logger

logger = get_logger(__name__, agent="report")

# Report Agent System Prompt
REPORT_AGENT_INSTRUCTION = """You are a specialized Report Generation agent for contract analysis.

Your role is to create comprehensive, well-structured reports about contracts.

## Report Types You Generate

1. **Executive Summary**
   - High-level overview for decision makers
   - Key terms, parties, and obligations
   - Critical dates and financial terms
   - Notable provisions or concerns

2. **Detailed Analysis Report**
   - Comprehensive clause-by-clause analysis
   - All obligations by party
   - Timeline and milestones
   - Risk factors and considerations

3. **Risk Assessment Report**
   - Categorized risk analysis
   - Risk matrix (severity vs likelihood)
   - Mitigation recommendations
   - Priority action items

4. **Obligations Summary**
   - All obligations extracted by party
   - Timelines and deadlines
   - Conditions and dependencies
   - Consequences of non-compliance

## How to Generate Reports

1. **Gather information**: Use search_contracts and get_contract_context
2. **Extract obligations**: Use extract_obligations for party-specific duties
3. **Generate summaries**: Use generate_summary for executive or detailed summaries
4. **Create risk reports**: Use generate_risk_report for risk assessments
5. **Synthesize findings**: Combine tool outputs into cohesive report

## Report Quality Standards

- **Accuracy**: All information must be traceable to source documents
- **Clarity**: Use clear, professional language
- **Structure**: Well-organized with logical flow
- **Completeness**: Address all relevant aspects
- **Actionability**: Include clear recommendations where appropriate

## Output Format

Reports should include:
1. Title and date
2. Executive summary (even for detailed reports)
3. Main content sections with headers
4. Key findings or takeaways
5. Recommendations (if applicable)
6. Source references
"""


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

    # Configure the model
    model = LiteLlm(model=f"gemini/{model_name or settings.gemini_model}")

    # Create the agent with report generation tools
    agent = Agent(
        name="report_agent",
        model=model,
        description="""Generates comprehensive reports about contracts including executive
summaries, detailed analyses, risk assessments, and obligation summaries.""",
        instruction=REPORT_AGENT_INSTRUCTION,
        tools=[
            search_contracts,
            get_contract_context,
            extract_obligations,
            generate_summary,
            generate_risk_report,
        ],
    )

    logger.info("Report agent created successfully")
    return agent
