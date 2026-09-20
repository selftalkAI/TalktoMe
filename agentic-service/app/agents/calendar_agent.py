from __future__ import annotations

from typing import Any

from ..workflow.models import PlanStep
from ..workflow.state import RiskClass


class CalendarAgent:
    """Read-only calendar lookup — one half of the MVP's first connector (ADD §22).

    Plans a single READ_ONLY step, so it never needs approval under the
    default PolicyGate rules (FR-AGT-003).
    """

    name = 'calendar'

    def plan(self, goal: str) -> list[PlanStep]:
        return [
            PlanStep(
                tool='calendar',
                operation='list_upcoming_events',
                risk_class=RiskClass.READ_ONLY,
                args={'goal': goal},
            )
        ]

    def execute_step(self, step: PlanStep) -> dict[str, Any]:
        # Placeholder — no real calendar connector is wired yet. A real
        # implementation calls a scoped, user-authorized calendar API here
        # (TDD §8.2: exact operation, minimum scope, no long-lived secrets in the model).
        return {'events': [], 'note': 'calendar connector not yet implemented'}
