from __future__ import annotations

import json
from typing import Any

from .. import memory_repo, profiles_repo
from ..brain1 import profile as brain1_profile
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


def converse(
    profile_email: str,
    domain: str,
    message: str,
    *,
    conversation: list[dict[str, str]] | None = None,
    trigger: str = 'message',
    intention: dict[str, Any] | None = None,
    streak: int | None = None,
    support_message: str = '',
    checkin_mode: bool = False,
    escalation_level: int = 0,
) -> dict[str, Any]:
    """One conversational turn (ADD §8.2): Brain 2's checked reply, plus —
    rarely — a separate profile proposal (Remember step, ADR-022).

    Returns `reply` (the chat text; never stored as a profile entry),
    `persona`, `reading`, `plan`, `verdict`, `fallback`, and `proposal` (a
    `profile_entries` row with status='proposed', or None). `conversation`
    is the thread so far as real turns, not including `message`.
    """
    checkins = intentions_repo.list_checkins(intention['intention_id'], profile_email) if intention else None
    result = coach.reply(
        profile_email,
        domain,
        message,
        conversation=conversation,
        trigger=trigger,
        intention=intention,
        checkins=checkins,
        streak=streak,
        support_message=support_message,
        checkin_mode=checkin_mode,
        escalation_level=escalation_level,
    )
    proposal = None
    if trigger == 'message' and result['safety'] == 'ok' and _learned_something_lasting(profile_email, domain, result['reading'], intention):
        proposal = propose_refinement(profile_email, domain, message, intention=intention, streak=streak)
    brain1_profile.save_version(profile_email, brain1_profile.build(profile_email), reason=f'turn:{domain}')
    return {
        'reply': result['content'],
        'safety': result['safety'],
        'run_id': result.get('run_id'),
        'persona': result['persona'],
        'reading': result['reading'],
        'plan': result['plan'],
        'verdict': result['verdict'],
        'fallback': result['fallback'],
        'proposal': proposal,
    }


# How much new, durable material in one area justifies offering a profile
# update. Lower = more proposals; the point of ADR-022 is that they are rare.
NEW_MEMORIES_FOR_PROPOSAL = 3


def _learned_something_lasting(
    profile_email: str, domain: str, reading: dict[str, Any], intention: dict[str, Any] | None
) -> bool:
    """The Remember step's gate — deterministic, never a model's call:
    a goal milestone reached today, or enough new durable memories in this
    area since the last proposal, with nothing already waiting for review."""
    history = profile_store.history(profile_email, domain)
    if history and history[-1]['status'] == profile_store.PROPOSED:
        return False  # one pending proposal per area at a time

    minutes = reading.get('minutes_today')
    if intention and reading.get('did_it_today') and isinstance(minutes, int) and minutes >= intention['target_minutes']:
        return True

    since = history[-1]['proposed_at'] if history else ''
    fresh = [
        m
        for m in memory_repo.list_memories(profile_email, status=memory_repo.ACTIVE, domain=domain)
        if m['created_at'] > since and m.get('sensitivity_tier') != 'T3'
    ]
    return len(fresh) >= NEW_MEMORIES_FOR_PROPOSAL


def propose_refinement(
    profile_email: str,
    domain: str,
    user_reflection: str,
    intention: dict[str, Any] | None = None,
    streak: int | None = None,
    support_message: str = '',
    source_memory_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Drafts a durable Profile entry for one area — never writes it. Returns
    a `profile_entries` row with status='proposed'; only `accept_proposal`
    can change that (ADR-014). Not a chat reply (ADR-022): a short, checked
    snapshot written by Broca `profile_narrative`, grounded in this area's
    non-T3 memories and goal history.
    """
    domain_memories = [
        m
        for m in memory_repo.list_memories(profile_email, status=memory_repo.ACTIVE, domain=domain)
        if m.get('sensitivity_tier') != 'T3'
    ]
    previous = profile_store.get_accepted(profile_email, domain)
    payload: dict[str, Any] = {
        **_profile_facts(profile_email),
        'operation': 'profile_narrative',
        'domain': domain,
        'user_reflection': user_reflection,
        'previous_entry_content': previous['content'] if previous else None,
        'domain_memories': [m['content'] for m in domain_memories],
    }
    if intention is not None:
        payload.update({'title': intention['title'], 'target_minutes': intention['target_minutes'], 'streak': streak})

    allowed = '\n'.join([json.dumps(payload), support_message])
    content = ''
    for _ in range(2):
        draft = _run_broca(profile_email, payload)
        result = check_reply(draft, allowed_text=allowed, max_words=NARRATIVE_MAX_WORDS, max_questions=0)
        if result.passed:
            content = draft
            break
        payload['rewrite_feedback'] = result.feedback()
    if not content:
        content = _fallback_profile_content(domain, user_reflection, intention)

    return profile_store.propose(
        profile_email=profile_email,
        domain=domain,
        content=content,
        source_memory_ids=source_memory_ids or [m['memory_id'] for m in domain_memories],
    )


NARRATIVE_MAX_WORDS = 90


def _run_broca(profile_email: str, payload: dict[str, Any]) -> str:
    try:
        run = AgenticServiceClient().create_agent_run('broca', user_id=profile_email, goal=_as_json(payload))
    except AgenticServiceError:
        return ''
    return ((_first_step_result(run) or {}).get('content') or '').strip()


def _fallback_profile_content(domain: str, user_reflection: str, intention: dict[str, Any] | None) -> str:
    """Plain and honest — used only when no draft passed Check."""
    if intention is not None:
        return f"You're working toward {intention['title'].lower()}, {intention['target_minutes']} minutes a day — this area is still taking shape."
    if user_reflection.strip():
        return f"In {domain}, you said: \"{user_reflection.strip()[:200]}\""
    return f'Not much is known about {domain} yet — it will fill in as you talk about it.'


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
