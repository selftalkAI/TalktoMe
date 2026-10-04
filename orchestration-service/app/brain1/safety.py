from __future__ import annotations

import re
from typing import Any

# Brain 1's Safety Core (Building_Brain1.md §13; FSD FR-B1-011, FR-SAFE-008).
# Runs first on every message, before anything else in Brain 1 or Brain 2.
#   ok       → normal conversation
#   concern  → Brain 2 may only listen gently: no goals, no advice, no challenge
#   crisis   → no coaching at all: a reviewed care message with crisis lines,
#              and the turn is excluded from memory
# Deterministic rules, tuned for recall over precision — a false "concern"
# costs one gentle reply; a missed crisis can cost far more. The care text
# below is a fixed, reviewed script, never model-generated.

OK, CONCERN, CRISIS = 'ok', 'concern', 'crisis'

_CRISIS_PATTERNS = [
    r'\bkill(ing)?\s+my\s?self\b', r'\bsuicid', r'\bend(ing|ed)?\s+(it\s+all|my\s+(own\s+)?life|things)\b', r'\b(want|wanted|wanting)\s+to\s+die\b',
    r'\bwish\s+i\s+(was|were)\s+dead\b', r'\bbetter\s+off\s+dead\b', r'\bhurt(ing)?\s+my\s?self\b',
    r'\bself[-\s]?harm', r'\bcut(ting)?\s+my\s?self\b', r'\boverdose\b', r"\bdon'?t\s+want\s+to\s+(be\s+alive|live|wake\s+up)\b",
    r'\bno\s+reason\s+to\s+live\b', r'\b(take|taking)\s+my\s+(own\s+)?life\b',
    r"\bdon'?t\s+want\s+to\s+be\s+here\s+any\s?more\b", r'\bnot\s+worth\s+living\b', r'\bdisappear\s+for\s+good\b',
]
_CONCERN_PATTERNS = [
    r"\bcan'?t\s+(do\s+this|go\s+on|take\s+(it|this))\s+any\s?more\b", r"\bcan'?t\s+go\s+on\b", r"\bwhat'?s\s+(even\s+)?the\s+point\b",
    r'\bhopeless\b', r'\bworthless\b', r'\bno\s+point\s+(in|to)\b', r'\bgive\s+up\s+on\s+everything\b',
    r'\bnobody\s+(cares|would\s+(notice|care))\b', r'\bso\s+(alone|lonely)\b', r'\bfalling\s+apart\b',
    r'\bbreaking\s+down\b', r'\bpanic\s+attack', r"\bcan'?t\s+stop\s+crying\b",
]
_CRISIS_RE = [re.compile(p, re.IGNORECASE) for p in _CRISIS_PATTERNS]
_CONCERN_RE = [re.compile(p, re.IGNORECASE) for p in _CONCERN_PATTERNS]


def assess(message: str) -> dict[str, Any]:
    """`{'level': ok|concern|crisis, 'matched': pattern or None}`."""
    text = message or ''
    for pattern in _CRISIS_RE:
        if pattern.search(text):
            return {'level': CRISIS, 'matched': pattern.pattern}
    for pattern in _CONCERN_RE:
        if pattern.search(text):
            return {'level': CONCERN, 'matched': pattern.pattern}
    return {'level': OK, 'matched': None}


# Reviewed crisis lines by country, matched from the onboarding location.
_RESOURCES = (
    (('canada', ', bc', ', on', ', ab', ', qc', ', mb', ', sk', ', ns', ', nb', ', nl', ', pe'),
     'call or text 9-8-8 (Suicide Crisis Helpline, Canada), any time', '911'),
    (('united states', 'usa', ', us', ', tx', ', ca', ', ny', ', fl', ', wa', ', il'),
     'call or text 988 (Suicide & Crisis Lifeline, US), any time', '911'),
    (('united kingdom', ', uk', 'england', 'scotland', 'wales', 'northern ireland', 'london'),
     'call Samaritans free on 116 123, any time', '999'),
)


def care_message(first_name: str, location: str | None) -> str:
    """The fixed crisis reply: care first, then real help."""
    lowered = f", {(location or '').lower()}"
    line, emergency = 'please contact a local crisis line or someone you trust right now', 'your local emergency number'
    for markers, resource, number in _RESOURCES:
        if any(m in lowered for m in markers):
            line, emergency = resource, number
            break
    return (
        f"{first_name}, I'm really glad you told me, and I'm worried about you. You deserve support from a real "
        f'person right now — {line}. If you might act on these feelings, call {emergency}. '
        "I'm here with you too. Are you safe right now?"
    )
