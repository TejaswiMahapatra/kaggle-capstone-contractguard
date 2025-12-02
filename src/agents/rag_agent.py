"""
RAG Agent - Document Retrieval and Question Answering

This agent specializes in retrieving relevant contract content from the
vector database and answering questions based on the retrieved context.

Uses proper RAG pipeline:
1. Query embedding via Gemini/local embeddings
2. Vector search in Weaviate
3. Context-aware answer generation
"""

from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm

from src.config import settings
from src.tools.search_tool import search_contracts_tool, get_contract_context_tool, list_documents_tool
from src.templates import get_prompt, get_template
from src.observability.logger import get_logger

logger = get_logger(__name__, agent="rag")


def create_rag_agent(model_name: str | None = None) -> Agent:
    """
    Create the RAG agent for document retrieval and Q&A.

    This agent is responsible for:
    - Searching contract documents using semantic similarity
    - Retrieving full document context when needed
    - Answering questions based on retrieved content

    Args:
        model_name: Optional model override (defaults to settings.gemini_model)

    Returns:
        Configured Google ADK Agent for RAG operations
    """
    logger.info("Creating RAG agent")

    # Load template data
    template = get_template("rag_agent")
    instruction = get_prompt("rag_agent", "instruction")
    description = template.get("description", "RAG agent for contract retrieval and Q&A")

    # Configure the model - use Gemini via LiteLLM
    model = LiteLlm(model=f"gemini/{model_name or settings.gemini_model}")

    # Create the agent with search tools
    agent = Agent(
        name="rag_agent",
        model=model,
        description=description,
        instruction=instruction,
        tools=[search_contracts_tool, get_contract_context_tool, list_documents_tool],
    )

    logger.info("RAG agent created successfully")
    return agent
