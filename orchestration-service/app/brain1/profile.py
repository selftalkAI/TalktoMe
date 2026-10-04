from __future__ import annotations

import hashlib
import json
import uuid
from datetime import date, datetime, timezone
from typing import Any

from .. import memory_repo, profiles_repo
from ..brain2 import intentions_repo, profile_store
from ..db import get_connection
from . import patterns

# The Brain 1 Profile (Building_Brain1.md §8) — Brain 1's model of the whole
# person, in 12 sections, built from what they have actually told us. Every
# field is a record with its evidence, so Brain 1 (and the person) can always
# answer "how do you know that?", and a correction cleanly replaces a value.
# This module compiles the profile from the memory layer — it never invents a
# field — and keeps one stored version per change: the history of how Brain 1
# came to know them. The live Here & Now section is separate (`here_now.py`).

SECTIONS = (
    ('identity', 'Identity'),
    ('people', 'People'),
    ('inner_world', 'Inner world'),
    ('body', 'Body & health'),
    ('life_map', 'Life map & places'),
    ('tastes', 'Tastes & rituals'),
    ('goals', 'Goals & journeys'),
    ('story', 'Story & memory'),
    ('what_works', 'What works'),
    ('communication', 'Communication'),
    ('boundaries', 'Boundaries & consent'),
    ('open_questions', 'Open questions'),
)

# Which section (and owning core.sub-agent) a memory belongs to, by its life
# area first — the most specific signal — then by its memory type.
_AREA_ROUTES = (
    (('family', 'kids', 'children', 'partner', 'parent', 'parenting', 'relationship', 'friends', 'people'), 'people', 'relationships.family'),
    (('fitness', 'gym', 'exercise', 'health', 'sleep', 'energy', 'nutrition', 'body', 'weight', 'running'), 'body', 'body.fitness'),
    (('emotion', 'emotions', 'feelings', 'stress', 'mood', 'mental'), 'inner_world', 'mind.emotion'),
    (('values', 'purpose', 'faith', 'meaning', 'legacy', 'spirituality'), 'inner_world', 'meaning.purpose'),
    (('work', 'career', 'job'), 'identity', 'work.career'),
    (('money', 'finance', 'finances', 'spending', 'budget'), 'life_map', 'money.spending'),
    (('cooking', 'food', 'reading', 'learning', 'music', 'hobby', 'hobbies', 'skills', 'travel'), 'tastes', 'growth.curiosity'),
    (('home', 'schedule', 'routine', 'places'), 'life_map', 'lifestyle.daily_rhythm'),
)
_TYPE_ROUTES = {
    'relationship': ('people', 'relationships.family'),
    'routine': ('life_map', 'lifestyle.daily_rhythm'),
    'constraint': ('life_map', 'lifestyle.daily_rhythm'),
    'preference': ('tastes', 'lifestyle.tastes_preferences'),
    'goal': ('goals', 'behaviour.goals'),
    'project_context': ('goals', 'behaviour.goals'),
    'event': ('story', 'life_story.life_events'),
    'user_instruction': ('communication', 'relationships.communication_style'),
    'learned_strategy': ('what_works', 'learned'),
    'fact': ('identity', 'identity.personality'),
}
_LIVE_STATUSES = (memory_repo.ACTIVE, memory_repo.REQUIRES_CONFIRMATION)
_BOUNDARY_WORDS = ("don't", 'do not', 'never', 'avoid', 'stop')
VOICE_PREFERENCE_DOMAIN = 'brain1_voice_preference'

# Questions every Brain 1 starts with, per core — asked one at a time, only
# when natural (Building_Brain1.md §14.1). Dropped once the section has facts.
STARTER_QUESTIONS = (
    ('lifestyle', 'life_map', 'What does a normal weekday look like for you, from wake-up to bedtime?', 80),
    ('relationships', 'people', "Who's at home with you?", 70),
    ('lifestyle', 'tastes', "What's a small thing that reliably makes your day better?", 40),
    ('identity', 'inner_world', 'What matters most to you right now?', 30),
)


