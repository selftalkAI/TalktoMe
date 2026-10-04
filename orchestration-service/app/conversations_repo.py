from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from .db import get_connection

# The conversation (ADD §25 Conversation domain): every message and Brain 2
# reply, per person and life area. Brain 1 summarises finished sessions into
# episodic memory (`brain1/episodes.py`) and delivers proactive check-ins here.

SESSION_GAP_MINUTES = 60


def append(profile_email: str, domain: str, role: str, content: str, *, run_id: str | None = None,
           proactive: bool = False) -> dict[str, Any]:
    row = {
        'turn_id': str(uuid.uuid4()), 'profile_email': profile_email, 'domain': domain, 'role': role,
        'content': content, 'run_id': run_id, 'proactive': int(proactive),
        'created_at': datetime.now(timezone.utc).isoformat(),
    }
    with get_connection() as conn:
        conn.execute(
            'INSERT INTO conversation_turns (turn_id, profile_email, domain, role, content, run_id, proactive, created_at) '
            'VALUES (:turn_id, :profile_email, :domain, :role, :content, :run_id, :proactive, :created_at)',
            row,
        )
    return row


def history(profile_email: str, domain: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    """Most recent turns, oldest first."""
    query = 'SELECT * FROM conversation_turns WHERE profile_email = ?'
    params: list[Any] = [profile_email]
    if domain:
        query += ' AND domain = ?'
        params.append(domain)
    query += ' ORDER BY created_at DESC LIMIT ?'
    params.append(limit)
    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in reversed(rows)]


def current_session(profile_email: str, domain: str, gap_minutes: int = SESSION_GAP_MINUTES) -> list[dict[str, Any]]:
    """The turns of the ongoing session: everything since the last gap longer
    than `gap_minutes`, oldest first."""
    turns = history(profile_email, domain, limit=40)
    session: list[dict[str, Any]] = []
    for turn in reversed(turns):
        if session and _minutes_between(turn['created_at'], session[-1]['created_at']) > gap_minutes:
            break
        session.append(turn)
    return list(reversed(session))


def as_messages(turns: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [{'role': t['role'], 'content': t['content']} for t in turns]


def unsummarised(profile_email: str, domain: str) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            'SELECT * FROM conversation_turns WHERE profile_email = ? AND domain = ? AND episode_id IS NULL ORDER BY created_at',
            (profile_email, domain),
        ).fetchall()
    return [dict(r) for r in rows]


def mark_summarised(turn_ids: list[str], episode_id: str) -> None:
    with get_connection() as conn:
        conn.executemany('UPDATE conversation_turns SET episode_id = ? WHERE turn_id = ?', [(episode_id, t) for t in turn_ids])


def domains_with_unsummarised(profile_email: str) -> list[str]:
    with get_connection() as conn:
        rows = conn.execute(
            'SELECT DISTINCT domain FROM conversation_turns WHERE profile_email = ? AND episode_id IS NULL', (profile_email,)
        ).fetchall()
    return [r['domain'] for r in rows]


def domains_awaiting_reply(profile_email: str) -> list[dict[str, Any]]:
    """Areas where Brain 2 spoke last: `{domain, last_turn, proactive_since_reply}`."""
    with get_connection() as conn:
        domains = [r['domain'] for r in conn.execute(
            'SELECT DISTINCT domain FROM conversation_turns WHERE profile_email = ?', (profile_email,)).fetchall()]
    awaiting = []
    for domain in domains:
        turns = history(profile_email, domain, limit=10)
        if not turns or turns[-1]['role'] != 'assistant':
            continue
        since_reply = []
        for t in reversed(turns):
            if t['role'] == 'user':
                break
            since_reply.append(t)
        awaiting.append({'domain': domain, 'last_turn': turns[-1], 'proactive_since_reply': sum(t['proactive'] for t in since_reply)})
    return awaiting


def proactive_count_since(profile_email: str, since: datetime) -> int:
    with get_connection() as conn:
        row = conn.execute(
            'SELECT COUNT(*) AS n FROM conversation_turns WHERE profile_email = ? AND proactive = 1 AND created_at >= ?',
            (profile_email, since.isoformat()),
        ).fetchone()
    return int(row['n'])


def minutes_since(timestamp: str) -> float:
    return (datetime.now(timezone.utc) - datetime.fromisoformat(timestamp)).total_seconds() / 60


def _minutes_between(earlier: str, later: str) -> float:
    return (datetime.fromisoformat(later) - datetime.fromisoformat(earlier)).total_seconds() / 60


def hours_ago(hours: float) -> datetime:
    return datetime.now(timezone.utc) - timedelta(hours=hours)
