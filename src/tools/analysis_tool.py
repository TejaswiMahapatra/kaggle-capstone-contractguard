"""
Analysis tools for contract examination.

These tools enable agents to perform deep analysis on contract content,
including risk identification, obligation extraction, and clause analysis.
"""

from typing import Any

from google.adk.tools import FunctionTool
from google import genai

from src.config import settings
from src.observability.logger import get_logger
from src.observability.tracer import trace_operation

logger = get_logger(__name__, tool="analysis")


async def analyze_clause(
    clause_text: str,
    analysis_type: str = "general",
    context: str | None = None,
) -> dict[str, Any]:
    """
    Perform deep analysis on a contract clause.

    Args:
        clause_text: The text of the clause to analyze
        analysis_type: Type of analysis - "general", "legal", "financial", "compliance"
        context: Optional additional context about the contract

    Returns:
        Dictionary containing analysis results
    """
    with trace_operation("analyze_clause", {"analysis_type": analysis_type}):
        logger.info("Analyzing clause", analysis_type=analysis_type)

        # Build analysis prompt based on type
        analysis_prompts = {
            "general": """Analyze this contract clause and provide:
1. Summary of what this clause does
2. Key terms and conditions
3. Parties' obligations
4. Important dates or deadlines
5. Any notable provisions""",
            "legal": """Perform a legal analysis of this clause:
1. Legal implications and enforceability
2. Potential ambiguities or interpretation issues
3. Standard vs non-standard provisions
4. Jurisdictional considerations
5. Recommended legal review points""",
            "financial": """Analyze the financial aspects of this clause:
1. Payment terms and amounts
2. Financial obligations
3. Penalties or fees
4. Cost implications
5. Financial risks""",
            "compliance": """Analyze compliance aspects of this clause:
1. Regulatory requirements addressed
2. Compliance obligations
3. Reporting requirements
4. Audit provisions
5. Potential compliance gaps""",
        }

        prompt = analysis_prompts.get(analysis_type, analysis_prompts["general"])

        full_prompt = f"""{prompt}

Contract Clause:
{clause_text}

{f"Additional Context: {context}" if context else ""}

Provide a structured analysis:"""

        try:
            client = genai.Client(api_key=settings.google_api_key)
            response = await client.aio.models.generate_content(
                model=settings.gemini_model,
                contents=full_prompt,
            )

            analysis = response.text

            return {
                "success": True,
                "analysis_type": analysis_type,
                "clause_preview": clause_text[:200] + "..." if len(clause_text) > 200 else clause_text,
                "analysis": analysis,
            }

        except Exception as e:
            logger.error("Clause analysis failed", error=str(e))
            return {
                "success": False,
                "error": str(e),
                "analysis_type": analysis_type,
            }


async def identify_risks(
    contract_text: str,
    risk_categories: list[str] | None = None,
) -> dict[str, Any]:
    """
    Identify potential risks in contract content.

    Args:
        contract_text: Contract text to analyze for risks
        risk_categories: Optional list of risk categories to focus on
            Options: "legal", "financial", "operational", "compliance", "reputational"

    Returns:
        Dictionary containing identified risks with severity levels
    """
    with trace_operation("identify_risks"):
        logger.info("Identifying contract risks")

        categories = risk_categories or ["legal", "financial", "operational", "compliance"]
        categories_str = ", ".join(categories)

        prompt = f"""Analyze this contract text and identify potential risks.

Focus on these risk categories: {categories_str}

For each risk identified, provide:
1. Risk Category (from the list above)
2. Risk Description
3. Severity Level (Critical, High, Medium, Low)
4. Affected Clause/Section (if identifiable)
5. Mitigation Recommendation

Contract Text:
{contract_text}

Format your response as a structured list of risks:"""

        try:
            client = genai.Client(api_key=settings.google_api_key)
            response = await client.aio.models.generate_content(
                model=settings.gemini_model,
                contents=prompt,
            )

            return {
                "success": True,
                "risk_categories_analyzed": categories,
                "risk_analysis": response.text,
                "text_analyzed_length": len(contract_text),
            }

        except Exception as e:
            logger.error("Risk identification failed", error=str(e))
            return {
                "success": False,
                "error": str(e),
            }


async def extract_obligations(
    contract_text: str,
    party_name: str | None = None,
) -> dict[str, Any]:
    """
    Extract obligations and commitments from contract text.

    Args:
        contract_text: Contract text to extract obligations from
        party_name: Optional specific party to focus on

    Returns:
        Dictionary containing extracted obligations by party
    """
    with trace_operation("extract_obligations", {"party_name": party_name}):
        logger.info("Extracting obligations", party_name=party_name)

        party_filter = f"Focus specifically on obligations for: {party_name}" if party_name else "Extract obligations for all parties mentioned"

        prompt = f"""Extract all obligations and commitments from this contract text.

{party_filter}

For each obligation, identify:
1. Obligated Party (who must perform)
2. Obligation Description (what they must do)
3. Obligation Type (payment, delivery, service, compliance, reporting, etc.)
4. Timeline/Deadline (if specified)
5. Conditions (any conditions that must be met)
6. Consequences of Non-Compliance (if stated)

Contract Text:
{contract_text}

Provide a structured list of obligations:"""

        try:
            client = genai.Client(api_key=settings.google_api_key)
            response = await client.aio.models.generate_content(
                model=settings.gemini_model,
                contents=prompt,
            )

            return {
                "success": True,
                "party_filter": party_name,
                "obligations": response.text,
                "text_analyzed_length": len(contract_text),
            }

        except Exception as e:
            logger.error("Obligation extraction failed", error=str(e))
            return {
                "success": False,
                "error": str(e),
            }


# Create ADK FunctionTools - FunctionTool derives name from function name
analyze_clause_tool = FunctionTool(func=analyze_clause)
identify_risks_tool = FunctionTool(func=identify_risks)
extract_obligations_tool = FunctionTool(func=extract_obligations)
