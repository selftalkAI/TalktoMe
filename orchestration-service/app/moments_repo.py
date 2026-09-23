from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .db import get_connection, init_db

init_db()


def create_moment(profile_email: str, source: str, content: str, mood: str | None, photo_data_url: str | None) -> dict[str, Any]:
    moment_id = f'mom_{_count_all_moments() + 1:04d}'
    created_at = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            'INSERT INTO moments (id, created_at, source, content, mood, photo_data_url, reflection, profile_email) '
            'VALUES (?, ?, ?, ?, ?, ?, NULL, ?)',
            (moment_id, created_at, source, content, mood, photo_data_url, profile_email),
        )
    return {
        'id': moment_id,
        'created_at': created_at,
        'source': source,
        'content': content,
        'mood': mood,
        'photo_data_url': photo_data_url,
        'reflection': None,
    }


def list_moments(profile_email: str) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            'SELECT * FROM moments WHERE profile_email = ? ORDER BY created_at DESC',
            (profile_email,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_moment(moment_id: str, profile_email: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            'SELECT * FROM moments WHERE id = ? AND profile_email = ?',
            (moment_id, profile_email),
        ).fetchone()
    return dict(row) if row else None


def set_reflection(moment_id: str, profile_email: str, reflection: str) -> None:
    with get_connection() as conn:
        conn.execute(
            'UPDATE moments SET reflection = ? WHERE id = ? AND profile_email = ?',
            (reflection, moment_id, profile_email),
        )


def _count_all_moments() -> int:
    # IDs are globally unique across every profile, just so two people can
    # never collide on the same mom_XXXX id.
    with get_connection() as conn:
        (count,) = conn.execute('SELECT COUNT(*) FROM moments').fetchone()
    return count
