from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from ..db import get_connection, init_db

init_db()

ACTIVE = 'active'
SUPERSEDED = 'superseded'

# How many consecutive days of missing a target before Brain 2 even considers
# offering support. Short enough to matter, long enough that one off day
# never triggers anything — Brain 1 is allowed to have a bad day in peace.
SHORTFALL_STREAK_THRESHOLD = 3
STREAK_LOOKBACK_DAYS = 14


def _new_intention_id() -> str:
    return f'intention_{uuid.uuid4().hex[:12]}'


def today_iso() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def create_intention(
    profile_email: str, domain: str, title: str, target_minutes: int, supersedes_intention_id: str | None = None
) -> dict[str, Any]:
    intention_id = _new_intention_id()
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            'INSERT INTO brain2_intentions (intention_id, profile_email, domain, title, target_minutes, '
            'status, supersedes_intention_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            (intention_id, profile_email, domain, title, target_minutes, ACTIVE, supersedes_intention_id, now),
        )
    intention = get_intention(intention_id, profile_email)
    assert intention is not None
    return intention


def get_intention(intention_id: str, profile_email: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            'SELECT * FROM brain2_intentions WHERE intention_id = ? AND profile_email = ?',
            (intention_id, profile_email),
        ).fetchone()
    return dict(row) if row else None


def get_active_intention(profile_email: str, domain: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM brain2_intentions WHERE profile_email = ? AND domain = ? AND status = 'active' "
            'ORDER BY created_at DESC LIMIT 1',
            (profile_email, domain),
        ).fetchone()
    return dict(row) if row else None


def supersede_intention(intention_id: str, profile_email: str, new_target_minutes: int) -> dict[str, Any]:
    """A renegotiated target supersedes the old intention rather than mutating

    it — the original target, and the fact it didn't work, stays visible in
    history (same pattern as `profile_store.accept`'s supersede).
    """
    old = get_intention(intention_id, profile_email)
    if old is None:
        raise KeyError(f'Unknown intention {intention_id} for {profile_email}')
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            'UPDATE brain2_intentions SET status = ? WHERE intention_id = ? AND profile_email = ?',
            (SUPERSEDED, intention_id, profile_email),
        )
    return create_intention(profile_email, old['domain'], old['title'], new_target_minutes, supersedes_intention_id=intention_id)


def log_checkin(intention_id: str, profile_email: str, checkin_date: str, minutes: int, note: str | None = None) -> dict[str, Any]:
    """Ground truth for one calendar day. Logging twice in a day accumulates

    minutes rather than overwriting — never lossy, same rule as US-004's
    `goal_logs`.
    """
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            'INSERT INTO brain2_checkins (intention_id, profile_email, checkin_date, actual_minutes, note, created_at) '
            'VALUES (?, ?, ?, ?, ?, ?) '
            'ON CONFLICT(intention_id, checkin_date) DO UPDATE SET '
            'actual_minutes = actual_minutes + excluded.actual_minutes, '
            'note = COALESCE(excluded.note, brain2_checkins.note)',
            (intention_id, profile_email, checkin_date, minutes, note, now),
        )
        row = conn.execute(
            'SELECT * FROM brain2_checkins WHERE intention_id = ? AND checkin_date = ?',
            (intention_id, checkin_date),
        ).fetchone()
    assert row is not None
    return dict(row)


def list_checkins(intention_id: str, profile_email: str, limit_days: int = STREAK_LOOKBACK_DAYS) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            'SELECT * FROM brain2_checkins WHERE intention_id = ? AND profile_email = ? '
            'ORDER BY checkin_date DESC LIMIT ?',
            (intention_id, profile_email, limit_days),
        ).fetchall()
    return [dict(row) for row in reversed(rows)]


def shortfall_streak(checkins: list[dict[str, Any]], target_minutes: int) -> int:
    """Consecutive calendar days, walking backward from the most recent logged

    day, that fell short of target. A day that met/exceeded target, or a
    calendar gap with no log at all, stops the count — this only reasons
    about days it actually has data for (no background scheduler assumption
    about unlogged days).
    """
    if not checkins:
        return 0
    by_date = {row['checkin_date']: row['actual_minutes'] for row in checkins}
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
