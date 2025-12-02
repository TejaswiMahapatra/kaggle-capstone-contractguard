"""
A2A Agent Card - Capability Discovery

Agent Cards are JSON documents that describe an agent's capabilities,
enabling other agents to discover and interact with it via A2A protocol.

Based on Google's A2A Protocol specification v0.3.
"""

from dataclasses import dataclass, field
from typing import Any
import json

from src.config import settings


@dataclass
class AgentSkill:
    """
    Represents a specific skill/capability of an agent.

    Skills are the primary way agents advertise their capabilities
    to other agents in the A2A protocol.
    """
    id: str
    name: str
    description: str
    input_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
    tags: list[str] = field(default_factory=list)
    examples: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to A2A-compatible dictionary."""
        result = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
        }
        if self.input_schema:
            result["inputSchema"] = self.input_schema
        if self.output_schema:
            result["outputSchema"] = self.output_schema
        if self.tags:
            result["tags"] = self.tags
        if self.examples:
            result["examples"] = self.examples
        return result


@dataclass
class AgentCard:
    """
    A2A Agent Card - describes agent capabilities for discovery.

    The Agent Card is the cornerstone of A2A's capability discovery mechanism.
    It contains:
    - Agent identity and metadata
    - Supported skills/capabilities
    - Connection information
    - Authentication requirements
    """
    name: str
    description: str
    version: str = "1.0.0"
    protocol_version: str = "0.3"
    url: str = ""
    skills: list[AgentSkill] = field(default_factory=list)
    authentication: dict[str, Any] | None = None
    capabilities: dict[str, bool] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to A2A-compatible JSON format."""
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "protocolVersion": self.protocol_version,
            "url": self.url,
            "skills": [skill.to_dict() for skill in self.skills],
            "authentication": self.authentication,
            "capabilities": {
                "streaming": self.capabilities.get("streaming", True),
                "pushNotifications": self.capabilities.get("push_notifications", False),
                "stateManagement": self.capabilities.get("state_management", True),
                **self.capabilities,
            },
            "metadata": self.metadata,
        }

    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentCard":
        """Create AgentCard from dictionary."""
        skills = [
            AgentSkill(
                id=s["id"],
                name=s["name"],
                description=s["description"],
                input_schema=s.get("inputSchema"),
                output_schema=s.get("outputSchema"),
                tags=s.get("tags", []),
                examples=s.get("examples", []),
            )
            for s in data.get("skills", [])
        ]

        return cls(
            name=data["name"],
            description=data["description"],
            version=data.get("version", "1.0.0"),
            protocol_version=data.get("protocolVersion", "0.3"),
            url=data.get("url", ""),
            skills=skills,
            authentication=data.get("authentication"),
            capabilities=data.get("capabilities", {}),
            metadata=data.get("metadata", {}),
        )


