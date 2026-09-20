from __future__ import annotations

from typing import Any, Protocol

from ..workflow.models import PlanStep


class Agent(Protocol):
    """The shape every individual agentic flow must implement.

    plan() is the Planner role (ADD §8): it proposes steps but has no
    authority to run them — the workflow engine's PolicyGate decides that.
    execute_step() is the Executor role: it only runs once the engine has
    already cleared the step through policy.
    """

    name: str

    def plan(self, goal: str) -> list[PlanStep]: ...

    def execute_step(self, step: PlanStep) -> dict[str, Any]: ...
