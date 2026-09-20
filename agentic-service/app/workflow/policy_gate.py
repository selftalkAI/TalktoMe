from __future__ import annotations

from .models import PlanStep
from .state import PolicyDecision, RiskClass

_APPROVAL_REQUIRED_RISK_CLASSES = {RiskClass.CONSEQUENTIAL_WRITE, RiskClass.HIGH_IMPACT}


class PolicyGate:
    """Deterministic authorization check (ADR-007) — the planner/agent output

    proposes a step; this is the only thing allowed to decide whether it runs.
    FR-AGT-003: CONSEQUENTIAL_WRITE and HIGH_IMPACT steps always require
    explicit approval unless a standing permission already covers them.

    This is intentionally minimal for MVP: it only looks at risk class. Real
    consent/scope/connector-grant checks belong to the Orchestration Service's
    Policy/Consent Service (ADD §13) — this gate should eventually call back
    into Orchestration rather than deciding in isolation, the same way
    AgenticServiceClient lets Orchestration call this service today.
    """

    def evaluate(self, step: PlanStep) -> PolicyDecision:
        if step.risk_class in _APPROVAL_REQUIRED_RISK_CLASSES:
            return PolicyDecision.ALLOW if step.approved else PolicyDecision.REQUIRE_APPROVAL
        return PolicyDecision.ALLOW
