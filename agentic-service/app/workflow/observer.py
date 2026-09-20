from __future__ import annotations

from datetime import datetime, timezone

from .models import AgentRun


class Observer:
    """Records what happened at each transition (ADD §8 — the Observer role).

    For MVP this appends a human-readable audit trail onto the in-memory run.
    A production Observer writes an AuditEvent row per transition (TDD §4).
    """

    def record(self, run: AgentRun, note: str) -> None:
        timestamp = datetime.now(timezone.utc).isoformat()
        run.history.append(f'[{timestamp}] {note}')
