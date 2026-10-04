from __future__ import annotations

from .amygdala import Amygdala
from .anterior_cingulate import AnteriorCingulate
from .base import Agent
from .brain_one import BrainOne
from .broca import Broca
from .calendar_agent import CalendarAgent
from .core_agent import CoreAgent
from .email_digest_agent import EmailDigestAgent
from .hippocampus import Hippocampus
from .prefrontal_cortex import PrefrontalCortex
from .sensory_cortex import SensoryCortex
from .thalamus import Thalamus
from .world_knowledge import WorldKnowledge

# The cognitive agents (Thalamus, Sensory Cortex, Hippocampus, Prefrontal
# Cortex, Amygdala, Broca's Area, Anterior Cingulate) are Brain 2's reasoning, each doing one
# distinct job, each with its own LangGraph-backed workflow (see
# `_graph.py`) — replacing the single SmartAgent/ProfileAgent classes that
# used to hold all six behind an if/elif dispatch. WorldKnowledge is not one
# of them — it's a gateway (ADD §4 Intelligence plane), the one place outside
# knowledge is allowed in, same distinction as the Model Gateway. CalendarAgent
# and EmailDigestAgent stay unnamed by this metaphor too: they're external
# connectors (ADD §4 Action plane), not one of Brain 2's own cognitive
# functions. BrainOne is neither — it's a SIMULATION-ONLY stand-in for User 1
# (Brain 1), used by `orchestration-service/scripts/simulate_brain1_brain2_hour.py`
# to run an unattended, scripted conversation with Brain 2; the real app never
# calls it (see its module docstring).
_REGISTRY: dict[str, Agent] = {
    Thalamus.name: Thalamus(),
    SensoryCortex.name: SensoryCortex(),
    Hippocampus.name: Hippocampus(),
    PrefrontalCortex.name: PrefrontalCortex(),
    Amygdala.name: Amygdala(),
    Broca.name: Broca(),
    AnteriorCingulate.name: AnteriorCingulate(),
    WorldKnowledge.name: WorldKnowledge(),
    CoreAgent.name: CoreAgent(),
    CalendarAgent.name: CalendarAgent(),
    EmailDigestAgent.name: EmailDigestAgent(),
    BrainOne.name: BrainOne(),
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
