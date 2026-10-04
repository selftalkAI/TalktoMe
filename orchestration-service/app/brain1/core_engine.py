from __future__ import annotations

import json
import re
import threading
import uuid
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from ..config import settings
from ..db import get_connection
from ..spinal_cord import AgenticServiceClient, AgenticServiceError
from . import tools

# Brain 1's core agents (Building_Brain1.md §7, §10). Each core is a YAML
# definition (cores/*.yaml): a goal, the lenses of its sub-agents, and when to
# wake it. The Router picks up to MAX_CORES for a message; each runs a bounded
# think → act → check loop — the model (Agentic Service `core_agent.think`)
# chooses a tool or finishes, the tool runs HERE, next to the data — and its
# conclusion is stored as the core's latest area summary. The Context Pack
# reads those summaries (`latest_summaries`), so Brain 2 speaks from what
# Brain 1 has understood, not from raw facts.

CORES_DIR = Path(__file__).parent / 'cores'
MAX_CORES = 3
SUMMARY_FRESH_HOURS = 24


@lru_cache(maxsize=1)
def cores() -> dict[str, dict[str, Any]]:
    return {d['id']: d for d in (yaml.safe_load(p.read_text()) for p in sorted(CORES_DIR.glob('*.yaml')))}


def route(domain: str, message: str, reading: dict[str, Any]) -> list[str]:
    """The cores this message is about, best first (at most MAX_CORES)."""
    text = (message or '').lower()
    scored = []
    for core_id, core in cores().items():
        routes = core.get('routes') or {}
        score = 0
        if (domain or '').lower() in (routes.get('domains') or []):
            score += 3
        score += 2 * sum(1 for w in routes.get('words') or [] if re.search(r'(?<![a-z])' + re.escape(w) + r'(?![a-z])', text))
        if reading.get('intent') in (routes.get('intents') or []):
            score += 1
        if score:
            scored.append((score, core_id))
    scored.sort(key=lambda s: s[0], reverse=True)
    return [core_id for _, core_id in scored[:MAX_CORES]]


def run_core(profile_email: str, core_id: str, message: str, reading: dict[str, Any]) -> dict[str, Any]:
    """One core's bounded investigation. Returns the stored summary row, or
    an empty summary when the model was unavailable."""
    core = cores()[core_id]
    findings: list[dict[str, Any]] = []
    result: dict[str, Any] = {}
    for step in range(settings.brain1_core_max_steps + 1):
        must_finish = step == settings.brain1_core_max_steps
        result = _think(profile_email, core, message, reading, findings, must_finish)
        if result.get('action') != 'tool':
            break
        findings.append({'tool': result['tool'], 'args': result['args'],
                         'result': tools.run(result['tool'], profile_email, result['args'])})

    summary = (result.get('summary') or '').strip()
    if not summary:
        return {'core': core_id, 'summary': '', 'steps': findings}
    if result.get('open_question'):
        _queue_question(profile_email, core_id, result['open_question'])
    return _save(profile_email, core_id, summary, result.get('confidence', 0.5), findings)


def run_cores(profile_email: str, domain: str, message: str, reading: dict[str, Any]) -> list[dict[str, Any]]:
    return [run_core(profile_email, core_id, message, reading) for core_id in route(domain, message, reading)]


def run_in_background(profile_email: str, domain: str, message: str, reading: dict[str, Any]) -> threading.Thread:
    """Background mode: understand after the reply, so the next reply benefits."""
    thread = threading.Thread(target=_safe_run, args=(profile_email, domain, message, reading), daemon=True)
    thread.start()
    return thread


def latest_summaries(profile_email: str, max_age_hours: int = SUMMARY_FRESH_HOURS) -> list[dict[str, Any]]:
    """Each core's most recent, still-fresh understanding."""
    since = (datetime.now(timezone.utc) - timedelta(hours=max_age_hours)).isoformat()
    with get_connection() as conn:
        rows = conn.execute(
            'SELECT core, summary, confidence, created_at FROM brain1_area_summaries '
            'WHERE profile_email = ? AND created_at >= ? ORDER BY created_at DESC',
            (profile_email, since),
        ).fetchall()
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        latest.setdefault(row['core'], dict(row))
    return list(latest.values())


def _think(profile_email: str, core: dict[str, Any], message: str, reading: dict[str, Any],
           findings: list[dict[str, Any]], must_finish: bool) -> dict[str, Any]:
    payload = {
        'core': {k: core.get(k) for k in ('name', 'goal', 'sub_agents')},
        'tools': tools.describe(),
        'message': message,
        'reading': reading,
        'findings': findings,
        'must_finish': must_finish,
    }
    try:
        run = AgenticServiceClient().create_agent_run('core_agent', user_id=profile_email, goal=json.dumps(payload))
    except AgenticServiceError:
        return {}
    steps = run.get('steps') or []
    result = steps[0].get('result') if run.get('status') == 'completed' and steps else None
    return result if isinstance(result, dict) else {}


def _save(profile_email: str, core_id: str, summary: str, confidence: float, findings: list[dict[str, Any]]) -> dict[str, Any]:
    row = {
        'summary_id': str(uuid.uuid4()),
        'profile_email': profile_email,
        'core': core_id,
        'summary': summary,
        'confidence': confidence,
        'steps_json': json.dumps([{'tool': f['tool'], 'args': f['args']} for f in findings]),
        'created_at': datetime.now(timezone.utc).isoformat(),
    }
    with get_connection() as conn:
        conn.execute(
            'INSERT INTO brain1_area_summaries (summary_id, profile_email, core, summary, confidence, steps_json, created_at) '
            'VALUES (:summary_id, :profile_email, :core, :summary, :confidence, :steps_json, :created_at)',
            row,
        )
    return {'core': core_id, 'summary': summary, 'confidence': confidence, 'steps': findings}


def _queue_question(profile_email: str, core_id: str, question: str) -> None:
    with get_connection() as conn:
        conn.execute(
            'INSERT OR IGNORE INTO brain1_open_questions (question_id, profile_email, core, sub_agent, question, priority, '
            "status, created_at) VALUES (?, ?, ?, NULL, ?, 60, 'open', ?)",
            (str(uuid.uuid4()), profile_email, core_id, question.strip()[:200], datetime.now(timezone.utc).isoformat()),
        )


def _safe_run(profile_email: str, domain: str, message: str, reading: dict[str, Any]) -> None:
    try:
        run_cores(profile_email, domain, message, reading)
    except Exception:  # noqa: BLE001 - background understanding must never crash the service
        pass
