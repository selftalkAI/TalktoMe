from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from ..db import get_connection, init_db

init_db()

PROPOSED = 'proposed'
ACCEPTED = 'accepted'
SUPERSEDED = 'superseded'
REJECTED = 'rejected'


def _new_id() -> str:
    return f'profile_entry_{uuid.uuid4().hex[:12]}'


def _row_to_dict(row: Any) -> dict[str, Any]:
    data = dict(row)
    data['source_memory_ids'] = json.loads(data['source_memory_ids'] or '[]')
    return data


def propose(
    profile_email: str,
    domain: str,
    content: str,
    source_memory_ids: list[str],
) -> dict[str, Any]:
    """Brain 2 drafts a refinement. This is a disclosure, not a write — the row

    lands as `proposed`, never touching whatever is currently `accepted` for
    this domain, and it never will unless `accept()` is called on this exact
    row (ADR-014, `12_Agentic AI Architecture` Boundaries).
    """
    current = get_accepted(profile_email, domain)
    version = (current['version'] + 1) if current else 1

    entry_id = _new_id()
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            'INSERT INTO profile_entries (profile_entry_id, profile_email, domain, version, content, '
            'source_memory_ids, status, proposed_at, accepted_at, superseded_by) '
            'VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL)',
            (entry_id, profile_email, domain, version, content, json.dumps(source_memory_ids), PROPOSED, now),
        )
    entry = get_entry(entry_id, profile_email)
    assert entry is not None
    return entry


def accept(profile_entry_id: str, profile_email: str) -> dict[str, Any]:
    """The only path by which a Profile entry ever becomes `accepted`. Brain 1's

    explicit call, never inferred from conversation and never automatic —
    whether this proposal came from a user-triggered run or the Scheduler.
    Supersedes whatever was previously accepted for this domain; that prior
    row is kept, not deleted (ADR-014).
    """
    entry = get_entry(profile_entry_id, profile_email)
    if entry is None:
        raise KeyError(f'Unknown profile entry {profile_entry_id} for {profile_email}')
    if entry['status'] != PROPOSED:
        raise ValueError(f"Entry {profile_entry_id} is '{entry['status']}', not proposed — nothing to accept")

    now = datetime.now(timezone.utc).isoformat()
    previous = get_accepted(entry['profile_email'], entry['domain'])
    with get_connection() as conn:
        if previous is not None:
            conn.execute(
                'UPDATE profile_entries SET status = ?, superseded_by = ? WHERE profile_entry_id = ?',
                (SUPERSEDED, profile_entry_id, previous['profile_entry_id']),
            )
        conn.execute(
            'UPDATE profile_entries SET status = ?, accepted_at = ? WHERE profile_entry_id = ?',
            (ACCEPTED, now, profile_entry_id),
        )
    updated = get_entry(profile_entry_id, profile_email)
    assert updated is not None
    return updated


def reject(profile_entry_id: str, profile_email: str) -> dict[str, Any]:
    """Nothing is superseded. The proposal is simply marked rejected and the

    currently accepted entry (if any) is untouched.
    """
    entry = get_entry(profile_entry_id, profile_email)
    if entry is None:
        raise KeyError(f'Unknown profile entry {profile_entry_id} for {profile_email}')
    with get_connection() as conn:
        conn.execute(
            'UPDATE profile_entries SET status = ? WHERE profile_entry_id = ?',
            (REJECTED, profile_entry_id),
        )
    updated = get_entry(profile_entry_id, profile_email)
    assert updated is not None
    return updated


def get_entry(profile_entry_id: str, profile_email: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            'SELECT * FROM profile_entries WHERE profile_entry_id = ? AND profile_email = ?',
            (profile_entry_id, profile_email),
        ).fetchone()
    return _row_to_dict(row) if row else None


def get_accepted(profile_email: str, domain: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM profile_entries WHERE profile_email = ? AND domain = ? AND status = 'accepted'",
            (profile_email, domain),
        ).fetchone()
    return _row_to_dict(row) if row else None


def history(profile_email: str, domain: str) -> list[dict[str, Any]]:
    """Every version ever proposed for this domain, oldest first — nothing is

    ever deleted from this list, only superseded or rejected in place.
    """
    with get_connection() as conn:
        rows = conn.execute(
            'SELECT * FROM profile_entries WHERE profile_email = ? AND domain = ? ORDER BY version ASC, proposed_at ASC',
            (profile_email, domain),
        ).fetchall()
    return [_row_to_dict(row) for row in rows]
