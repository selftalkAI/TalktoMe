from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from ..db import get_connection
from . import knowledge

# Brain 1's Learned layer (Building_Brain1.md §9.5): what works for THIS
# person. Every Brain 2 reply is traced with the persona, stance and cards it
# used (`runs.py`); the person's next move scores that reply (`brain1_outcomes`):
#
#   took_action  they did it / report a step taken        +2
#   change_talk  they talk toward change (MI DARN-CAT)    +1
#   accepted     they accepted a profile proposal         +1
#   sustain      normal ambivalence                        0
#   silence      no reply until Brain 2 checked in        -0.5
#   discord      pushback                                 -2
#
# Weights only act once there is enough evidence (MIN_EVIDENCE), so one bad
# reply never locks a person out of an approach. Her own explicit choices
# (e.g. a voice) always win over anything learned.

OUTCOME_VALUES = {'took_action': 2.0, 'change_talk': 1.0, 'accepted': 1.0, 'sustain': 0.0, 'silence': -0.5, 'discord': -2.0}
_CHANGE_TALK = ('desire', 'ability', 'reason', 'need', 'commitment', 'activation')
MIN_EVIDENCE_TO_AVOID = 2
MIN_EVIDENCE_TO_PREFER = 3
AVOID_AT_OR_BELOW = -1.0
PREFER_AT_OR_ABOVE = 1.0
WINDOW_DAYS = 90
SCORABLE_HOURS = 72  # a reply older than this is not scored by a new message


def outcome_from_reading(reading: dict[str, Any]) -> str | None:
    """How their message responds to the previous reply — None when it says
    nothing either way (that is not evidence, so nothing is recorded)."""
    talk, intent = reading.get('change_talk'), reading.get('intent')
    if talk == 'discord' or intent == 'pushback':
        return 'discord'
    if reading.get('did_it_today') is True or talk == 'taking_steps':
        return 'took_action'
    if talk in _CHANGE_TALK:
        return 'change_talk'
    if talk == 'sustain':
        return 'sustain'
    return None


def score_previous_turn(profile_email: str, *, reading: dict[str, Any] | None = None, outcome: str | None = None) -> str | None:
    """Scores Brain 2's latest unscored reply with this outcome (or the one
    derived from `reading`). Returns the outcome recorded, or None."""
    outcome = outcome or outcome_from_reading(reading or {})
    if outcome is None:
        return None
    run = _latest_unscored_run(profile_email)
    if run is None:
        return None
    record(profile_email, run, outcome)
    return outcome


def record(profile_email: str, run: dict[str, Any], outcome: str) -> None:
    if outcome not in OUTCOME_VALUES:
        raise ValueError(f'Unknown outcome {outcome!r}')
    trace = run.get('trace') or json.loads(run.get('trace_json') or '{}')
    with get_connection() as conn:
        conn.execute(
            'INSERT INTO brain1_outcomes (outcome_id, profile_email, run_id, card_ids, voice, expertise, stance, outcome, created_at) '
            'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (
                str(uuid.uuid4()), profile_email, run.get('run_id'), json.dumps(trace.get('cards') or []),
                (trace.get('persona') or {}).get('voice'), (trace.get('persona') or {}).get('expertise'),
                (trace.get('plan') or {}).get('stance'), outcome, datetime.now(timezone.utc).isoformat(),
            ),
        )


