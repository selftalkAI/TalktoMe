from __future__ import annotations

from .base import Agent
from .calendar_agent import CalendarAgent
from .email_digest_agent import EmailDigestAgent
from .smart_agent import SmartAgent

_REGISTRY: dict[str, Agent] = {
    CalendarAgent.name: CalendarAgent(),
    EmailDigestAgent.name: EmailDigestAgent(),
    SmartAgent.name: SmartAgent(),
}


def get_agent(name: str) -> Agent:
    agent = _REGISTRY.get(name)
    if agent is None:
        supported = ', '.join(sorted(_REGISTRY))
        raise KeyError(f"Unknown agent '{name}'. Supported: {supported}.")
    return agent


def list_agents() -> list[str]:
    return sorted(_REGISTRY)


__all__ = ['Agent', 'get_agent', 'list_agents']
