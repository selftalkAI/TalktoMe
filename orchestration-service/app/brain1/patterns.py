from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from .. import conversations_repo, memory_repo
from ..brain2 import intentions_repo
from ..spinal_cord import AgenticServiceClient, AgenticServiceError

# Patterns across conversations (Building_Brain1.md §14.3, Scenario 8). The
# nightly reflection looks across weeks of what they said and did; the model
# (Prefrontal Cortex `find_patterns`) proposes at most two patterns, each with
# quoted evidence — and this module re-checks every quote against their own
# words, dropping any pattern that isn't backed by two different real notes.
# A pattern is stored as a hypothesis (`requires_confirmation`): it shows up
# for them to confirm ("That's right") or dismiss, and Brain 2 may gently check
# it in conversation. It never becomes a fact about them on Brain 1's say-so.

SOURCE_TYPE = 'pattern'
WINDOW_DAYS = 45
MAX_ITEMS = 40
ITEM_CHARS = 300
MIN_ITEMS = 3


def detect(profile_email: str) -> list[dict[str, Any]]:
    items = gather(profile_email)
    if len(items) < MIN_ITEMS:
        return []
    known = [m['content'] for m in memory_repo.list_memories(profile_email, status=None) if m.get('source_type') == SOURCE_TYPE]
    proposed = _find(profile_email, items, known)
    created = []
    for pattern in proposed:
        text = (pattern.get('pattern') or '').strip()
        if not text or not grounded(pattern.get('evidence') or [], items) or _already_known(text, known):
            continue
        created.append(memory_repo.create_memory(
            profile_email=profile_email, memory_type='fact', content=text, explicitness='inferred', confidence=0.6,
            sensitivity_tier='T2', status=memory_repo.REQUIRES_CONFIRMATION, rationale_code='PATTERN_ACROSS_CONVERSATIONS',
            source_type=SOURCE_TYPE, source_id=json.dumps(pattern.get('evidence'))[:500],
        ))
        known.append(text)
    return created


def gather(profile_email: str) -> list[str]:
    """Her own words and record over the window: episode summaries, check-in
    notes, and her messages — never T3, never Brain 2's words."""
    since = (datetime.now(timezone.utc) - timedelta(days=WINDOW_DAYS)).isoformat()
    items: list[str] = []
    for m in memory_repo.list_memories(profile_email, memory_type='event'):
        if m.get('source_type') == 'episode' and m['created_at'] >= since and m.get('sensitivity_tier') != 'T3':
            items.append(m['content'])
    for intention in intentions_repo.list_active_intentions(profile_email):
        for c in intentions_repo.list_checkins(intention['intention_id'], profile_email, limit_days=WINDOW_DAYS):
            if c.get('note'):
                items.append(f"{c['checkin_date']} ({intention['title']}, {c['actual_minutes']} min): {c['note']}")
    for turn in conversations_repo.history(profile_email, limit=80):
        if turn['role'] == 'user' and turn['created_at'] >= since:
            items.append(f"{turn['created_at'][:10]}: {turn['content']}")
    return [i[:ITEM_CHARS] for i in items][-MAX_ITEMS:]


def grounded(evidence: list[str], items: list[str]) -> bool:
    """At least two quotes, each really in her notes, from two different notes."""
    norm_items = [_norm(i) for i in items]
    sources = set()
    for quote in evidence:
        q = _norm(quote).strip('"\' .')
        if len(q) < 4:
            continue
        hits = [n for n, item in enumerate(norm_items) if q in item]
        if hits:
            sources.add(next((h for h in hits if h not in sources), hits[0]))
    return len(sources) >= 2


def pending(profile_email: str) -> list[dict[str, Any]]:
    return [m for m in memory_repo.list_memories(profile_email, status=memory_repo.REQUIRES_CONFIRMATION)
            if m.get('source_type') == SOURCE_TYPE]


def accuracy(profile_email: str) -> float | None:
    """How often her verdict agreed with Brain 1's patterns — the measured
    "prediction accuracy" of Brain Strength (Building_Brain1.md §8.5)."""
    judged = [m for m in memory_repo.list_memories(profile_email, status=None)
              if m.get('source_type') == SOURCE_TYPE and m['status'] in (memory_repo.ACTIVE, memory_repo.SUPPRESSED, memory_repo.DELETED)]
    if not judged:
        return None
    return round(sum(1 for m in judged if m['status'] == memory_repo.ACTIVE) / len(judged), 2)


def _find(profile_email: str, items: list[str], known: list[str]) -> list[dict[str, Any]]:
    payload = {'operation': 'find_patterns', 'items': items, 'known_patterns': known}
    try:
        run = AgenticServiceClient().create_agent_run('prefrontal_cortex', user_id=profile_email, goal=json.dumps(payload))
    except AgenticServiceError:
        return []
    steps = run.get('steps') or []
    result = steps[0].get('result') if run.get('status') == 'completed' and steps else None
    return (result or {}).get('patterns') or [] if isinstance(result, dict) else []


def _already_known(text: str, known: list[str]) -> bool:
    words = set(re.findall(r'[a-z]{4,}', text.lower()))
    for k in known:
        other = set(re.findall(r'[a-z]{4,}', k.lower()))
        if words and len(words & other) / len(words | other) >= 0.6:
            return True
    return False


def _norm(text: str) -> str:
    return re.sub(r'\s+', ' ', (text or '').lower()).replace('’', "'")
