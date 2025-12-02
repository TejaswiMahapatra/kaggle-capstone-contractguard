"""
ContractGuard AI - A2A Protocol Support

Agent-to-Agent communication using Google's A2A Protocol.
Enables remote agents to interact with ContractGuard AI agents.

Components:
- AgentCard: Agent capability discovery
- A2AServer: Expose agents via A2A protocol
- A2AClient: Consume remote A2A agents
"""

from src.a2a.agent_card import (
    AgentCard,
    AgentSkill,
    create_agent_card,
)
from src.a2a.server import A2AServer, create_a2a_server
from src.a2a.client import A2AClient

__all__ = [
    "AgentCard",
    "AgentSkill",
    "create_agent_card",
    "A2AServer",
    "create_a2a_server",
    "A2AClient",
]