def create_agent_card(
    base_url: str | None = None,
    include_all_skills: bool = True,
) -> AgentCard:
    """
    Create the ContractGuard AI Agent Card.

    This card describes all capabilities of the ContractGuard AI system
    for discovery by other A2A-compatible agents.

    Args:
        base_url: Base URL where the agent is hosted
        include_all_skills: Whether to include all agent skills

    Returns:
        Configured AgentCard for ContractGuard AI
    """
    url = base_url or f"http://{settings.api_host}:{settings.api_port}"

    skills = []

    if include_all_skills:
        # Contract Search & Retrieval
        skills.append(AgentSkill(
            id="contract_search",
            name="Contract Search",
            description="Search contracts using semantic similarity. Find specific clauses, terms, or information across all stored contracts.",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "top_k": {"type": "integer", "default": 5},
                    "document_id": {"type": "string", "description": "Optional: limit to specific document"},
                },
                "required": ["query"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "results": {"type": "array", "items": {"type": "object"}},
                    "total": {"type": "integer"},
                },
            },
            tags=["search", "retrieval", "rag"],
            examples=[
                {"query": "termination clauses"},
                {"query": "payment terms", "top_k": 10},
            ],
        ))

        # Risk Analysis
        skills.append(AgentSkill(
            id="risk_analysis",
            name="Risk Analysis",
            description="Analyze contracts for legal, financial, and operational risks. Provides severity ratings and mitigation recommendations.",
            input_schema={
                "type": "object",
                "properties": {
                    "document_id": {"type": "string", "description": "Document to analyze"},
                    "risk_categories": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Categories: legal, financial, operational, compliance, reputational",
                    },
                },
                "required": ["document_id"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "risks": {"type": "array"},
                    "overall_risk_score": {"type": "number"},
                    "recommendations": {"type": "array"},
                },
            },
            tags=["analysis", "risk", "compliance"],
        ))

        # Contract Comparison
        skills.append(AgentSkill(
            id="contract_comparison",
            name="Contract Comparison",
            description="Compare two or more contracts to identify differences, improvements, and potential issues.",
            input_schema={
                "type": "object",
                "properties": {
                    "document_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 2,
                        "description": "Documents to compare",
                    },
                    "focus_areas": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Areas to focus comparison on",
                    },
                },
                "required": ["document_ids"],
            },
            tags=["analysis", "comparison"],
        ))

        # Report Generation
        skills.append(AgentSkill(
            id="report_generation",
            name="Report Generation",
            description="Generate comprehensive reports including executive summaries, risk assessments, and obligation extracts.",
            input_schema={
                "type": "object",
                "properties": {
                    "document_id": {"type": "string"},
                    "report_type": {
                        "type": "string",
                        "enum": ["executive_summary", "risk_report", "obligations", "full_analysis"],
                    },
                    "format": {
                        "type": "string",
                        "enum": ["markdown", "json", "html"],
                        "default": "markdown",
                    },
                },
                "required": ["document_id", "report_type"],
            },
            tags=["report", "summary", "documentation"],
        ))

        # Document Ingestion
        skills.append(AgentSkill(
            id="document_ingestion",
            name="Document Ingestion",
            description="Upload and process PDF contracts for analysis. Includes OCR, chunking, and vector embedding.",
            input_schema={
                "type": "object",
                "properties": {
                    "file_url": {"type": "string", "format": "uri"},
                    "collection_name": {"type": "string", "default": "contracts"},
                },
                "required": ["file_url"],
            },
            tags=["ingestion", "upload", "processing"],
        ))

        # Q&A
        skills.append(AgentSkill(
            id="contract_qa",
            name="Contract Q&A",
            description="Ask questions about contracts and receive accurate, sourced answers using RAG.",
            input_schema={
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "document_id": {"type": "string", "description": "Optional: limit to specific document"},
                    "session_id": {"type": "string", "description": "For conversation continuity"},
                },
                "required": ["question"],
            },
            tags=["qa", "search", "conversation"],
        ))

    return AgentCard(
        name="ContractGuard AI",
        description="""Enterprise Contract Intelligence Platform powered by Google ADK.

Provides comprehensive contract analysis including:
- Semantic search across contract libraries
- Risk identification and assessment
- Contract comparison and benchmarking
- Report generation and summaries
- Interactive Q&A with contract context

Built for enterprise-scale contract management with multi-agent orchestration.""",
        version="0.1.0",
        protocol_version="0.3",
        url=url,
        skills=skills,
        authentication={
            "type": "none",  # Can be "bearer", "api_key", "oauth2"
            # "bearerToken": {"header": "Authorization"},
        },
        capabilities={
            "streaming": True,
            "push_notifications": False,
            "state_management": True,
            "long_running_tasks": True,
            "batch_processing": True,
        },
        metadata={
            "provider": "ContractGuard AI",
            "category": "enterprise",
            "industry": "legal",
            "supported_formats": ["pdf"],
            "languages": ["en"],
            "max_document_size_mb": 50,
        },
    )


# Pre-configured agent card instance
default_agent_card = create_agent_card()
