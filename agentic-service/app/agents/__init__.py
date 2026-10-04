from __future__ import annotations

from .amygdala import Amygdala
from .anterior_cingulate import AnteriorCingulate
from .base import Agent
from .broca import Broca
from .core_agent import CoreAgent
from .hippocampus import Hippocampus
from .prefrontal_cortex import PrefrontalCortex
from .sensory_cortex import SensoryCortex
from .thalamus import Thalamus
from .world_knowledge import WorldKnowledge

# Brain 2's cognitive agents (Thalamus, Sensory Cortex, Hippocampus, Prefrontal
# Cortex, Amygdala, Broca's Area, Anterior Cingulate) each do distinct jobs, each
# with its own LangGraph workflow (`_graph.py`). CoreAgent runs one step of a
# Brain 1 core agent's investigation (Building_Brain1.md §10). WorldKnowledge is
# a gateway for outside knowledge, not a cognitive organ.
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
