from __future__ import annotations

from typing import Any

from ..clients import AgenticServiceClient, AgenticServiceError
from . import intentions_repo, profile_store

# Brain 2 is one orchestrating model taking on different jobs at different
# moments (ADD §8.2, ADR-013) — this module IS that orchestrator for the
# intention/support/Profile loop. It never calls the model to decide WHETHER
# something happened (that's `intentions_repo.shortfall_streak`, a
# deterministic gate, same layer as `memory_manager.py`'s write-gate); the
# model is only ever asked to compose language once this module has already
# decided a moment is worth talking about.
#
# Every path that could change durable state is explicit and named for what
# it does to Brain 1's trust: `set_intention` and `log_checkin` write ground
# truth Brain 1 stated directly. `offer_support` and `propose_refinement`
# never write anything durable — they return a draft. Only `accept_proposal`
# ever supersedes a Profile entry.


def set_intention(profile_email: str, domain: str, title: str, target_minutes: int) -> dict[str, Any]:
    """Brain 1 states an intention in their own words — explicit and

    self-authored, so it needs no reflection-check before becoming trackable
    (the reflection gate is for relayed content, not a person's own stated
    goal; `FSD FR-PROF-002`).
    """
    return intentions_repo.create_intention(profile_email, domain, title, target_minutes)


def log_checkin(
    profile_email: str, intention_id: str, minutes: int, checkin_date: str | None = None, note: str | None = None
) -> dict[str, Any]:
    """Ground truth for one day, then the deterministic check for whether

    Brain 2 should say anything at all. Returns `needs_support=True` only on a
    real, multi-day pattern — one missed day is not a pattern (`SHORTFALL_STREAK_THRESHOLD`).
    """
    checkin_date = checkin_date or intentions_repo.today_iso()
    intentions_repo.log_checkin(intention_id, profile_email, checkin_date, minutes, note)

    intention = intentions_repo.get_intention(intention_id, profile_email)
    assert intention is not None
    checkins = intentions_repo.list_checkins(intention_id, profile_email)
    streak = intentions_repo.shortfall_streak(checkins, intention['target_minutes'])

    return {
        'intention': intention,
        'checkins': checkins,
        'streak': streak,
        'needs_support': streak >= intentions_repo.SHORTFALL_STREAK_THRESHOLD,
    }


def offer_support(profile_email: str, intention: dict[str, Any], streak: int, checkins: list[dict[str, Any]]) -> dict[str, Any]:
    """Brain 2 notices, and asks — it never decides what Brain 1 should do.

    This never touches durable state; the returned message is something to
    show Brain 1, not something recorded as fact about them.
    """
    payload = {
        'mode': 'brain2_support_message',
        'domain': intention['domain'],
        'title': intention['title'],
        'target_minutes': intention['target_minutes'],
        'streak': streak,
        'checkins': [{'checkin_date': c['checkin_date'], 'actual_minutes': c['actual_minutes']} for c in checkins],
    }
    try:
        agentic = AgenticServiceClient()
        run = agentic.create_agent_run('smart', user_id=profile_email, goal=_as_json(payload))
    except AgenticServiceError:
        return _fallback_support_message(intention, streak)

    result = _first_step_result(run)
    if result is None or not result.get('message'):
        return _fallback_support_message(intention, streak)
    return {'message': result['message'], 'suggested_target_minutes': result.get('suggested_target_minutes')}


def propose_refinement(
    profile_email: str,
    intention: dict[str, Any],
    streak: int,
    support_message: str,
    user_reflection: str,
    source_memory_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Drafts the Profile proposal — never writes it. Returns a `profile_entries`

    row with status='proposed'; only `accept_proposal` can ever change that.
    """
    previous = profile_store.get_accepted(profile_email, intention['domain'])
    payload = {
        'mode': 'brain2_profile_narrative',
        'domain': intention['domain'],
        'title': intention['title'],
        'target_minutes': intention['target_minutes'],
        'streak': streak,
        'support_message': support_message,
        'user_reflection': user_reflection,
        'previous_entry_content': previous['content'] if previous else None,
    }
    try:
        agentic = AgenticServiceClient()
        run = agentic.create_agent_run('smart', user_id=profile_email, goal=_as_json(payload))
        result = _first_step_result(run)
        content = (result or {}).get('content') or ''
    except AgenticServiceError:
        content = ''

    if not content:
        content = _fallback_profile_content(intention, streak, support_message, user_reflection)

    return profile_store.propose(
        profile_email=profile_email,
        domain=intention['domain'],
        content=content,
        source_memory_ids=source_memory_ids or [],
    )


def accept_proposal(profile_entry_id: str, profile_email: str) -> dict[str, Any]:
    """The one and only path to a durable Profile write. See `profile_store.accept`."""
    return profile_store.accept(profile_entry_id, profile_email)


def refine_proposal(
    profile_entry_id: str, profile_email: str, additional_reflection: str, streak: int, support_message: str
) -> dict[str, Any]:
    """Brain 1 isn't satisfied with the draft — reject this version and draft a

    new one incorporating what they added. The rejected draft stays in
    history; nothing about it is deleted.
    """
    entry = profile_store.get_entry(profile_entry_id, profile_email)
    if entry is None:
        raise KeyError(f'Unknown profile entry {profile_entry_id} for {profile_email}')
    profile_store.reject(profile_entry_id, profile_email)

    intention = intentions_repo.get_active_intention(profile_email, entry['domain'])
    if intention is None:
        raise KeyError(f"No active intention for domain '{entry['domain']}' to refine against")

    combined_reflection = additional_reflection
    return propose_refinement(
        profile_email=profile_email,
        intention=intention,
        streak=streak,
        support_message=support_message,
        user_reflection=combined_reflection,
        source_memory_ids=entry['source_memory_ids'],
    )


def reject_proposal(profile_entry_id: str, profile_email: str) -> dict[str, Any]:
    return profile_store.reject(profile_entry_id, profile_email)


def adjust_intention(profile_email: str, intention_id: str, new_target_minutes: int) -> dict[str, Any]:
    """Brain 1 accepted Brain 2's suggested smaller target — this is Brain 1's

    call being carried out, not Brain 2 deciding on its own.
    """
    return intentions_repo.supersede_intention(intention_id, profile_email, new_target_minutes)


def _first_step_result(run: dict[str, Any]) -> dict[str, Any] | None:
    if run.get('status') != 'completed':
        return None
    steps = run.get('steps') or []
    result = steps[0].get('result') if steps else None
    return result if isinstance(result, dict) else None


def _as_json(payload: dict[str, Any]) -> str:
    import json

    return json.dumps(payload)


def _fallback_support_message(intention: dict[str, Any], streak: int) -> dict[str, Any]:
    """Used only when the Agentic Service is unreachable — a plain, honest,

    still-never-commanding message so the loop stays demonstrable without a
    model provider configured. Not a substitute for the real thing.
    """
    return {
        'message': (
            f"I noticed {intention['title']} has been under {intention['target_minutes']} min/day for "
            f'{streak} days running. What got in the way this week? And would a smaller daily target '
            f'feel more doable right now than {intention["target_minutes"]} min — or is it something else?'
        ),
        'suggested_target_minutes': None,
    }


def _fallback_profile_content(intention: dict[str, Any], streak: int, support_message: str, user_reflection: str) -> str:
    reflection = user_reflection or 'no reflection was recorded'
    return (
        f"For {streak} days you fell short of your {intention['target_minutes']} min/day goal for "
        f"'{intention['title']}'. Brain 2 asked what was getting in the way instead of pushing harder. "
        f'You said: {reflection}'
    )
