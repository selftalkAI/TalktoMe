from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from .db import get_connection, init_db

init_db()

ACTIVE = 'active'
SUPERSEDED = 'superseded'
DELETED = 'deleted'

ON_TRACK = 'on_track'
RENEGOTIATION_OFFERED = 'renegotiation_offered'
ADJUSTED = 'adjusted'


def _new_id() -> str:
    return f'goal_{uuid.uuid4().hex[:12]}'


def create_goal(profile_email: str, title: str, target_minutes: int, supersedes_goal_id: str | None = None) -> dict[str, Any]:
    goal_id = _new_id()
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            'INSERT INTO goals (goal_id, profile_email, title, target_minutes, status, state, '
            'current_streak_under_target, last_evaluated_date, last_nudged_date, pending_nudge_message, '
            'pending_nudge_suggested_target, supersedes_goal_id, created_at, updated_at) '
            'VALUES (?, ?, ?, ?, ?, ?, 0, NULL, NULL, NULL, NULL, ?, ?, ?)',
            (goal_id, profile_email, title, target_minutes, ACTIVE, ON_TRACK, supersedes_goal_id, now, now),
        )
    goal = get_goal(goal_id, profile_email)
    assert goal is not None  # just inserted it
    return goal


def get_goal(goal_id: str, profile_email: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            'SELECT * FROM goals WHERE goal_id = ? AND profile_email = ?',
            (goal_id, profile_email),
        ).fetchone()
    return dict(row) if row else None


def list_goals(profile_email: str, status: str | None = ACTIVE) -> list[dict[str, Any]]:
    query = 'SELECT * FROM goals WHERE profile_email = ?'
    params: list[Any] = [profile_email]
    if status is not None:
        query += ' AND status = ?'
        params.append(status)
    query += ' ORDER BY created_at DESC'
    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def upsert_goal_log(goal_id: str, profile_email: str, log_date: str, minutes: int) -> dict[str, Any]:
    """Writes actual minutes for one calendar day. Logging the same goal twice

    on the same day accumulates (two sessions in a day add up) rather than
    overwriting — this is the ground truth the shortfall evaluator reads, so
    it must never be silently lossy.
    """
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            'INSERT INTO goal_logs (goal_id, profile_email, log_date, actual_minutes, created_at) '
            'VALUES (?, ?, ?, ?, ?) '
            'ON CONFLICT(goal_id, log_date) DO UPDATE SET actual_minutes = actual_minutes + excluded.actual_minutes',
            (goal_id, profile_email, log_date, minutes, now),
        )
        row = conn.execute(
            'SELECT * FROM goal_logs WHERE goal_id = ? AND log_date = ?',
            (goal_id, log_date),
        ).fetchone()
    assert row is not None  # just wrote it
    return dict(row)


def list_goal_logs(goal_id: str, profile_email: str, limit_days: int) -> list[dict[str, Any]]:
    """Most recent `limit_days` logged calendar days, oldest to newest."""
    with get_connection() as conn:
        rows = conn.execute(
            'SELECT * FROM goal_logs WHERE goal_id = ? AND profile_email = ? '
            'ORDER BY log_date DESC LIMIT ?',
            (goal_id, profile_email, limit_days),
        ).fetchall()
    return [dict(row) for row in reversed(rows)]


def update_goal_progress(goal_id: str, profile_email: str, streak: int, last_evaluated_date: str) -> dict[str, Any] | None:
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            'UPDATE goals SET current_streak_under_target = ?, last_evaluated_date = ?, updated_at = ? '
            'WHERE goal_id = ? AND profile_email = ?',
            (streak, last_evaluated_date, now, goal_id, profile_email),
        )
    return get_goal(goal_id, profile_email)


def set_nudge(
    goal_id: str, profile_email: str, message: str, suggested_target: int | None, last_nudged_date: str
) -> dict[str, Any] | None:
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            'UPDATE goals SET state = ?, pending_nudge_message = ?, pending_nudge_suggested_target = ?, '
            'last_nudged_date = ?, updated_at = ? WHERE goal_id = ? AND profile_email = ?',
            (RENEGOTIATION_OFFERED, message, suggested_target, last_nudged_date, now, goal_id, profile_email),
        )
    return get_goal(goal_id, profile_email)


def clear_nudge(goal_id: str, profile_email: str, new_state: str = ON_TRACK) -> dict[str, Any] | None:
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            'UPDATE goals SET state = ?, pending_nudge_message = NULL, pending_nudge_suggested_target = NULL, '
            'updated_at = ? WHERE goal_id = ? AND profile_email = ?',
            (new_state, now, goal_id, profile_email),
        )
    return get_goal(goal_id, profile_email)


def supersede_goal(goal_id: str, profile_email: str, new_target_minutes: int) -> dict[str, Any]:
    """Adjusting a target supersedes the old goal rather than mutating it in

    place — the original target and the history of it not working stay
    auditable, same pattern as `memory_repo.correct_memory`.
    """
    old = get_goal(goal_id, profile_email)
    if old is None:
        raise KeyError(f'Unknown goal {goal_id} for {profile_email}')
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            'UPDATE goals SET status = ?, updated_at = ? WHERE goal_id = ? AND profile_email = ?',
            (SUPERSEDED, now, goal_id, profile_email),
        )
    new_goal = create_goal(profile_email, old['title'], new_target_minutes, supersedes_goal_id=goal_id)
    with get_connection() as conn:
        conn.execute(
            'UPDATE goals SET state = ? WHERE goal_id = ? AND profile_email = ?',
            (ADJUSTED, new_goal['goal_id'], profile_email),
        )
    updated = get_goal(new_goal['goal_id'], profile_email)
    assert updated is not None
    return updated
