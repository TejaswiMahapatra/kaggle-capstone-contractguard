"""
Search tools for contract document retrieval.

These tools perform semantic search using Weaviate vector database
with proper embedding-based retrieval.
"""

from typing import Any

from google.adk.tools import FunctionTool

from src.observability.logger import get_logger
from src.observability.tracer import trace_operation

logger = get_logger(__name__, tool="search")


async def search_contracts(
    query: str,
    collection_name: str = "contracts",
    top_k: int = 5,
    document_id: str | None = None,
) -> dict[str, Any]:
    """
    Search contracts using semantic similarity with Weaviate vector database.

    This tool:
    1. Embeds the query using the configured embedding model
    2. Performs vector similarity search in Weaviate
    3. Returns ranked results with text and metadata

    Args:
        query: Natural language search query
        collection_name: Vector collection to search (default: "contracts")
        top_k: Number of results to return (default: 5)
        document_id: Optional - filter to search within a specific document only

    Returns:
        Dictionary containing:
        - success: Whether the search succeeded
        - query: The original query
        - result_count: Number of results found
        - results: List of results with text, score, and metadata
    """
    with trace_operation("search_contracts", {"query": query[:50], "top_k": top_k}):
        logger.info("Searching contracts", query=query[:100], top_k=top_k)

        try:
            # Import services
            from src.services.embedding_service import get_embedding_service
            from src.services.vector_service import get_vector_service

            embedding_service = get_embedding_service()
            vector_service = get_vector_service()

            # Step 1: Embed the query
            query_vector = await embedding_service.embed_query(query)
            logger.debug("Query embedded", dimension=len(query_vector))

            # Step 2: Build filters if document_id specified
            filters = None
            if document_id:
                filters = {"document_id": document_id}

            # Step 3: Perform vector search
            results = await vector_service.search(
                collection_name=collection_name,
                query_vector=query_vector,
                top_k=top_k,
                filters=filters,
            )

            # Step 4: Format results
            formatted_results = []
            for i, result in enumerate(results):
                formatted_results.append({
                    "rank": i + 1,
                    "text": result.text,
                    "score": round(result.score, 4),
                    "metadata": {
                        "document_id": result.metadata.get("document_id", ""),
                        "document_name": result.metadata.get("document_name", ""),
                        "clause_number": result.metadata.get("clause_number", ""),
                        "section_title": result.metadata.get("section_title", ""),
                        "page_number": result.metadata.get("page_number", 0),
                        "chunk_type": result.metadata.get("chunk_type", ""),
                    },
                })

            logger.info(
                "Search completed",
                result_count=len(formatted_results),
                top_score=formatted_results[0]["score"] if formatted_results else 0,
            )

            return {
                "success": True,
                "query": query,
                "result_count": len(formatted_results),
                "results": formatted_results,
            }

        except Exception as e:
            logger.error("Search failed", error=str(e))
            return {
                "success": False,
                "error": str(e),
                "query": query,
                "results": [],
            }


async def get_contract_context(
    document_id: str,
    collection_name: str = "contracts",
) -> dict[str, Any]:
    """
    Get full context for a specific contract document.

    Retrieves all chunks belonging to a document, ordered by position,
    to provide complete context for analysis.

    Args:
        document_id: ID of the document to retrieve
        collection_name: Vector collection name (default: "contracts")

    Returns:
        Dictionary containing:
        - success: Whether retrieval succeeded
        - document_id: The document ID
        - text: Full concatenated document text
        - chunk_count: Number of chunks retrieved
        - sections: List of unique sections found
    """
    with trace_operation("get_contract_context", {"document_id": document_id}):
        logger.info("Getting contract context", document_id=document_id)

        try:
            from src.services.vector_service import get_vector_service

            vector_service = get_vector_service()

            # Get all chunks for this document
            results = await vector_service.get_by_document_id(
                collection_name=collection_name,
                document_id=document_id,
            )

            if not results:
                return {
                    "success": False,
                    "error": "Document not found",
                    "document_id": document_id,
                }

            # Combine all chunks into full context
            full_text = "\n\n".join([r.text for r in results])

            # Extract unique sections
            sections = list(set(
                r.metadata.get("section_title", "")
                for r in results
                if r.metadata.get("section_title")
            ))

            # Get document name from first chunk
            document_name = results[0].metadata.get("document_name", "") if results else ""

            logger.info(
                "Context retrieved",
                document_id=document_id,
                chunks=len(results),
                sections=len(sections),
            )

            return {
                "success": True,
                "document_id": document_id,
                "document_name": document_name,
                "text": full_text,
                "chunk_count": len(results),
                "sections": sections,
                "total_characters": len(full_text),
            }

        except Exception as e:
            logger.error("Failed to get context", error=str(e))
            return {
                "success": False,
                "error": str(e),
                "document_id": document_id,
            }


async def list_documents(
    collection_name: str = "contracts",
) -> dict[str, Any]:
    """
    List documents available in the contract collection.

    Useful for understanding what contracts are available to query.

    Args:
        collection_name: Vector collection name (default: "contracts")

    Returns:
        Dictionary containing:
        - success: Whether operation succeeded
        - collection_name: The collection queried
        - total_chunks: Total number of chunks in collection
        - collection_exists: Whether the collection exists
    """
    with trace_operation("list_documents"):
        logger.info("Listing documents", collection=collection_name)

        try:
            from src.services.vector_service import get_vector_service

            vector_service = get_vector_service()
            stats = await vector_service.get_collection_stats(collection_name)

            return {
                "success": True,
                "collection_name": collection_name,
                "total_chunks": stats.get("count", 0),
                "collection_exists": stats.get("exists", False),
            }

        except Exception as e:
            logger.error("Failed to list documents", error=str(e))
            return {
                "success": False,
                "error": str(e),
            }


# Create ADK FunctionTools - FunctionTool derives name from function name
search_contracts_tool = FunctionTool(func=search_contracts)
get_contract_context_tool = FunctionTool(func=get_contract_context)
list_documents_tool = FunctionTool(func=list_documents)
