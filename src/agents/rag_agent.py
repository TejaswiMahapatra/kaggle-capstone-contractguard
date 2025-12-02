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
from src.tools.search_tool import search_contracts, get_contract_context, list_documents
from src.observability.logger import get_logger

logger = get_logger(__name__, agent="rag")

# RAG Agent System Prompt
RAG_AGENT_INSTRUCTION = """You are a specialized RAG (Retrieval-Augmented Generation) agent for contract analysis.

Your role is to:
1. Search through contract documents to find relevant information using semantic search
2. Retrieve specific clauses, sections, or full documents when needed
3. Answer questions accurately based on the retrieved contract content
4. Provide well-sourced responses with references to specific clauses

## How to Answer Questions

1. **Always search first**: Before answering any question about contracts, use the search_contracts tool
2. **Use multiple searches if needed**: Complex questions may require multiple searches with different queries
3. **Cite your sources**: Reference the clause number, section title, or document when providing information
4. **Be precise**: Contract analysis requires accuracy - don't make assumptions
5. **Acknowledge limitations**: If information isn't found, clearly state that

## Available Tools

- **search_contracts**: Semantic search across all contracts. Use natural language queries.
  Example: search_contracts(query="payment terms and deadlines")

- **get_contract_context**: Get the full text of a specific document.
  Use when you need complete context, not just snippets.
  Example: get_contract_context(document_id="abc-123")

- **list_documents**: See what documents are available in the collection.

## Response Format

When answering questions:
1. State what you found
2. Quote relevant text when appropriate
3. Cite the source (document, section, clause)
4. Provide your analysis or answer
5. Note any limitations or uncertainties

Example response:
"Based on the Service Agreement (Section 5.2 - Termination), either party may terminate
this agreement with 30 days written notice. The relevant clause states: '[quote]'.
This means..."
"""


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

    # Configure the model - use Gemini via LiteLLM
    model = LiteLlm(model=f"gemini/{model_name or settings.gemini_model}")

    # Create the agent with search tools
    agent = Agent(
        name="rag_agent",
        model=model,
        description="""Retrieves relevant contract content using semantic search and answers
questions based on the retrieved context. Specializes in finding specific clauses,
terms, and sections within legal documents.""",
        instruction=RAG_AGENT_INSTRUCTION,
        tools=[search_contracts, get_contract_context, list_documents],
    )

    logger.info("RAG agent created successfully")
    return agent
