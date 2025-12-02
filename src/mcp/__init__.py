"""
ContractGuard AI - MCP Tools Integration

Model Context Protocol (MCP) tools integration for ContractGuard AI.
Enables both consuming external MCP servers and exposing ContractGuard
tools as an MCP server.

Components:
- MCPToolManager: Manage connections to MCP servers
- ContractGuardMCPServer: Expose ContractGuard tools via MCP
- Pre-configured toolsets for common use cases
"""

from src.mcp.toolset import (
    MCPToolManager,
    get_mcp_tool_manager,
    create_filesystem_toolset,
    create_database_toolset,
)
from src.mcp.server import ContractGuardMCPServer, create_mcp_server

__all__ = [
    "MCPToolManager",
    "get_mcp_tool_manager",
    "create_filesystem_toolset",
    "create_database_toolset",
    "ContractGuardMCPServer",
    "create_mcp_server",
]