def record_for_latest_run(profile_email: str, outcome: str) -> bool:
    """For signals that aren't a reply to the latest message (e.g. accepting
    a proposal): attribute to Brain 2's most recent reply, scored or not."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM brain1_runs WHERE profile_email = ? AND safety_level != 'crisis' ORDER BY created_at DESC LIMIT 1",
            (profile_email,),
        ).fetchone()
    if row is None:
        return False
    record(profile_email, dict(row), outcome)
    return True


def weights(profile_email: str) -> dict[str, dict[str, dict[str, Any]]]:
    """{'cards'|'voices'|'stances': {key: {'n', 'average', 'counts'}}} over the window."""
    since = (datetime.now(timezone.utc) - timedelta(days=WINDOW_DAYS)).isoformat()
    with get_connection() as conn:
        rows = conn.execute(
            'SELECT card_ids, voice, stance, outcome FROM brain1_outcomes WHERE profile_email = ? AND created_at >= ?',
            (profile_email, since),
        ).fetchall()
    tallies: dict[str, dict[str, list[str]]] = {'cards': {}, 'voices': {}, 'stances': {}}
    for row in rows:
        for card_id in json.loads(row['card_ids'] or '[]'):
            tallies['cards'].setdefault(card_id, []).append(row['outcome'])
        if row['voice'] and row['voice'] not in ('care',):
            tallies['voices'].setdefault(row['voice'], []).append(row['outcome'])
        if row['stance']:
            tallies['stances'].setdefault(row['stance'], []).append(row['outcome'])
    return {kind: {key: _summarise(outcomes) for key, outcomes in items.items()} for kind, items in tallies.items()}


def avoided(profile_email: str, w: dict[str, Any] | None = None) -> dict[str, set[str]]:
    w = w if w is not None else weights(profile_email)
    return {kind: {k for k, s in items.items() if s['n'] >= MIN_EVIDENCE_TO_AVOID and s['average'] <= AVOID_AT_OR_BELOW}
            for kind, items in w.items()}


def preferred(profile_email: str, w: dict[str, Any] | None = None) -> dict[str, set[str]]:
    w = w if w is not None else weights(profile_email)
    return {kind: {k for k, s in items.items() if s['n'] >= MIN_EVIDENCE_TO_PREFER and s['average'] >= PREFER_AT_OR_ABOVE}
            for kind, items in w.items()}


def works_text(profile_email: str) -> str:
    """'What works / what to avoid' for the Context Pack — plain language,
    only where there is enough evidence."""
    w = weights(profile_email)
    good, bad = preferred(profile_email, w), avoided(profile_email, w)
    lines = []
    for kind in ('cards', 'voices', 'stances'):
        for key in sorted(good[kind]):
            lines.append(f"- Works for them: {describe(kind, key)} ({evidence(w[kind][key])}).")
        for key in sorted(bad[kind]):
            lines.append(f"- Avoid: {describe(kind, key)} ({evidence(w[kind][key])}).")
    return '\n'.join(lines)


def describe(kind: str, key: str) -> str:
    if kind == 'cards':
        card = next((c for c in knowledge.cards() if c['id'] == key), None)
        return f'"{card["principle"]}"' if card else key
    if kind == 'voices':
        return f"talking like {key.replace('_', ' ')}"
    return f'a {key} approach'


def evidence(summary: dict[str, Any]) -> str:
    counts = summary['counts']
    good = counts.get('took_action', 0) + counts.get('change_talk', 0) + counts.get('accepted', 0)
    bad = counts.get('discord', 0) + counts.get('silence', 0)
    return f"{good} of {summary['n']} times it helped, {bad} times it didn't land"


def _summarise(outcomes: list[str]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for o in outcomes:
        counts[o] = counts.get(o, 0) + 1
    return {'n': len(outcomes), 'average': round(sum(OUTCOME_VALUES[o] for o in outcomes) / len(outcomes), 2), 'counts': counts}


def _latest_unscored_run(profile_email: str) -> dict[str, Any] | None:
    since = (datetime.now(timezone.utc) - timedelta(hours=SCORABLE_HOURS)).isoformat()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM brain1_runs WHERE profile_email = ? AND safety_level != 'crisis' AND created_at >= ? "
            'ORDER BY created_at DESC LIMIT 1',
            (profile_email, since),
        ).fetchone()
        if row is None:
            return None
        scored = conn.execute('SELECT 1 FROM brain1_outcomes WHERE run_id = ? LIMIT 1', (row['run_id'],)).fetchone()
    return None if scored else dict(row)
