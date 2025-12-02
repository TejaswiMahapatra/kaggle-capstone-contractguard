"""
Report generation tools for contract analysis.

These tools enable agents to generate structured reports including
summaries, risk assessments, and comparison reports.
"""

from typing import Any

from google.adk.tools import FunctionTool
from google import genai

from src.config import settings
from src.observability.logger import get_logger
from src.observability.tracer import trace_operation

logger = get_logger(__name__, tool="report")


async def _generate_summary_impl(
    contract_text: str,
    summary_type: str = "executive",
    max_length: int = 500,
) -> dict[str, Any]:
    """
    Generate a summary of contract content.

    Args:
        contract_text: Contract text to summarize
        summary_type: Type of summary - "executive", "detailed", "bullet_points"
        max_length: Approximate maximum length of summary in words

    Returns:
        Dictionary containing the generated summary
    """
    with trace_operation("generate_summary", {"summary_type": summary_type}):
        logger.info("Generating summary", summary_type=summary_type)

        summary_instructions = {
            "executive": f"""Create an executive summary (approximately {max_length} words) that covers:
- Purpose of the contract
- Key parties involved
- Main terms and conditions
- Critical dates and deadlines
- Financial terms
- Notable provisions or concerns

Write in a professional, concise style suitable for senior executives.""",
            "detailed": f"""Create a detailed summary (approximately {max_length} words) that covers:
- Full context and background
- All parties and their roles
- Complete terms and conditions
- All obligations by party
- Timeline and milestones
- Financial arrangements
- Risk factors
- Termination conditions

Be thorough while remaining clear and organized.""",
            "bullet_points": f"""Create a bullet-point summary (approximately {max_length} words) with sections:

**Contract Overview**
- [Key facts about the contract]

**Parties**
- [List all parties and roles]

**Key Terms**
- [Main terms and conditions]

**Obligations**
- [Key obligations by party]

**Financial Terms**
- [Payment and financial details]

**Important Dates**
- [Critical dates and deadlines]

**Risks & Concerns**
- [Any notable risks]""",
        }

        prompt = f"""{summary_instructions.get(summary_type, summary_instructions["executive"])}

Contract Text:
{contract_text}

Generate the summary:"""

        try:
            client = genai.Client(api_key=settings.google_api_key)
            response = await client.aio.models.generate_content(
                model=settings.gemini_model,
                contents=prompt,
            )

            return {
                "success": True,
                "summary_type": summary_type,
                "summary": response.text,
                "source_length": len(contract_text),
            }

        except Exception as e:
            logger.error("Summary generation failed", error=str(e))
            return {
                "success": False,
                "error": str(e),
                "summary_type": summary_type,
            }


async def _generate_risk_report_impl(
    risks: str,
    contract_summary: str | None = None,
) -> dict[str, Any]:
    """
    Generate a formal risk assessment report.

    Args:
        risks: Previously identified risks (from identify_risks tool)
        contract_summary: Optional contract summary for context

    Returns:
        Dictionary containing the risk report
    """
    with trace_operation("generate_risk_report"):
        logger.info("Generating risk report")

        context_section = f"""
Contract Summary:
{contract_summary}
""" if contract_summary else ""

        prompt = f"""Generate a formal Risk Assessment Report based on the identified risks.

{context_section}

Identified Risks:
{risks}

Create a professional report with these sections:

# Risk Assessment Report

## Executive Summary
[Brief overview of overall risk posture]

## Risk Matrix
[Categorize risks by severity and likelihood]

## Detailed Risk Analysis
[For each risk: description, impact, probability, affected areas]

## Risk Mitigation Recommendations
[Specific actions to address each risk]

## Priority Actions
[Ranked list of most critical actions needed]

## Conclusion
[Overall assessment and next steps]

Generate the report:"""

        try:
            client = genai.Client(api_key=settings.google_api_key)
            response = await client.aio.models.generate_content(
                model=settings.gemini_model,
                contents=prompt,
            )

            return {
                "success": True,
                "report_type": "risk_assessment",
                "report": response.text,
            }

        except Exception as e:
            logger.error("Risk report generation failed", error=str(e))
            return {
                "success": False,
                "error": str(e),
            }


async def _generate_comparison_report_impl(
    contract_a_text: str,
    contract_b_text: str,
    contract_a_name: str = "Contract A",
    contract_b_name: str = "Contract B",
    comparison_focus: list[str] | None = None,
) -> dict[str, Any]:
    """
    Generate a comparison report between two contracts.

    Args:
        contract_a_text: Text of first contract
        contract_b_text: Text of second contract
        contract_a_name: Display name for first contract
        contract_b_name: Display name for second contract
        comparison_focus: Optional list of areas to focus on
            Options: "terms", "obligations", "risks", "financial", "timeline"

    Returns:
        Dictionary containing the comparison report
    """
    with trace_operation("generate_comparison_report"):
        logger.info(
            "Generating comparison report",
            contract_a=contract_a_name,
            contract_b=contract_b_name,
        )

        focus_areas = comparison_focus or ["terms", "obligations", "risks", "financial"]
        focus_str = ", ".join(focus_areas)

        prompt = f"""Generate a detailed comparison report between two contracts.

**{contract_a_name}:**
{contract_a_text[:5000]}{"..." if len(contract_a_text) > 5000 else ""}

**{contract_b_name}:**
{contract_b_text[:5000]}{"..." if len(contract_b_text) > 5000 else ""}

Focus comparison on: {focus_str}

Create a professional comparison report:

# Contract Comparison Report

## Overview
[Brief description of both contracts and comparison purpose]

## Side-by-Side Comparison

### Key Terms
| Aspect | {contract_a_name} | {contract_b_name} | Analysis |
|--------|-------------------|-------------------|----------|
[Compare key terms]

### Obligations
[Compare obligations for each party]

### Financial Terms
[Compare financial aspects]

### Risk Comparison
[Compare risk profiles]

### Timeline & Deadlines
[Compare important dates]

## Key Differences
[Highlight most significant differences]

## Similarities
[Note important similarities]

## Recommendations
[Which contract is more favorable and why]

## Conclusion
[Summary of comparison findings]

Generate the report:"""

        try:
            client = genai.Client(api_key=settings.google_api_key)
            response = await client.aio.models.generate_content(
                model=settings.gemini_model,
                contents=prompt,
            )

            return {
                "success": True,
                "report_type": "comparison",
                "contracts_compared": [contract_a_name, contract_b_name],
                "focus_areas": focus_areas,
                "report": response.text,
            }

        except Exception as e:
            logger.error("Comparison report generation failed", error=str(e))
            return {
                "success": False,
                "error": str(e),
            }


# Create ADK FunctionTools - FunctionTool derives name from function name
generate_summary = FunctionTool(func=_generate_summary_impl)
generate_risk_report = FunctionTool(func=_generate_risk_report_impl)
generate_comparison_report = FunctionTool(func=_generate_comparison_report_impl)
