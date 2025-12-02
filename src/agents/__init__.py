"""
ContractGuard AI - Multi-Agent System

This module contains all Google ADK agents:
- Orchestrator: Root agent that coordinates all sub-agents
- RAG Agent: Document retrieval and question answering
- Risk Agent: Contract risk analysis
- Compare Agent: Contract comparison
- Report Agent: Structured report generation
"""

import uuid
from typing import Any

from google.adk.agents import BaseAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from src.agents.orchestrator import create_orchestrator_agent, create_simple_agent
from src.agents.rag_agent import create_rag_agent
from src.agents.risk_agent import create_risk_agent
from src.agents.compare_agent import create_compare_agent
from src.agents.report_agent import create_report_agent


# Shared session service for all runners
_session_service = InMemorySessionService()


def create_runner(agent: BaseAgent, app_name: str = "contractguard") -> Runner:
    """Create a Runner with the required session service.

    Args:
        agent: The agent to run
        app_name: Application name for the runner

    Returns:
        Configured Runner instance
    """
    return Runner(
        agent=agent,
        app_name=app_name,
        session_service=_session_service,
    )


async def run_agent(runner: Runner, prompt: str, user_id: str | None = None, session_id: str | None = None) -> Any:
    """Run an agent with a prompt and return the final response.

    This helper function wraps the new ADK run_async API which requires
    user_id, session_id and returns an AsyncGenerator.

    Args:
        runner: The Runner instance to use
        prompt: The prompt to send to the agent
        user_id: Optional user ID (generated if not provided)
        session_id: Optional session ID (generated if not provided)

    Returns:
        The final response content from the agent
    """
    # Generate IDs if not provided
    if user_id is None:
        user_id = f"user_{uuid.uuid4().hex[:8]}"
    if session_id is None:
        session_id = f"session_{uuid.uuid4().hex[:8]}"

    # Create session first (required by ADK)
    await _session_service.create_session(
        app_name=runner.app_name,
        user_id=user_id,
        session_id=session_id,
    )

    # Create the message content
    message = types.Content(
        role="user",
        parts=[types.Part(text=prompt)],
    )

    # Run the agent and collect the final response
    final_response = None
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=message,
    ):
        # Events can have different types - we want the final agent response
        if hasattr(event, "content") and event.content:
            content = event.content
            # Extract text from Content object if possible
            if hasattr(content, "parts") and content.parts:
                texts = []
                for part in content.parts:
                    if hasattr(part, "text") and part.text:
                        texts.append(part.text)
                if texts:
                    final_response = "\n".join(texts)
                else:
                    final_response = content
            else:
                final_response = content
        elif hasattr(event, "text"):
            final_response = event.text

    return final_response


__all__ = [
    "create_orchestrator_agent",
    "create_simple_agent",
    "create_rag_agent",
    "create_risk_agent",
    "create_compare_agent",
    "create_report_agent",
    "create_runner",
    "run_agent",
]