def build(profile_email: str) -> dict[str, Any]:
    """Compiles the profile now. Returns `{'sections': {key: [field, ...]},
    'strength': {...}, 'built_at': ...}`; each field is
    `{value, source, evidence, confidence, status, tier, owner}`."""
    sections: dict[str, list[dict[str, Any]]] = {key: [] for key, _ in SECTIONS}
    person = profiles_repo.get_profile(profile_email) or {}

    sections['identity'] += _identity_fields(person)
    for memory in _live_memories(profile_email):
        if (memory.get('domain') or '') == VOICE_PREFERENCE_DOMAIN:
            sections['communication'].append(_field(f"Prefers Brain 2 to talk like: {memory['content'].replace('_', ' ')}", memory, 'relationships.communication_style'))
            continue
        if (memory.get('domain') or '').startswith('brain1_'):
            continue
        section, owner = route(memory)
        sections[section].append(_field(memory['content'], memory, owner))

    sections['goals'] += _goal_fields(profile_email)
    sections['story'] += _accepted_entries(profile_email)
    _seed_open_questions(profile_email, sections)
    sections['open_questions'] = [
        {'value': q['question'], 'source': 'brain1', 'evidence': [], 'confidence': 1.0, 'status': 'open',
         'tier': 'T2', 'owner': q['core'], 'priority': q['priority'], 'question_id': q['question_id']}
        for q in open_questions(profile_email)
    ]
    measured = {'prediction_accuracy': patterns.accuracy(profile_email), 'correction_rate': correction_rate(profile_email)}
    return {'sections': sections, 'strength': {**strength(sections), **measured}, 'built_at': _now()}


def correction_rate(profile_email: str) -> float | None:
    """Share of what Brain 1 recorded about them that they had to correct —
    should fall over time (Building_Brain1.md §8.5)."""
    rows = memory_repo.list_memories(profile_email, status=None)
    recorded = [m for m in rows if m.get('rationale_code') != 'USER_CORRECTION' and not (m.get('domain') or '').startswith('brain1_')]
    if not recorded:
        return None
    corrected = sum(1 for m in rows if m.get('rationale_code') == 'USER_CORRECTION')
    return round(corrected / len(recorded), 2)


def route(memory: dict[str, Any]) -> tuple[str, str]:
    """(section, owner) for one memory — by life area, then by type."""
    if memory.get('source_type') == 'pattern':
        return 'goals', 'behaviour.barriers'  # a pattern Brain 1 noticed across conversations
    area = (memory.get('domain') or '').lower()
    for keywords, section, owner in _AREA_ROUTES:
        if any(k in area for k in keywords):
            return section, owner
    if memory.get('type') == 'user_instruction' and any(w in memory['content'].lower() for w in _BOUNDARY_WORDS):
        return 'boundaries', 'safety.boundaries'
    return _TYPE_ROUTES.get(memory.get('type') or 'fact', ('identity', 'identity.personality'))


def strength(sections: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    """How well Brain 1 knows them (Building_Brain1.md §8.5). Coverage and
    confidence are measured now; prediction accuracy and correction rate
    arrive with the learning stage and are reported as None until then."""
    knowable = [key for key, _ in SECTIONS if key != 'open_questions']
    confirmed = [k for k in knowable if any(f['status'] == 'confirmed' for f in sections[k])]
    fields = [f for k in knowable for f in sections[k]]
    return {
        'coverage': round(len(confirmed) / len(knowable), 2),
        'sections_known': len(confirmed),
        'sections_total': len(knowable),
        'average_confidence': round(sum(f['confidence'] for f in fields) / len(fields), 2) if fields else 0.0,
        'prediction_accuracy': None,
        'correction_rate': None,
    }


def save_version(profile_email: str, profile: dict[str, Any], reason: str = '') -> dict[str, Any] | None:
    """Stores a new version only when the profile actually changed. Returns
    the new version row, or None when nothing changed."""
    payload = json.dumps(profile['sections'], sort_keys=True, default=str)
    content_hash = hashlib.sha256(payload.encode('utf-8')).hexdigest()
    latest = latest_version(profile_email)
    if latest and latest['content_hash'] == content_hash:
        return None
    row = {
        'version_id': str(uuid.uuid4()),
        'profile_email': profile_email,
        'version': (latest['version'] + 1) if latest else 1,
        'profile_json': payload,
        'content_hash': content_hash,
        'reason': reason,
        'created_at': _now(),
    }
    with get_connection() as conn:
        conn.execute(
            'INSERT INTO brain1_profile_versions (version_id, profile_email, version, profile_json, content_hash, '
            'reason, created_at) VALUES (:version_id, :profile_email, :version, :profile_json, :content_hash, :reason, :created_at)',
            row,
        )
    return row


def latest_version(profile_email: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            'SELECT * FROM brain1_profile_versions WHERE profile_email = ? ORDER BY version DESC LIMIT 1', (profile_email,)
        ).fetchone()
    return dict(row) if row else None


def open_questions(profile_email: str) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM brain1_open_questions WHERE profile_email = ? AND status = 'open' ORDER BY priority DESC, created_at",
            (profile_email,),
        ).fetchall()
    return [dict(r) for r in rows]


def set_question_status(profile_email: str, question_id: str, status: str) -> bool:
    """She can skip a question she doesn't want asked ('dropped')."""
    if status not in ('dropped', 'answered'):
        raise ValueError("status must be 'dropped' or 'answered'")
    with get_connection() as conn:
        cur = conn.execute('UPDATE brain1_open_questions SET status = ? WHERE question_id = ? AND profile_email = ?',
                           (status, question_id, profile_email))
    return cur.rowcount > 0


