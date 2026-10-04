from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from .. import memory_repo
from ..db import get_connection

# Per-category consent for T3 information (ADD §7.1; FSD FR-MEM-011, BR-018).
# Health and finances are only ever used by Brain 1 / Brain 2 when she has
# opted in for that category:
#   - without it, T3 details stay `requires_confirmation`: stored but unused,
#     never in the Context Pack, never shown to a model
#   - opting in activates her own explicit statements in that category
#   - opting out (or declining) puts them back out of use (suppressed)

CATEGORIES = ('health', 'finances')
_FINANCES_RE = re.compile(r'\b(money|debt|loan|salary|income|savings|mortgage|rent|bank|credit|budget|finance|finances|spending|invest)', re.IGNORECASE)


def category_of(item: dict[str, Any]) -> str:
    """Which T3 category a memory or profile field belongs to."""
    text = f"{item.get('domain') or item.get('area') or ''} {item.get('content') or item.get('value') or ''}"
    return 'finances' if _FINANCES_RE.search(text) else 'health'


def status(profile_email: str) -> dict[str, bool | None]:
    """{'health': True | False | None, 'finances': ...} — None means never asked."""
    with get_connection() as conn:
        rows = conn.execute('SELECT category, granted FROM brain1_consents WHERE profile_email = ?', (profile_email,)).fetchall()
    found = {r['category']: bool(r['granted']) for r in rows}
    return {c: found.get(c) for c in CATEGORIES}


def granted(profile_email: str, category: str) -> bool:
    return status(profile_email).get(category) is True


def allowed_categories(profile_email: str) -> set[str]:
    return {c for c, ok in status(profile_email).items() if ok}


def shareable(item: dict[str, Any], allowed: set[str]) -> bool:
    """May this memory / field reach a model? Non-T3 always; T3 only with consent."""
    tier = item.get('sensitivity_tier') or item.get('tier')
    return tier != 'T3' or category_of(item) in allowed


def set_consent(profile_email: str, category: str, granted_: bool) -> dict[str, Any]:
    if category not in CATEGORIES:
        raise ValueError(f"Unknown category '{category}'. Use one of: {', '.join(CATEGORIES)}.")
    with get_connection() as conn:
        conn.execute(
            'INSERT INTO brain1_consents (profile_email, category, granted, updated_at) VALUES (?, ?, ?, ?) '
            'ON CONFLICT(profile_email, category) DO UPDATE SET granted = excluded.granted, updated_at = excluded.updated_at',
            (profile_email, category, int(granted_), datetime.now(timezone.utc).isoformat()),
        )
    changed = []
    for memory in _t3_memories(profile_email, category):
        if granted_ and memory['status'] == memory_repo.REQUIRES_CONFIRMATION and memory['explicitness'] == 'explicit':
            changed.append(memory_repo.confirm_memory(memory['memory_id'], profile_email))
        elif not granted_ and memory['status'] in (memory_repo.ACTIVE, memory_repo.REQUIRES_CONFIRMATION):
            changed.append(memory_repo.suppress_memory(memory['memory_id'], profile_email))
    return {'category': category, 'granted': granted_, 'memories_changed': len([c for c in changed if c])}


def pending_requests(profile_email: str, new_memories: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Consent questions to ask after a turn: one per category she hasn't
    answered yet that just came up in something she said."""
    asked = status(profile_email)
    categories = {category_of(m) for m in new_memories if m.get('sensitivity_tier') == 'T3'}
    return [
        {'category': c, 'question': f"You mentioned something about your {c}. Should Brain 2 remember {c} details so it can take them into account? You can change this any time."}
        for c in sorted(categories)
        if asked.get(c) is None
    ]


def _t3_memories(profile_email: str, category: str) -> list[dict[str, Any]]:
    return [m for m in memory_repo.list_memories(profile_email, status=None) if m.get('sensitivity_tier') == 'T3' and category_of(m) == category]
