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

VOICES = ('friend', 'coach', 'big_sister', 'big_brother', 'mother_like', 'father_like', 'grandparent_like', 'mentor', 'buddy')
DEFAULT_VOICE = 'friend'

# Stored as an explicit user-instruction memory in a system-owned domain, so it
# survives restarts, is visible and deletable like any memory, and never shows
# up in the Context Pack as a "fact" about her life.
PREFERENCE_DOMAIN = 'brain1_voice_preference'

_REQUEST_RE = re.compile(
    r'\b(?:talk|speak|text|be|act)\b[^.?!]{0,30}?\blike\s+(?:a|an|my|her|his)?\s*(big\s+)?'
    r'(sister|sis|brother|bro|friend|mate|mom|mum|mother|dad|father|grandma|grandpa|grandmother|grandfather|granny|nana|mentor|buddy|coach)\b',
    re.IGNORECASE,
)
_LESS_COACHY_RE = re.compile(r'\bless\s+coach[- ]?y\b|\bstop\s+coaching\b', re.IGNORECASE)
_CLEAR_RE = re.compile(r'\b(?:talk|speak)\s+(?:normally|like\s+(?:yourself|you\s+normally\s+do))\b', re.IGNORECASE)
_WORD_TO_VOICE = {
    'sister': 'big_sister', 'sis': 'big_sister', 'brother': 'big_brother', 'bro': 'big_brother',
    'friend': 'friend', 'mate': 'friend', 'mom': 'mother_like', 'mum': 'mother_like', 'mother': 'mother_like',
    'dad': 'father_like', 'father': 'father_like', 'grandma': 'grandparent_like', 'grandpa': 'grandparent_like',
    'grandmother': 'grandparent_like', 'grandfather': 'grandparent_like', 'granny': 'grandparent_like',
    'nana': 'grandparent_like', 'mentor': 'mentor', 'buddy': 'buddy', 'coach': 'coach',
}

_LOSS_RE = re.compile(r'\b(passed away|passed|died|lost|death|funeral|estranged|don\'t speak to|no longer speak)\b', re.IGNORECASE)
_VOICE_PEOPLE = {
    'mother_like': re.compile(r'\b(mom|mum|mother|mama|amma)\b', re.IGNORECASE),
    'big_sister': re.compile(r'\b(sister|sis)\b', re.IGNORECASE),
    'big_brother': re.compile(r'\b(brother|bro)\b', re.IGNORECASE),
    'father_like': re.compile(r'\b(dad|father|papa|daddy)\b', re.IGNORECASE),
    'grandparent_like': re.compile(r'\b(grandma|grandpa|grandmother|grandfather|granny|nana|grandparents?)\b', re.IGNORECASE),
}

_HEAVY_FEELINGS = ('tired', 'exhausted', 'overwhelmed', 'drained', 'sad', 'guilty', 'hopeless', 'lonely', 'burnt out', 'burned out')
_DECISION_RE = re.compile(
    r'\b(should i (take|quit|leave|move|buy|lend|accept|stay|sell|sign|marry|go back)|big decision|decide whether|'
    r"can.t decide|torn between|choose between)\b",
    re.IGNORECASE,
)
_PERSPECTIVE_RE = re.compile(r'\b(behind|my age|life is|this year|getting old|what.s it all for|regret)\b', re.IGNORECASE)
_BIG_NEWS_RE = re.compile(r'(!{2,}|\b(got the|promotion|passed|nailed|finally did|engaged|new job)\b)', re.IGNORECASE)

_FITNESS_DOMAINS = ('fitness', 'gym', 'exercise', 'health', 'running', 'sport', 'workout')

