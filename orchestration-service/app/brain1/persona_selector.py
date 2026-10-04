from __future__ import annotations

import re
from typing import Any

from .. import memory_repo

# Brain 1's Persona Selector (Building_Brain1.md §12.4; Building_Brain2.md §5.2).
# Picks Brain 2's persona — a voice and an expertise — for every reply. Brain 2
# owns what each persona sounds like (agentic-service prompts/voices,
# prompts/expertise); Brain 1 owns which one fits this person right now.
#
# Order of precedence:
#   1. Her own explicit choice ("talk to me like my sister") — always wins
#      until she changes it (FSD FR-PER-002, BR-017).
#   2. Voices that could hurt are blocked (FR-PER-003) — e.g. no mother-like
#      voice when she has told us her mother died.
#   3. Otherwise chosen from her state and the topic.
# The Safety Core (Brain 1 Stage) will override all of this once it exists.

VOICES = ('friend', 'coach', 'big_sister', 'big_brother', 'mother_like')
DEFAULT_VOICE = 'friend'

# Stored as an explicit user-instruction memory in a system-owned domain, so it
# survives restarts, is visible and deletable like any memory, and never shows
# up in the Context Pack as a "fact" about her life.
PREFERENCE_DOMAIN = 'brain1_voice_preference'

_REQUEST_RE = re.compile(
    r'\b(?:talk|speak|text|be|act)\b[^.?!]{0,30}?\blike\s+(?:a|an|my|her|his)?\s*(big\s+)?'
    r'(sister|sis|brother|bro|friend|mate|mom|mum|mother|coach)\b',
    re.IGNORECASE,
)
_LESS_COACHY_RE = re.compile(r'\bless\s+coach[- ]?y\b|\bstop\s+coaching\b', re.IGNORECASE)
_CLEAR_RE = re.compile(r'\b(?:talk|speak)\s+(?:normally|like\s+(?:yourself|you\s+normally\s+do))\b', re.IGNORECASE)
_WORD_TO_VOICE = {
    'sister': 'big_sister', 'sis': 'big_sister', 'brother': 'big_brother', 'bro': 'big_brother',
    'friend': 'friend', 'mate': 'friend', 'mom': 'mother_like', 'mum': 'mother_like', 'mother': 'mother_like',
    'coach': 'coach',
}

_LOSS_RE = re.compile(r'\b(passed away|passed|died|lost|death|funeral|estranged|don\'t speak to|no longer speak)\b', re.IGNORECASE)
_VOICE_PEOPLE = {
    'mother_like': re.compile(r'\b(mom|mum|mother|mama|amma)\b', re.IGNORECASE),
    'big_sister': re.compile(r'\b(sister|sis)\b', re.IGNORECASE),
    'big_brother': re.compile(r'\b(brother|bro)\b', re.IGNORECASE),
}

_HEAVY_FEELINGS = ('tired', 'exhausted', 'overwhelmed', 'drained', 'sad', 'guilty', 'hopeless', 'lonely', 'burnt out', 'burned out')
_FITNESS_DOMAINS = ('fitness', 'gym', 'exercise', 'health', 'running', 'sport', 'workout')
_FEELING_DOMAINS = ('emotion', 'emotions', 'feelings', 'stress', 'mood', 'mental')


def select(profile_email: str, domain: str, latest_message: str, reading: dict[str, Any]) -> dict[str, str]:
    """Returns `{'voice', 'expertise', 'source'}` for this reply. A voice
    request in `latest_message` is recorded first, so it applies to the very
    reply that answers it."""
    _record_request(profile_email, latest_message)
    blocked = blocked_voices(profile_email)
    preferred = preferred_voice(profile_email)

    if preferred and preferred not in blocked:
        voice, source = preferred, 'her_choice'
    else:
        voice, source = _voice_for_moment(domain, reading), 'selected'
        if voice in blocked:
            voice = DEFAULT_VOICE

    return {'voice': voice, 'expertise': _expertise_for(domain, reading), 'source': source}


def preferred_voice(profile_email: str) -> str | None:
    memories = memory_repo.list_memories(profile_email, memory_type='user_instruction', domain=PREFERENCE_DOMAIN)
    if not memories:
        return None
    value = memories[0]['content']  # newest first
    return value if value in VOICES else None


def set_preferred_voice(profile_email: str, voice: str | None) -> str | None:
    """Records her explicit choice (None clears it). Older choices are
    superseded, never silently overwritten."""
    if voice is not None and voice not in VOICES:
        raise ValueError(f"Unknown voice '{voice}'. Choose one of: {', '.join(VOICES)}.")
    for old in memory_repo.list_memories(profile_email, memory_type='user_instruction', domain=PREFERENCE_DOMAIN):
        memory_repo.suppress_memory(old['memory_id'], profile_email)
    if voice is None:
        return None
    memory_repo.create_memory(
        profile_email=profile_email,
        memory_type='user_instruction',
        domain=PREFERENCE_DOMAIN,
        content=voice,
        explicitness='explicit',
        confidence=1.0,
        sensitivity_tier='T2',
        status=memory_repo.ACTIVE,
        rationale_code='USER_EXPLICIT',
        source_type='voice_preference',
    )
    return voice


def detect_request(message: str) -> str | None:
    """The voice she just asked for: a voice id, 'clear', or None."""
    if _CLEAR_RE.search(message or ''):
        return 'clear'
    match = _REQUEST_RE.search(message or '')
    if match:
        return _WORD_TO_VOICE[match.group(2).lower()]
    if _LESS_COACHY_RE.search(message or ''):
        return 'friend'
    return None


def blocked_voices(profile_email: str) -> set[str]:
    """Voices tied to a person she has lost or is estranged from."""
    blocked: set[str] = set()
    for memory in memory_repo.list_memories(profile_email):
        content = memory.get('content') or ''
        if not _LOSS_RE.search(content):
            continue
        for voice, person_re in _VOICE_PEOPLE.items():
            if person_re.search(content):
                blocked.add(voice)
    return blocked


def _record_request(profile_email: str, message: str) -> None:
    request = detect_request(message)
    if request == 'clear':
        set_preferred_voice(profile_email, None)
    elif request:
        set_preferred_voice(profile_email, request)


def _voice_for_moment(domain: str, reading: dict[str, Any]) -> str:
    feeling = (reading.get('feeling') or '').lower()
    intent = reading.get('intent')
    if any(f in feeling for f in _HEAVY_FEELINGS) or intent == 'venting':
        return 'mother_like'
    if intent in ('asking', 'progress') and _is_fitness(domain):
        return 'coach'
    return DEFAULT_VOICE


def _expertise_for(domain: str, reading: dict[str, Any]) -> str:
    feeling = (reading.get('feeling') or '').lower()
    if (domain or '').lower() in _FEELING_DOMAINS or reading.get('intent') == 'venting' or any(f in feeling for f in _HEAVY_FEELINGS):
        return 'mind_emotions'
    if _is_fitness(domain):
        return 'fitness_coach'
    return 'general'


def _is_fitness(domain: str) -> bool:
    return any(d in (domain or '').lower() for d in _FITNESS_DOMAINS)
