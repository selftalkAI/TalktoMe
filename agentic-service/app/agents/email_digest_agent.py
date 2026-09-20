from __future__ import annotations

from typing import Any

from ..workflow.models import PlanStep
from ..workflow.state import RiskClass


class EmailDigestAgent:
    """Read-only email digest — the other half of the MVP's first connector (ADD §22)."""

    name = 'email_digest'

    def plan(self, goal: str) -> list[PlanStep]:
        return [
            PlanStep(
                tool='email',
                operation='summarize_recent_messages',
                risk_class=RiskClass.READ_ONLY,
                args={'goal': goal},
            )
        ]

    def execute_step(self, step: PlanStep) -> dict[str, Any]:
        # Placeholder — no real email connector is wired yet.
        return {'summary': None, 'note': 'email connector not yet implemented'}