# Expertise by life area first, then by what they're talking about (first match wins).
_EXPERTISE_RULES = (
    ('mind_emotions', ('emotion', 'emotions', 'feelings', 'stress', 'mood', 'mental'), ()),
    ('financial_analyst', ('money', 'finance', 'finances', 'budget', 'spending'), ('money', 'budget', 'spent', 'spending', 'savings', 'debt', 'afford', '$')),
    ('career_mentor', ('work', 'career', 'job'), ('manager', 'boss', 'promotion', 'career', 'interview', 'colleague', 'job')),
    ('parenting_guide', ('parenting', 'kids', 'children'), ('toddler', 'tantrum', 'parenting', 'my son', 'my daughter', 'homework')),
    ('relationship_guide', ('relationships', 'partner', 'family', 'friends'), ('husband', 'wife', 'partner', 'boyfriend', 'girlfriend', 'argument', 'fight with')),
    ('sleep_guide', ('sleep',), ('sleep', 'insomnia', 'awake at', 'tired all')),
    ('nutritionist', ('nutrition', 'diet', 'eating'), ('eat', 'eating', 'snack', 'sugar', 'diet', 'protein')),
    ('chef', ('cooking', 'food', 'recipes'), ('cook', 'cooking', 'recipe', 'dinner', 'bake', 'baking')),
    ('fitness_coach', ('fitness', 'gym', 'exercise', 'health', 'running', 'sport', 'workout'), ('gym', 'workout', 'run', 'exercise', 'training')),
    ('skills_tutor', ('learning', 'skills', 'reading', 'music', 'language'), ('learn', 'practice', 'lesson', 'course', 'skill')),
    ('meaning_companion', ('meaning', 'purpose', 'faith', 'spirituality', 'legacy'), ('purpose', 'meaning', 'legacy', 'faith', 'pray')),
    ('life_designer', ('home', 'schedule', 'routine', 'lifestyle'), ('routine', 'schedule', 'clutter', 'mornings', 'evenings')),
)


def select(
    profile_email: str,
    domain: str,
    latest_message: str,
    reading: dict[str, Any],
    avoid_voices: set[str] | frozenset[str] = frozenset(),
) -> dict[str, str]:
    """Returns `{'voice', 'expertise', 'source'}` for this reply. A voice
    request in `latest_message` is recorded first, so it applies to the very
    reply that answers it. `avoid_voices` are voices that have repeatedly
    landed badly with this person (learning.py) — skipped unless she chose it."""
    _record_request(profile_email, latest_message)
    blocked = blocked_voices(profile_email)
    preferred = preferred_voice(profile_email)

    if preferred and preferred not in blocked:
        voice, source = preferred, 'her_choice'
    else:
        voice, source = _voice_for_moment(domain, reading, latest_message), 'selected'
        unavailable = blocked | set(avoid_voices)
        if voice in unavailable:
            voice = next((v for v in (DEFAULT_VOICE, 'coach', 'big_sister', 'big_brother') if v not in unavailable), DEFAULT_VOICE)

    return {'voice': voice, 'expertise': _expertise_for(domain, reading, latest_message), 'source': source}


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


def _voice_for_moment(domain: str, reading: dict[str, Any], message: str = '') -> str:
    """Who they need right now, from how they are and what they're facing."""
    feeling = (reading.get('feeling') or '').lower()
    intent = reading.get('intent')
    expertise = _expertise_for(domain, reading, message)
    if any(f in feeling for f in _HEAVY_FEELINGS) or intent == 'venting':
        return 'mother_like'
    if _DECISION_RE.search(message or ''):
        return 'father_like'
    if intent == 'progress' and _BIG_NEWS_RE.search(message or ''):
        return 'buddy'
    if _PERSPECTIVE_RE.search(message or '') or expertise == 'meaning_companion':
        return 'grandparent_like'
    if expertise in ('career_mentor', 'financial_analyst', 'skills_tutor'):
        return 'mentor'
    if intent in ('asking', 'progress') and _is_fitness(domain):
        return 'coach'
    return DEFAULT_VOICE


def _expertise_for(domain: str, reading: dict[str, Any], message: str = '') -> str:
    feeling = (reading.get('feeling') or '').lower()
    if reading.get('intent') == 'venting' or any(f in feeling for f in _HEAVY_FEELINGS):
        return 'mind_emotions'
    area = (domain or '').lower()
    for expertise, areas, _ in _EXPERTISE_RULES:
        if area in areas:
            return expertise
    text = (message or '').lower()
    for expertise, _, words in _EXPERTISE_RULES:
        if any(re.search(r'(?<![a-z])' + re.escape(w) + r'(?![a-z])', text) if w.isalpha() or ' ' in w else w in text for w in words):
            return expertise
    return 'general'


def _is_fitness(domain: str) -> bool:
    return any(d in (domain or '').lower() for d in _FITNESS_DOMAINS)
