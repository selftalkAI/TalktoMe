from __future__ import annotations

import json
from typing import Any

from . import goal_tracker, goals_repo
from .clients import AgenticServiceClient, AgenticServiceError

# Same layer as memory_manager.py: the model proposes a classification of a
# piece of journal text, this module's deterministic gate decides what — if
# anything — actually happens to durable state (ADR-007). Nothing here trusts
# the model's classification blindly; each branch re-checks the preconditions
# that make it valid before touching goals_repo/goal_tracker.


def consider_for_goals(profile_email: str, content: str) -> str | None:
    """Reads one just-written moment for a goal-tracking signal (US-004) and

    applies it. Best-effort, same failure contract as memory_manager's
    remember_from_text: a missing/unreachable Agentic Service must never
    block saving the moment, so failures here are swallowed, not raised.

    Returns a message to use as this moment's reflection when a shortfall
    nudge fired (the caller uses this in place of the normal reflect_moment
    call); returns None otherwise, meaning "nothing special happened here."
    """
    content = (content or '').strip()
    if not content:
        return None

    active_goals = goals_repo.list_goals(profile_email)
    active_goal = active_goals[0] if active_goals else None

    try:
        agentic = AgenticServiceClient()
        goal_payload = json.dumps(
            {
                'mode': 'extract_goal_signal',
                'source_text': content,
                'active_goal': (
                    {'title': active_goal['title'], 'target_minutes': active_goal['target_minutes']}
                    if active_goal
                    else None
                ),
                'has_pending_nudge': bool(active_goal and active_goal['pending_nudge_message']),
            }
        )
        run = agentic.create_agent_run('smart', user_id=profile_email, goal=goal_payload)
    except AgenticServiceError:
        return None

    if run.get('status') != 'completed':
        return None
    steps = run.get('steps') or []
    result = steps[0].get('result') if steps else None
    if not isinstance(result, dict):
        return None

    signal = result.get('signal')

    if signal == 'new_goal' and active_goal is None:
        title = (result.get('title') or '').strip()
        target = result.get('target_minutes')
        if title and isinstance(target, int) and target > 0:
            goals_repo.create_goal(profile_email, title, target)
        return None

    if signal == 'session_log' and active_goal is not None:
        minutes = result.get('minutes')
        if isinstance(minutes, int) and minutes >= 0:
            outcome = goal_tracker.record_session(
                profile_email, active_goal['goal_id'], goal_tracker.today_iso(), minutes
            )
            if outcome['needs_response']:
                return _compose_and_persist_nudge(profile_email, outcome)
        return None

    if signal == 'adjustment' and active_goal is not None and active_goal['pending_nudge_message']:
        target = result.get('target_minutes')
        if isinstance(target, int) and target > 0:
            goals_repo.supersede_goal(active_goal['goal_id'], profile_email, target)
        return None

    return None


def _compose_and_persist_nudge(profile_email: str, outcome: dict[str, Any]) -> str | None:
    """Calls the goal_shortfall_response mode and persists the result — same

    deterministic-gate-already-decided, model-only-composes-language shape as
    the rest of this module."""
    goal = outcome['goal']
    logs = outcome['logs']
    streak = outcome['streak']

    try:
        agentic = AgenticServiceClient()
        goal_payload = json.dumps(
            {
                'mode': 'goal_shortfall_response',
                'title': goal['title'],
                'target_minutes': goal['target_minutes'],
                'streak': streak,
                'logs': [{'log_date': l['log_date'], 'actual_minutes': l['actual_minutes']} for l in logs],
            }
        )
        run = agentic.create_agent_run('smart', user_id=profile_email, goal=goal_payload)
    except AgenticServiceError:
        return None

    if run.get('status') != 'completed':
        return None
    steps = run.get('steps') or []
    result = steps[0].get('result') if steps else None
    if not isinstance(result, dict):
        return None

    message = result.get('message') or ''
    if not message:
        return None

    goals_repo.set_nudge(
        goal['goal_id'],
        profile_email,
        message=message,
        suggested_target=result.get('suggested_target_minutes'),
        last_nudged_date=goal_tracker.today_iso(),
    )
    return message
