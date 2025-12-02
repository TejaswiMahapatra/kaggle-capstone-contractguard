"""
MCP Toolset Manager - Consume External MCP Servers

This module provides integration with external MCP (Model Context Protocol)
servers, allowing ContractGuard agents to use tools from various MCP servers.

Supports:
- Stdio connections (local MCP servers)
- HTTP/SSE connections (remote MCP servers)
- Tool filtering and management
- Multiple concurrent MCP connections
"""

from dataclasses import dataclass, field
from typing import Any
from functools import lru_cache

from src.config import settings
from src.observability.logger import get_logger

logger = get_logger(__name__, component="mcp_toolset")


@dataclass
class MCPServerConfig:
    """Configuration for an MCP server connection."""
    name: str
    connection_type: str  # "stdio" or "sse"
    # For stdio connections
    command: str | None = None
    args: list[str] = field(default_factory=list)
    # For SSE connections
    url: str | None = None
    headers: dict[str, str] = field(default_factory=dict)
    # Tool filtering
    tool_filter: list[str] | None = None
    enabled: bool = True


class MCPToolManager:
    """
    Manages MCP tool connections and provides tools to agents.

    This manager:
    1. Connects to configured MCP servers
    2. Discovers available tools
    3. Provides tools to ADK agents
    4. Handles tool execution proxying

    Example:
        manager = MCPToolManager()
        manager.add_server(MCPServerConfig(
            name="filesystem",
            connection_type="stdio",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-filesystem", "/data"],
        ))

        tools = await manager.get_tools()
        agent = Agent(tools=tools)
    """

    def __init__(self):
        """Initialize the MCP tool manager."""
        self.servers: dict[str, MCPServerConfig] = {}
        self._toolsets: dict[str, Any] = {}
        self._initialized = False
        logger.info("MCP Tool Manager initialized")

    def add_server(self, config: MCPServerConfig):
        """
        Add an MCP server configuration.

        Args:
            config: Server configuration
        """
        self.servers[config.name] = config
        logger.info("MCP server added", name=config.name, type=config.connection_type)

    def remove_server(self, name: str):
        """Remove an MCP server configuration."""
        if name in self.servers:
            del self.servers[name]
            if name in self._toolsets:
                del self._toolsets[name]
            logger.info("MCP server removed", name=name)

    async def initialize(self):
        """
        Initialize connections to all configured MCP servers.

        Creates McpToolset instances for each server.
        """
        if self._initialized:
            return

        try:
            from google.adk.tools.mcp_tool import McpToolset
            from google.adk.tools.mcp_tool.mcp_session_manager import (
                StdioConnectionParams,
                SseConnectionParams,
            )
            from mcp import StdioServerParameters

            for name, config in self.servers.items():
                if not config.enabled:
                    continue

                try:
                    if config.connection_type == "stdio" and config.command:
                        toolset = McpToolset(
                            connection_params=StdioConnectionParams(
                                server_params=StdioServerParameters(
                                    command=config.command,
                                    args=config.args,
                                )
                            ),
                            tool_filter=config.tool_filter,
                        )

                    elif config.connection_type == "sse" and config.url:
                        toolset = McpToolset(
                            connection_params=SseConnectionParams(
                                url=config.url,
                                headers=config.headers,
                            ),
                            tool_filter=config.tool_filter,
                        )

                    else:
                        logger.warning(
                            "Invalid MCP config",
                            name=name,
                            type=config.connection_type,
                        )
                        continue

                    self._toolsets[name] = toolset
                    logger.info("MCP toolset initialized", name=name)

                except Exception as e:
                    logger.error(
                        "Failed to initialize MCP toolset",
                        name=name,
                        error=str(e),
                    )

            self._initialized = True

        except ImportError as e:
            logger.warning(
                "MCP not available - install google-adk[a2a]",
                error=str(e),
            )
            self._initialized = True  # Mark as initialized to avoid retries

    async def get_tools(self, server_name: str | None = None) -> list[Any]:
        """
        Get tools from MCP servers.

        Args:
            server_name: Optional - get tools from specific server only

        Returns:
            List of ADK-compatible tools
        """
        await self.initialize()

        tools = []

        if server_name:
            if server_name in self._toolsets:
                toolset = self._toolsets[server_name]
                # MCPToolset itself acts as a tool provider
                tools.append(toolset)
        else:
            tools.extend(self._toolsets.values())

        return tools

    def list_servers(self) -> list[dict[str, Any]]:
        """List configured MCP servers."""
        return [
            {
                "name": name,
                "type": config.connection_type,
                "enabled": config.enabled,
                "initialized": name in self._toolsets,
            }
            for name, config in self.servers.items()
        ]


# Singleton instance
_mcp_manager: MCPToolManager | None = None


def get_mcp_tool_manager() -> MCPToolManager:
    """Get the singleton MCP tool manager."""
    global _mcp_manager
    if _mcp_manager is None:
        _mcp_manager = MCPToolManager()
        _configure_default_servers(_mcp_manager)
    return _mcp_manager


def _configure_default_servers(manager: MCPToolManager):
    """Configure default MCP servers based on settings."""
    # Filesystem MCP server (for local document access)
    # Only enable if configured
    if hasattr(settings, 'mcp_filesystem_enabled') and settings.mcp_filesystem_enabled:
        manager.add_server(MCPServerConfig(
            name="filesystem",
            connection_type="stdio",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-filesystem", "/app/data"],
            tool_filter=["read_file", "list_directory"],
            enabled=True,
        ))


def create_filesystem_toolset(
    root_path: str = "/app/data",
    tool_filter: list[str] | None = None,
) -> MCPServerConfig:
    """
    Create a filesystem MCP toolset configuration.

    Args:
        root_path: Root path for filesystem access
        tool_filter: Optional list of tools to expose

    Returns:
        MCPServerConfig for filesystem server
    """
    return MCPServerConfig(
        name="filesystem",
        connection_type="stdio",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-filesystem", root_path],
        tool_filter=tool_filter or ["read_file", "list_directory", "search_files"],
        enabled=True,
    )


def create_database_toolset(
    connection_string: str,
    tool_filter: list[str] | None = None,
) -> MCPServerConfig:
    """
    Create a database MCP toolset configuration.

    Uses MCP Toolbox for Databases for BigQuery, PostgreSQL, etc.

    Args:
        connection_string: Database connection string
        tool_filter: Optional list of tools to expose

    Returns:
        MCPServerConfig for database server
    """
    return MCPServerConfig(
        name="database",
        connection_type="sse",
        url="http://localhost:5000/sse",  # MCP Toolbox default
        headers={"X-Database-Connection": connection_string},
        tool_filter=tool_filter or ["query", "schema"],
        enabled=True,
    )


# Pre-built toolset configurations for common scenarios
COMMON_MCP_CONFIGS = {
    "filesystem": lambda path="/data": create_filesystem_toolset(path),
    "brave_search": lambda api_key: MCPServerConfig(
        name="brave_search",
        connection_type="stdio",
        command="npx",
        args=["-y", "@anthropic-ai/mcp-server-brave-search"],
        enabled=bool(api_key),
    ),
    "github": lambda token: MCPServerConfig(
        name="github",
        connection_type="stdio",
        command="npx",
        args=["-y", "@anthropic-ai/mcp-server-github"],
        enabled=bool(token),
    ),
}
