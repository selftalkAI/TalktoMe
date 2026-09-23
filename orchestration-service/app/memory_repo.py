from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from .db import get_connection, init_db

init_db()

# Memory lifecycle statuses (FSD §11.1). Only ACTIVE memories are ever
# eligible for ordinary retrieval; the rest are excluded, not gone.
CANDIDATE = 'candidate'
ACTIVE = 'active'
REQUIRES_CONFIRMATION = 'requires_confirmation'
SUPPRESSED = 'suppressed'
SUPERSEDED = 'superseded'
DELETED = 'deleted'

VALID_TYPES = {
    'fact', 'preference', 'goal', 'relationship', 'event',
    'routine', 'constraint', 'project_context', 'user_instruction',
}
VALID_SENSITIVITY_TIERS = {'T0', 'T1', 'T2', 'T3'}


def _new_id() -> str:
    return f'mem_{uuid.uuid4().hex[:12]}'


def create_memory(
    profile_email: str,
    memory_type: str,
    content: str,
    explicitness: str,
    confidence: float,
    sensitivity_tier: str,
    status: str,
    rationale_code: str | None = None,
    source_type: str | None = None,
    source_id: str | None = None,
    supersedes_id: str | None = None,
) -> dict[str, Any]:
    memory_id = _new_id()
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            'INSERT INTO memories (memory_id, profile_email, type, content, explicitness, '
            'confidence, sensitivity_tier, status, rationale_code, source_type, source_id, '
            'supersedes_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (
                memory_id, profile_email, memory_type, content, explicitness, confidence,
                sensitivity_tier, status, rationale_code, source_type, source_id, supersedes_id,
                now, now,
            ),
        )
    memory = get_memory(memory_id, profile_email)
    assert memory is not None  # just inserted it
    return memory


def get_memory(memory_id: str, profile_email: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            'SELECT * FROM memories WHERE memory_id = ? AND profile_email = ?',
            (memory_id, profile_email),
        ).fetchone()
    return dict(row) if row else None


def list_memories(
    profile_email: str, status: str | None = ACTIVE, memory_type: str | None = None
) -> list[dict[str, Any]]:
    query = 'SELECT * FROM memories WHERE profile_email = ?'
    params: list[Any] = [profile_email]
    if status is not None:
        query += ' AND status = ?'
        params.append(status)
    if memory_type is not None:
        query += ' AND type = ?'
        params.append(memory_type)
    query += ' ORDER BY created_at DESC'
    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def find_duplicate(profile_email: str, memory_type: str, content: str) -> dict[str, Any] | None:
    """Exact-match dedup against this profile's active memories of the same type.

    MVP dedup is intentionally a simple normalized-text match, not semantic
    merging — TDD §5.3 warns that semantic similarity must not independently
    merge materially different facts, so a stricter check is the safer default
    until real conflict detection is designed.
    """
    normalized = content.strip().lower()
    for row in list_memories(profile_email, status=ACTIVE, memory_type=memory_type):
        if row['content'].strip().lower() == normalized:
            return row
    return None


def _set_status(memory_id: str, profile_email: str, status: str) -> dict[str, Any] | None:
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            'UPDATE memories SET status = ?, updated_at = ? WHERE memory_id = ? AND profile_email = ?',
            (status, now, memory_id, profile_email),
        )
    return get_memory(memory_id, profile_email)


def confirm_memory(memory_id: str, profile_email: str) -> dict[str, Any] | None:
    """A REQUIRES_CONFIRMATION candidate becomes ACTIVE once the user confirms it."""
    return _set_status(memory_id, profile_email, ACTIVE)


def suppress_memory(memory_id: str, profile_email: str) -> dict[str, Any] | None:
    return _set_status(memory_id, profile_email, SUPPRESSED)


def delete_memory(memory_id: str, profile_email: str) -> dict[str, Any] | None:
    return _set_status(memory_id, profile_email, DELETED)


def correct_memory(memory_id: str, profile_email: str, new_content: str) -> dict[str, Any]:
    """Supersedes the old memory rather than overwriting it — history stays

    intact and auditable; only ordinary retrieval moves to the new record
    (ADD §6 driver: a correction must affect future retrieval, not erase the past).
    """
    old = get_memory(memory_id, profile_email)
    if old is None:
        raise KeyError(f'Unknown memory {memory_id} for {profile_email}')
    _set_status(memory_id, profile_email, SUPERSEDED)
    return create_memory(
        profile_email=profile_email,
        memory_type=old['type'],
        content=new_content,
        explicitness='explicit',
        confidence=1.0,
        sensitivity_tier=old['sensitivity_tier'],
        status=ACTIVE,
        rationale_code='USER_CORRECTION',
        source_type='correction',
        source_id=memory_id,
        supersedes_id=memory_id,
    )