def _seed_open_questions(profile_email: str, sections: dict[str, list[dict[str, Any]]]) -> None:
    """Starter questions for sections still empty; drops ones now answered."""
    with get_connection() as conn:
        for core, section, question, priority in STARTER_QUESTIONS:
            if sections[section]:
                conn.execute(
                    "UPDATE brain1_open_questions SET status = 'answered' WHERE profile_email = ? AND question = ? AND status = 'open'",
                    (profile_email, question),
                )
            else:
                conn.execute(
                    'INSERT OR IGNORE INTO brain1_open_questions (question_id, profile_email, core, sub_agent, question, '
                    "priority, status, created_at) VALUES (?, ?, ?, ?, ?, ?, 'open', ?)",
                    (str(uuid.uuid4()), profile_email, core, section, question, priority, _now()),
                )


def _live_memories(profile_email: str) -> list[dict[str, Any]]:
    return [m for status in _LIVE_STATUSES for m in memory_repo.list_memories(profile_email, status=status)]


def _field(value: str, memory: dict[str, Any], owner: str) -> dict[str, Any]:
    confirmed = memory['status'] == memory_repo.ACTIVE and memory.get('explicitness') == 'explicit'
    return {
        'value': value,
        'memory_id': memory['memory_id'],  # what the mirror view's confirm / fix / forget act on
        'source': 'said' if memory.get('explicitness') == 'explicit' else 'inferred',
        'evidence': [memory['memory_id']],
        'confidence': float(memory.get('confidence') or 0),
        'status': 'confirmed' if confirmed else 'hypothesis',
        'tier': memory.get('sensitivity_tier') or 'T2',
        'owner': owner,
        'area': memory.get('domain'),
        'updated_at': memory.get('updated_at'),
    }


def _onboarding(value: str, owner: str) -> dict[str, Any]:
    return {'value': value, 'source': 'onboarding', 'evidence': ['profiles'], 'confidence': 1.0,
            'status': 'confirmed', 'tier': 'T2', 'owner': owner, 'area': None, 'updated_at': None}


def _identity_fields(person: dict[str, Any]) -> list[dict[str, Any]]:
    fields: list[dict[str, Any]] = []
    if person.get('full_name'):
        fields.append(_onboarding(f"Name: {person['full_name']}", 'identity.personality'))
    age = _age(person.get('dob'))
    if age is not None:
        fields.append(_onboarding(f'Age: {age}', 'identity.personality'))
    if person.get('location'):
        fields.append(_onboarding(f"Home: {person['location']}", 'lifestyle.places'))
    if person.get('quote'):
        fields.append(_onboarding(f'A line they chose for themselves: "{person["quote"]}"', 'identity.values'))
    interests = [i.replace('_', ' ') for i in person.get('interests') or []]
    if interests:
        fields.append(_onboarding(f"Interests: {', '.join(interests)}", 'growth.curiosity'))
    if person.get('other_interests'):
        fields.append(_onboarding(f"Also into: {person['other_interests']}", 'growth.curiosity'))
    return fields


def _goal_fields(profile_email: str) -> list[dict[str, Any]]:
    fields = []
    for intention in intentions_repo.list_active_intentions(profile_email):
        checkins = intentions_repo.list_checkins(intention['intention_id'], profile_email)
        recent = ', '.join(str(c['actual_minutes']) for c in sorted(checkins, key=lambda c: c['checkin_date'])[-5:])
        value = f"{intention['title']}: {intention['target_minutes']} min/day" + (f' (recent: {recent} min)' if recent else '')
        fields.append({'value': value, 'source': 'said', 'evidence': [intention['intention_id']], 'confidence': 1.0,
                       'status': 'confirmed', 'tier': 'T2', 'owner': 'behaviour.goals', 'area': intention['domain'],
                       'updated_at': intention.get('created_at')})
    return fields


def _accepted_entries(profile_email: str) -> list[dict[str, Any]]:
    fields = []
    for area in profile_store.list_domains(profile_email):
        entry = profile_store.get_accepted(profile_email, area)
        if entry:
            fields.append({'value': entry['content'], 'source': 'accepted', 'evidence': [entry['profile_entry_id']],
                           'confidence': 1.0, 'status': 'confirmed', 'tier': 'T2', 'owner': 'life_story.growth_narrative',
                           'area': area, 'updated_at': entry.get('accepted_at')})
    return fields


def _age(dob: str | None) -> int | None:
    if not dob:
        return None
    try:
        birth = date.fromisoformat(dob[:10])
    except ValueError:
        return None
    today = date.today()
    return today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
