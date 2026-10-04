from __future__ import annotations

from typing import Any

from .. import memory_repo, profiles_repo
from ..spinal_cord import AgenticServiceClient, AgenticServiceError
from . import coach, intentions_repo, profile_store
from .checks import check_reply

# This module is Brain 2's orchestrator for the intention/support/Profile
# loop (ADD §8.2, ADR-013) — it decides WHETHER and calls the right cognitive
# agent (Amygdala for a support message; Brain 2's checked reply step,
# `coach.py`, for the reply itself) to compose the language. It
# never calls a model to decide whether something happened — that's
# `intentions_repo.shortfall_streak`, a deterministic gate, same layer as
# `memory_manager.py`'s write-gate. A model is only ever asked to compose
# language once this module has already decided a moment is worth talking
# about.
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


def _profile_facts(profile_email: str) -> dict[str, Any]:
    """Who Brain 1 actually is — name, age, location, interests, their own

    chosen quote — the same facts Thalamus/Sensory Cortex/Prefrontal Cortex
    already ground their language in (`main.py`'s `_profile_facts`). Amygdala
    and Broca previously never received this at all, which is why their
    output could read generic/cold instead of like it's actually talking to
    this one person. Returns {} (not an error) if the profile can't be found
    — language composition degrading to "less personalized" must never block
    the support/proposal flow.
    """
    profile = profiles_repo.get_profile(profile_email)
    if profile is None:
        return {}
    return {
        'full_name': profile.get('full_name'),
        'dob': profile.get('dob'),
        'location': profile.get('location'),
        'interests': profile.get('interests'),
        'other_interests': profile.get('other_interests'),
        'quote': profile.get('quote'),
    }


def offer_support(profile_email: str, intention: dict[str, Any], streak: int, checkins: list[dict[str, Any]]) -> dict[str, Any]:
    """Brain 2 notices, and asks — it never decides what Brain 1 should do.

    This never touches durable state; the returned message is something to
    show Brain 1, not something recorded as fact about them.
    """
    payload = {
        **_profile_facts(profile_email),
        'domain': intention['domain'],
        'title': intention['title'],
        'target_minutes': intention['target_minutes'],
        'streak': streak,
        'checkins': [
            {'checkin_date': c['checkin_date'], 'actual_minutes': c['actual_minutes'], 'note': c.get('note')}
            for c in checkins
        ],
    }
    try:
        agentic = AgenticServiceClient()
        run = agentic.create_agent_run('amygdala', user_id=profile_email, goal=_as_json(payload))
    except AgenticServiceError:
        return _fallback_support_message(intention, streak)

    result = _first_step_result(run)
    if result is None or not result.get('message'):
        return _fallback_support_message(intention, streak)

    # Shown to the person, so it must pass Brain 2's Check like any reply
    # (FSD BR-016). A failing message is dropped, not shown — Brain 2's own
    # reply for the turn still carries the support context.
    allowed = '\n'.join([str(intention['target_minutes']), str(streak), *(str(c['actual_minutes']) for c in checkins)])
    message = result['message'] if check_reply(result['message'], allowed_text=allowed).passed else ''
    return {'message': message, 'suggested_target_minutes': result.get('suggested_target_minutes')}


def propose_refinement(
    profile_email: str,
    domain: str,
    user_reflection: str,
    intention: dict[str, Any] | None = None,
    streak: int | None = None,
    support_message: str = '',
    source_memory_ids: list[str] | None = None,
    conversation_history: str | None = None,
    checkin_mode: bool = False,
    escalation_level: int = 0,
    conversation: list[dict[str, str]] | None = None,
    trigger: str = 'message',
) -> dict[str, Any]:
    """Brain 2's reply for this turn, stored as a `profile_entries` row with
    status='proposed' — never written as durable; only `accept_proposal` can
    change that.

    The text comes from Brain 2's checked reply step (`coach.reply`: Context
    Pack → plan → Speak → Check → rewrite once → safe fallback), so nothing
    that fails Check is ever stored or shown (FSD BR-016). Storing every chat
    reply as a proposal is the pre-redesign contract callers still rely on;
    Brain 2 Phase E separates chat replies from (rare) profile proposals.

    `conversation` is the thread so far as real turns
    (`{'role': 'user'|'assistant', 'content': ...}`), not including
    `user_reflection`. `conversation_history` is the older "User: …/Brain 2: …"
    transcript string, still accepted and converted. `trigger` is 'message',
    or 'silence'/'schedule' when Brain 2 reaches out without new input.
    """
    domain_memories = memory_repo.list_memories(profile_email, status=memory_repo.ACTIVE, domain=domain)
    checkins = intentions_repo.list_checkins(intention['intention_id'], profile_email) if intention else None
    if not user_reflection.strip() and trigger == 'message':
        trigger = 'schedule'

    result = coach.reply(
        profile_email,
        domain,
        user_reflection,
        conversation=conversation if conversation is not None else _turns_from_history(conversation_history),
        trigger=trigger,
        intention=intention,
        checkins=checkins,
        streak=streak,
        support_message=support_message,
        checkin_mode=checkin_mode,
        escalation_level=escalation_level,
    )

    return profile_store.propose(
        profile_email=profile_email,
        domain=domain,
        content=result['content'],
        source_memory_ids=source_memory_ids or [m['memory_id'] for m in domain_memories],
    )


def _turns_from_history(conversation_history: str | None) -> list[dict[str, str]]:
    """Converts the older "User: …" / "Brain 2: …" transcript into real turns."""
    turns: list[dict[str, str]] = []
    for line in (conversation_history or '').splitlines():
        speaker, _, text = line.partition(':')
        if not text.strip():
            continue
        role = 'assistant' if speaker.strip().lower().startswith('brain 2') else 'user'
        turns.append({'role': role, 'content': text.strip()})
    return turns


def accept_proposal(profile_entry_id: str, profile_email: str) -> dict[str, Any]:
    """The one and only path to a durable Profile write. See `profile_store.accept`."""
    return profile_store.accept(profile_entry_id, profile_email)


def refine_proposal(
    profile_entry_id: str,
    profile_email: str,
    additional_reflection: str,
    intention: dict[str, Any] | None = None,
    streak: int | None = None,
    support_message: str = '',
) -> dict[str, Any]:
    """Brain 1 isn't satisfied with the draft — reject this version and draft a

    new one incorporating what they added. The rejected draft stays in
    history; nothing about it is deleted. `intention`/`streak` are only
    passed when this domain's proposal came from the goal-adherence flow
    (see `propose_refinement`) — every other domain refines from its own
    `memories`, which `propose_refinement` re-reads on its own.
    """
    entry = profile_store.get_entry(profile_entry_id, profile_email)
    if entry is None:
        raise KeyError(f'Unknown profile entry {profile_entry_id} for {profile_email}')
    profile_store.reject(profile_entry_id, profile_email)

    return propose_refinement(
        profile_email=profile_email,
        domain=entry['domain'],
        user_reflection=additional_reflection,
        intention=intention,
        streak=streak,
        support_message=support_message,
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
            f"{intention['title']} has been under {intention['target_minutes']} minutes for {streak} days "
            'running — that usually means the plan, not you, needs adjusting. What got in the way this week?'
        ),
        'suggested_target_minutes': None,
    }
