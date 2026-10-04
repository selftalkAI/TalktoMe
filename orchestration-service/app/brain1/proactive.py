from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from .. import conversations_repo, profiles_repo
from ..config import settings
from ..db import get_connection
from . import here_now

logger = logging.getLogger(__name__)

# Brain 1's Curious / proactive mode (Building_Brain1.md §14.3, Scenario 4):
# when a conversation is waiting on them, Brain 1 decides WHETHER reaching
# out would help — never just because time passed. Every rule here is
# deterministic and explainable:
#   - they haven't replied for long enough (BRAIN1_CHECKIN_AFTER_HOURS)
#   - at most MAX_UNANSWERED_CHECKINS check-ins in a row without a reply
#   - at most BRAIN1_MAX_CHECKINS_PER_DAY across all areas
#   - not at night in their city (quiet hours)
#   - not after a crisis — that needs people, not an app nudging
#   - not if their last check-ins went unanswered every time (it isn't welcome)
# The check-in itself is a normal Brain 2 turn with trigger='silence': gentle,
# about them not the goal, never inventing their words or numbers.

MAX_UNANSWERED_CHECKINS = 2
QUIET_PARTS_OF_DAY = ('night',)
CRISIS_LOOKBACK_HOURS = 72


def decide(profile_email: str, waiting: dict[str, Any], *, respect_timing: bool = True,
           respect_quiet_hours: bool = True) -> dict[str, Any]:
    """`{'reach_out': bool, 'reason': str}` for one area awaiting their reply.
    `respect_timing=False` skips the hours-since-last-turn and daily-cap rules
    (the interactive demo uses its own idle timer instead)."""
    if respect_timing:
        hours = conversations_repo.minutes_since(waiting['last_turn']['created_at']) / 60
        if hours < settings.brain1_checkin_after_hours:
            return _no(f'only {hours:.1f}h since the last message')
        if conversations_repo.proactive_count_since(profile_email, _start_of_today()) >= settings.brain1_max_checkins_per_day:
            return _no('already checked in today')
    if waiting['proactive_since_reply'] >= MAX_UNANSWERED_CHECKINS:
        return _no(f"{waiting['proactive_since_reply']} check-ins already unanswered")
    if _recent_crisis(profile_email):
        return _no('recent crisis — people, not an app, should reach out')
    if _checkins_ignored(profile_email):
        return _no('their recent check-ins all went unanswered')
    if respect_quiet_hours:
        person = profiles_repo.get_profile(profile_email) or {}
        part = here_now.compute(person.get('location'))['part_of_day']
        if part in QUIET_PARTS_OF_DAY:
            return _no(f"it's {part} where they are")
    return {'reach_out': True, 'reason': 'a gentle check-in could help'}


def run_cycle() -> list[dict[str, Any]]:
    """Scheduler job: every person, every area waiting on them → maybe a check-in."""
    from ..brain2 import orchestrator  # late import: brain2 depends on brain1, not the other way round

    sent = []
    for person in profiles_repo.list_profiles():
        email = person['email']
        for waiting in conversations_repo.domains_awaiting_reply(email):
            decision = decide(email, waiting)
            if not decision['reach_out']:
                continue
            try:
                turns = conversations_repo.as_messages(conversations_repo.history(email, waiting['domain'], limit=10))
                turn = orchestrator.converse(email, waiting['domain'], '', conversation=turns, trigger='silence',
                                             escalation_level=waiting['proactive_since_reply'])
                sent.append({'email': email, 'domain': waiting['domain'], 'reply': turn['reply']})
            except Exception:  # noqa: BLE001 - one person's check-in must never stop the cycle
                logger.exception('Proactive check-in failed for %s', email)
    return sent


def _recent_crisis(profile_email: str) -> bool:
    since = conversations_repo.hours_ago(CRISIS_LOOKBACK_HOURS).isoformat()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM brain1_runs WHERE profile_email = ? AND safety_level = 'crisis' AND created_at >= ? LIMIT 1",
            (profile_email, since),
        ).fetchone()
    return row is not None


def _checkins_ignored(profile_email: str, last_n: int = 3) -> bool:
    """True when their last `last_n` scored check-ins were all met with silence."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT o.outcome FROM brain1_outcomes o JOIN brain1_runs r ON r.run_id = o.run_id "
            "WHERE o.profile_email = ? AND r.trigger = 'silence' ORDER BY o.created_at DESC LIMIT ?",
            (profile_email, last_n),
        ).fetchall()
    return len(rows) == last_n and all(r['outcome'] == 'silence' for r in rows)


def _start_of_today() -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def _no(reason: str) -> dict[str, Any]:
    return {'reach_out': False, 'reason': reason}

