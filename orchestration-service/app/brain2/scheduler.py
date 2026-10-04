from __future__ import annotations

import logging
from typing import Any

from .. import memory_repo, profiles_repo
from ..brain1 import reflector as brain1_reflector
from . import intentions_repo, orchestrator, profile_store

logger = logging.getLogger(__name__)

# Brain 2's Scheduler (ADD §8.2 step 1, §4 Operations plane) — the second way
# the Profile refinement loop starts, alongside Brain 1 providing new input.
# This is what lets Brain 2 keep working on Brain 1's Profile while Brain 1
# is away: it runs with NO new input, only re-checking what's already
# durable (checkins already logged, memories already captured), and drafts
# a proposal when there's something worth reviewing. Every gate here is
# deterministic, same ADR-007 split as memory_manager's write-gate: this
# module decides WHETHER to draft; orchestrator.propose_refinement is what
# actually asks the model to draft. Nothing here ever writes durably to a
# Profile — only Brain 1's own accept call can (ADR-014); this only ever
# produces more `proposed` rows for Brain 1 to find waiting next time they
# open the app (`profile_store.list_pending`).


def run_recheck_cycle() -> list[dict[str, Any]]:
    """One full pass over every profile and every domain with something to

    reconsider. Returns every newly drafted proposal. Best-effort per
    profile — one profile's failure (e.g. Agentic Service briefly down)
    must never stop the rest of the cycle, same contract as
    memory_manager.remember_from_text.
    """
    drafted: list[dict[str, Any]] = []
    for profile in profiles_repo.list_profiles():
        drafted.extend(run_for_profile(profile['email']))
    return drafted


def run_for_profile(profile_email: str) -> list[dict[str, Any]]:
    """One recheck pass for a single profile — what the interval job calls

    per-profile inside `run_recheck_cycle`, and what `brain1.create` calls
    once, immediately, the moment a new Brain 1 is created, so Brain 2's
    side of the relationship is demonstrably live from minute one rather
    than waiting for the next scheduled cycle (ADD §1.1, §8.2).
    """
    try:
        drafted = _recheck_profile(profile_email)
    except Exception:
        logger.exception('Brain 2 Scheduler: recheck failed for %s', profile_email)
        drafted = []
    # Brain 1's nightly reflection rides the same cycle (Building_Brain1.md §14.3).
    brain1_reflector.run_for_profile(profile_email)
    return drafted


def _recheck_profile(profile_email: str) -> list[dict[str, Any]]:
    drafted: list[dict[str, Any]] = []

    intentions = intentions_repo.list_active_intentions(profile_email)
    for intention in intentions:
        proposal = _recheck_intention_domain(profile_email, intention)
        if proposal is not None:
            drafted.append(proposal)

    intention_domains = {i['domain'] for i in intentions}
    for domain in _generic_domains_with_new_activity(profile_email, intention_domains):
        drafted.append(
            orchestrator.propose_refinement(profile_email=profile_email, domain=domain, user_reflection='')
        )

    return drafted


def _recheck_intention_domain(profile_email: str, intention: dict[str, Any]) -> dict[str, Any] | None:
    """Re-evaluates one active intention's already-logged checkins — catches

    a shortfall pattern that formed without anyone calling the /support
    endpoint afterward, the same deterministic streak gate `log_checkin`
    uses at write time (`intentions_repo.shortfall_streak`).
    """
    if _has_pending_proposal(profile_email, intention['domain']):
        return None  # already something waiting for Brain 1's review here

    checkins = intentions_repo.list_checkins(intention['intention_id'], profile_email)
    streak = intentions_repo.shortfall_streak(checkins, intention['target_minutes'])
    if streak < intentions_repo.SHORTFALL_STREAK_THRESHOLD:
        return None

    support = orchestrator.offer_support(profile_email, intention, streak, checkins)
    return orchestrator.propose_refinement(
        profile_email=profile_email,
        domain=intention['domain'],
        user_reflection='',
        intention=intention,
        streak=streak,
        support_message=support['message'],
    )


def _generic_domains_with_new_activity(profile_email: str, intention_domains: set[str]) -> list[str]:
    """Domains outside goal-adherence (skill/emotion/learning/reading/...)

    that have active memories newer than their latest Profile entry — or no
    Profile entry at all yet — and nothing already waiting for review. This
    is what makes the Scheduler domain-agnostic (ADD §6.1): any domain a
    memory gets tagged with is eligible, not just ones with an intention.
    """
    ready: list[str] = []
    for domain in memory_repo.list_domains(profile_email):
        if domain in intention_domains:
            continue  # that domain's recheck already went through the intention path above
        if _has_pending_proposal(profile_email, domain):
            continue

        newest_memory_at = memory_repo.latest_active_created_at(profile_email, domain)
        if newest_memory_at is None:
            continue

        history = profile_store.history(profile_email, domain)
        last_synthesized_at = history[-1]['proposed_at'] if history else None
        if last_synthesized_at is None or newest_memory_at > last_synthesized_at:
            ready.append(domain)
    return ready


def _has_pending_proposal(profile_email: str, domain: str) -> bool:
    history = profile_store.history(profile_email, domain)
    return bool(history) and history[-1]['status'] == profile_store.PROPOSED
