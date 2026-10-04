from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from ..db import get_connection

# One trace per turn (TDD §5.4, Building_Brain1.md §20): safety level,
# persona, reading, plan, drafts' failures and the judge's verdict — so anyone
# can see *why* Brain 2 said what it said. Never stores the person's message
# or the reply text itself (observability without surveillance, TDD §31.7).


def record(profile_email: str, trigger: str, safety_level: str, trace: dict[str, Any], latency_ms: int) -> str:
    run_id = str(uuid.uuid4())
    with get_connection() as conn:
        conn.execute(
            'INSERT INTO brain1_runs (run_id, profile_email, trigger, safety_level, trace_json, latency_ms, created_at) '
            'VALUES (?, ?, ?, ?, ?, ?, ?)',
            (run_id, profile_email, trigger, safety_level, json.dumps(trace, default=str), latency_ms,
             datetime.now(timezone.utc).isoformat()),
        )
    return run_id


def get(run_id: str, profile_email: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute('SELECT * FROM brain1_runs WHERE run_id = ? AND profile_email = ?', (run_id, profile_email)).fetchone()
    if row is None:
        return None
    run = dict(row)
    run['trace'] = json.loads(run.pop('trace_json'))
    return run
