from __future__ import annotations

import re
from typing import Any, Callable

from .. import memory_repo
from ..brain2 import intentions_repo
from ..db import get_connection
from . import consent, knowledge

# Tools Brain 1's core agents can use while investigating (Building_Brain1.md
# §10.3). Each takes the person's email plus plain arguments and returns
# short text for the model to read. All are read-only, owner-scoped, and
# never return T3 (health/finances) or system-owned content.

MAX_MEMORIES = 6
SNIPPET_CHARS = 420
_WORD_RE = re.compile(r"[a-z']{3,}")


def search_memories(profile_email: str, query: str = '', **_: Any) -> str:
    """What they have told us, best keyword match first."""
    terms = set(_WORD_RE.findall((query or '').lower()))
    allowed = consent.allowed_categories(profile_email)
    rows = [
        m
        for status in (memory_repo.ACTIVE, memory_repo.REQUIRES_CONFIRMATION)
        for m in memory_repo.list_memories(profile_email, status=status)
        if consent.shareable(m, allowed) and not (m.get('domain') or '').startswith('brain1_')
        and not (m.get('sensitivity_tier') == 'T3' and m['status'] != memory_repo.ACTIVE)
    ]
    scored = sorted(rows, key=lambda m: len(terms & set(_WORD_RE.findall(m['content'].lower()))), reverse=True)
    hits = [m for m in scored if not terms or terms & set(_WORD_RE.findall(m['content'].lower()))][:MAX_MEMORIES]
    if not hits:
        return 'Nothing they have told us matches that.'
    return '\n'.join(f"- {m['content']} ({'said' if m['explicitness'] == 'explicit' else 'inferred'}, {m['created_at'][:10]})" for m in hits)


def get_checkins(profile_email: str, **_: Any) -> str:
    """Their active goals and recent check-ins."""
    lines = [f'Today is {intentions_repo.today_iso()}. Dated check-ins below are history, not today, unless dated today.']
    for intention in intentions_repo.list_active_intentions(profile_email):
        checkins = sorted(intentions_repo.list_checkins(intention['intention_id'], profile_email), key=lambda c: c['checkin_date'])[-7:]
        lines.append(f"Goal: {intention['title']}, {intention['target_minutes']} min/day.")
        lines += [f"  {c['checkin_date']}: {c['actual_minutes']} min" + (f' — "{c["note"]}"' if c.get('note') else '') for c in checkins]
    return '\n'.join(lines) if len(lines) > 1 else 'No goals or check-ins yet.'


def search_books(profile_email: str, query: str = '', **_: Any) -> str:
    """What the expert books say about something."""
    results = knowledge.search_books(query, top_k=2)
    if not results:
        return 'The books had nothing relevant.'
    return '\n'.join(f"- ({r['book']}) {' '.join(r['content'].split())[:SNIPPET_CHARS]}" for r in results)


def principles(profile_email: str, core: str = '', **_: Any) -> str:
    """The reviewed principle cards for an area."""
    cards = [c for c in knowledge.cards() if not core or c.get('core') == core]
    return '\n'.join(f"- {c['principle']}" for c in cards[:6]) or 'No principles for that area.'


def ask_core(profile_email: str, core: str = '', **_: Any) -> str:
    """What another core currently understands."""
    with get_connection() as conn:
        row = conn.execute(
            'SELECT summary, created_at FROM brain1_area_summaries WHERE profile_email = ? AND core = ? ORDER BY created_at DESC LIMIT 1',
            (profile_email, core),
        ).fetchone()
    return f"{row['summary']} (as of {row['created_at'][:16]})" if row else f'The {core} core has no understanding yet.'


# Core agents describe the PERSON, so they only get tools that return evidence
# about the person. Book knowledge (`search_books`, `principles`) stays out of
# their hands: in live testing a core turned a book passage into a "fact"
# about the person. Expert knowledge reaches Brain 2 only as reviewed principle
# cards, clearly labelled as ideas (`knowledge.select`).
TOOLS: dict[str, tuple[Callable[..., str], str]] = {
    'search_memories': (search_memories, 'search what they have told us — args: {"query": words}'),
    'get_checkins': (get_checkins, 'their goals and recent check-ins — args: {}'),
    'ask_core': (ask_core, 'what another part of their brain understands — args: {"core": one of body, mind, behaviour, relationships, lifestyle}'),
}
KNOWLEDGE_TOOLS: dict[str, tuple[Callable[..., str], str]] = {
    'search_books': (search_books, 'what the expert books say — args: {"query": words}'),
    'principles': (principles, 'expert principles for an area — args: {"core": one of body, mind, behaviour, relationships, growth, meaning}'),
}


def run(tool: str, profile_email: str, args: dict[str, Any]) -> str:
    entry = TOOLS.get(tool)
    if entry is None:
        return f'Unknown tool {tool!r}.'
    fn, _ = entry
    safe_args = {k: v for k, v in (args or {}).items() if isinstance(v, str)}
    return fn(profile_email, **safe_args)


def describe() -> dict[str, str]:
    return {name: help_text for name, (_, help_text) in TOOLS.items()}
