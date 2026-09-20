from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .state import RiskClass, RunStatus, StepStatus


def _new_id() -> str:
    return uuid.uuid4().hex


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class PlanStep:
    """One step of an agent's plan (TDD §8.1 planning contract)."""

    tool: str
    operation: str
    risk_class: RiskClass
    args: dict[str, Any] = field(default_factory=dict)
    step_id: str = field(default_factory=_new_id)
    status: StepStatus = StepStatus.PENDING
    approved: bool = False
    result: dict[str, Any] | None = None


@dataclass
class AgentRun:
    """Durable-shaped agent run record.

    NOTE: this is held in-memory in the Agentic Service for MVP scaffolding.
    Per ADD §11 / TDD §5.1, the durable copy of this state must live in
    PostgreSQL owned by the Orchestration Service before this goes beyond a
    single-process demo — the Agentic Service is not the system of record.
    """

    user_id: str
    agent_name: str
    goal: str
    run_id: str = field(default_factory=_new_id)
    status: RunStatus = RunStatus.CREATED
    plan_version: int = 1
    steps: list[PlanStep] = field(default_factory=list)
    history: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=_utcnow)
    completed_at: datetime | None = None
