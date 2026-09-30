from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from . import goals_repo

# How many days of history to pull for the streak computation, and how long a
# consecutive under-target streak must be before it's worth interrupting the
# user about (US-004: "7 consecutive days" is the story's own example).
SHORTFALL_WINDOW_DAYS = 7
SHORTFALL_STREAK_THRESHOLD = 7


def today_iso() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _compute_streak_under_target(logs: list[dict[str, Any]], target_minutes: int) -> int:
    """Consecutive calendar days, walking backward from the most recent logged

    day, where a session was logged AND fell short of the target. A day that
    met/exceeded target stops the streak at 0 (the goal was actually hit). A
    calendar gap with no log at all also stops counting further back — no
    logged data for a day means no claim can be made about it (this mechanism
    only re-evaluates on new data, it never assumes what happened on an
    unlogged day; see US-004's "no background scheduler" scoping note).
    """
    if not logs:
        return 0

    by_date = {row['log_date']: row['actual_minutes'] for row in logs}
    streak = 0
    cursor = datetime.fromisoformat(max(by_date)).date()
    while True:
        key = cursor.isoformat()
        if key not in by_date:
            break
        if by_date[key] >= target_minutes:
            break
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def recsession(profile_email: str, goal_id: str, log_date: str, minutes: int) -> dict[str, Any]:
    """Writes one logged session and deterministically re-evaluates the goal's

    shortfall state. Never calls the model — this is the write-gate
    equivalent for goal tracking, same spirit as `memory_manager`'s
    `_apply_write_gate`: the model only ever composes language from a pattern
    this function has already decided exists.
    """
    goals_repo.upsert_goal_log(goal_id, profile_email, log_date, minutes)
    goal = goals_repo.get_goal(goal_id, profile_email)
    if goal is None:
        raise KeyError(f'Unknown goal {goal_id} for {profile_email}')

    logs = goals_repo.list_goal_logs(goal_id, profile_email, limit_days=SHORTFALL_WINDOW_DAYS)
    streak = _compute_streak_under_target(logs, goal['target_minutes'])
    goal = goals_repo.update_goal_progress(goal_id, profile_email, streak=streak, last_evaluated_date=today_iso())
    assert goal is not None

    if streak == 0:
        if goal['state'] != goals_repo.ON_TRACK:
            goal = goals_repo.clear_nudge(goal_id, profile_email, new_state=goals_repo.ON_TRACK)
        return {'needs_response': False, 'goal': goal}

    already_flagged = goal['state'] in (goals_repo.RENEGOTIATION_OFFERED, goals_repo.ADJUSTED) and goal['last_nudged_date']
    if streak >= SHORTFALL_STREAK_THRESHOLD and not already_flagged:
        return {'needs_response': True, 'goal': goal, 'logs': logs, 'streak': streak}

    return {'needs_response': False, 'goal': goal}
