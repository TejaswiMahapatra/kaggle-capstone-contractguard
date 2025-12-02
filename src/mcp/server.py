"""
MCP Server - Expose ContractGuard Tools via MCP

This module implements an MCP server that exposes ContractGuard AI's
tools to external MCP clients. This allows other AI systems and
applications to use ContractGuard's contract analysis capabilities.

Based on the Model Context Protocol specification.
"""

import json
from typing import Any

from src.observability.logger import get_logger

logger = get_logger(__name__, component="mcp_server")


class ContractGuardMCPServer:
    """
    MCP Server exposing ContractGuard tools.

    Implements the MCP server protocol to expose ContractGuard's
    contract analysis tools to external clients.

    Tools exposed:
    - search_contracts: Semantic contract search
    - analyze_risk: Risk analysis
    - compare_contracts: Contract comparison
    - generate_report: Report generation
    - extract_clauses: Clause extraction

    Example:
        server = ContractGuardMCPServer()
        # Run with MCP transport
        await server.run_stdio()  # For stdio transport
        # Or expose via HTTP
        app.include_router(server.get_http_router())
    """

    def __init__(self):
        """Initialize MCP server with ContractGuard tools."""
        self.tools = self._register_tools()
        logger.info("ContractGuard MCP Server initialized", tools=len(self.tools))

    def _register_tools(self) -> dict[str, dict[str, Any]]:
        """Register ContractGuard tools for MCP exposure."""
        return {
            "search_contracts": {
                "name": "search_contracts",
                "description": "Search contracts using semantic similarity. Find specific clauses, terms, or information across stored contracts.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query for contract content",
                        },
                        "top_k": {
                            "type": "integer",
                            "description": "Number of results to return",
                            "default": 5,
                        },
                        "document_id": {
                            "type": "string",
                            "description": "Optional: limit search to specific document",
                        },
                    },
                    "required": ["query"],
                },
            },
            "analyze_risk": {
                "name": "analyze_risk",
                "description": "Analyze a contract for potential risks across legal, financial, operational, and compliance categories.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "document_id": {
                            "type": "string",
                            "description": "Document ID to analyze",
                        },
                        "categories": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Risk categories to analyze",
                            "default": ["legal", "financial", "operational"],
                        },
                    },
                    "required": ["document_id"],
                },
            },
            "compare_contracts": {
                "name": "compare_contracts",
                "description": "Compare two or more contracts to identify differences and similarities.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "document_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 2,
                            "description": "Document IDs to compare",
                        },
                        "focus_areas": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Specific areas to focus comparison",
                        },
                    },
                    "required": ["document_ids"],
                },
            },
            "generate_report": {
                "name": "generate_report",
                "description": "Generate a comprehensive report for a contract document.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "document_id": {
                            "type": "string",
                            "description": "Document ID to report on",
                        },
                        "report_type": {
                            "type": "string",
                            "enum": ["summary", "risk", "obligations", "full"],
                            "description": "Type of report to generate",
                            "default": "summary",
                        },
                    },
                    "required": ["document_id"],
                },
            },
            "extract_clauses": {
                "name": "extract_clauses",
                "description": "Extract specific clause types from a contract.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "document_id": {
                            "type": "string",
                            "description": "Document ID to extract from",
                        },
                        "clause_types": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Types of clauses to extract",
                            "default": ["termination", "payment", "liability", "confidentiality"],
                        },
                    },
                    "required": ["document_id"],
                },
            },
        }

    async def list_tools(self) -> list[dict[str, Any]]:
        """
        MCP list_tools handler.

        Returns list of available tools per MCP spec.
        """
        return list(self.tools.values())

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """
        MCP call_tool handler.

        Executes a tool and returns results in MCP format.

        Args:
            name: Tool name to execute
            arguments: Tool arguments

        Returns:
            MCP-formatted content blocks
        """
        if name not in self.tools:
            return [{
                "type": "text",
                "text": json.dumps({"error": f"Unknown tool: {name}"}),
            }]

        try:
            result = await self._execute_tool(name, arguments)
            return [{
                "type": "text",
                "text": json.dumps(result),
            }]
        except Exception as e:
            logger.error("Tool execution failed", tool=name, error=str(e))
            return [{
                "type": "text",
                "text": json.dumps({"error": str(e)}),
            }]

    async def _execute_tool(
        self,
        name: str,
        arguments: dict[str, Any],
    ) -> Any:
        """Execute a ContractGuard tool."""
        if name == "search_contracts":
            from src.tools.search_tool import _search_contracts_impl
            return await _search_contracts_impl(
                query=arguments["query"],
                top_k=arguments.get("top_k", 5),
                document_id=arguments.get("document_id"),
            )

        elif name == "analyze_risk":
            from src.agents import create_risk_agent, create_runner, run_agent

            agent = create_risk_agent()
            runner = create_runner(agent, app_name="contractguard-mcp")

            categories = arguments.get("categories", ["legal", "financial", "operational"])
            prompt = f"""Analyze document {arguments['document_id']} for risks.
Focus on categories: {', '.join(categories)}
Provide structured risk assessment with severity ratings."""

            result = await run_agent(runner, prompt)
            return {"analysis": str(result)}

        elif name == "compare_contracts":
            from src.agents import create_compare_agent, create_runner, run_agent

            agent = create_compare_agent()
            runner = create_runner(agent, app_name="contractguard-mcp")

            doc_ids = arguments["document_ids"]
            focus = arguments.get("focus_areas", [])

            prompt = f"""Compare contracts: {', '.join(doc_ids)}
{f'Focus on: {", ".join(focus)}' if focus else 'Comprehensive comparison'}"""

            result = await run_agent(runner, prompt)
            return {"comparison": str(result)}

        elif name == "generate_report":
            from src.agents import create_report_agent, create_runner, run_agent

            agent = create_report_agent()
            runner = create_runner(agent, app_name="contractguard-mcp")

            report_type = arguments.get("report_type", "summary")
            prompt = f"""Generate a {report_type} report for document {arguments['document_id']}"""

            result = await run_agent(runner, prompt)
            return {"report": str(result)}

        elif name == "extract_clauses":
            from src.tools.search_tool import _search_contracts_impl

            clause_types = arguments.get("clause_types", [
                "termination", "payment", "liability", "confidentiality"
            ])

            results = {}
            for clause_type in clause_types:
                search_result = await _search_contracts_impl(
                    query=f"{clause_type} clause",
                    top_k=3,
                    document_id=arguments["document_id"],
                )
                results[clause_type] = search_result.get("results", [])

            return {"clauses": results}

        else:
            raise ValueError(f"Unknown tool: {name}")

    def get_fastapi_router(self):
        """
        Get FastAPI router for HTTP-based MCP transport.

        Returns:
            FastAPI APIRouter with MCP endpoints
        """
        from fastapi import APIRouter
        from fastapi.responses import JSONResponse

        router = APIRouter(prefix="/mcp", tags=["mcp"])

        @router.get("/tools")
        async def list_tools_endpoint():
            """List available MCP tools."""
            tools = await self.list_tools()
            return JSONResponse(content={"tools": tools})

        @router.post("/tools/{tool_name}")
        async def call_tool_endpoint(tool_name: str, arguments: dict[str, Any]):
            """Execute an MCP tool."""
            result = await self.call_tool(tool_name, arguments)
            return JSONResponse(content={"content": result})

        return router


def create_mcp_server() -> ContractGuardMCPServer:
    """
    Factory function to create MCP server.

    Returns:
        Configured ContractGuardMCPServer instance
    """
    return ContractGuardMCPServer()


# Default MCP server instance
default_mcp_server = create_mcp_server()
