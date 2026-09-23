from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from .db import get_connection, init_db

init_db()


def _row_to_dict(row: Any) -> dict[str, Any]:
    data = dict(row)
    data['interests'] = json.loads(data['interests'] or '[]')
    return data


def upsert_profile(
    email: str,
    full_name: str,
    dob: str | None,
    location: str | None,
    interests: list[str],
    other_interests: str | None,
    photo_data_url: str | None,
    quote: str | None,
) -> dict[str, Any]:
    """Creates the profile for this email, or overwrites it if one already exists —

    the login flow is 'give your email, get your profile back', so signing up
    again with the same email is expected to just update it, not collide.
    """
    with get_connection() as conn:
        existing = conn.execute('SELECT created_at FROM profiles WHERE email = ?', (email,)).fetchone()
        created_at = existing['created_at'] if existing else datetime.now(timezone.utc).isoformat()
        conn.execute(
            'INSERT INTO profiles (email, full_name, dob, location, interests, other_interests, '
            'photo_data_url, quote, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) '
            'ON CONFLICT(email) DO UPDATE SET '
            'full_name = excluded.full_name, dob = excluded.dob, location = excluded.location, '
            'interests = excluded.interests, other_interests = excluded.other_interests, '
            'photo_data_url = excluded.photo_data_url, quote = excluded.quote',
            (
                email,
                full_name,
                dob,
                location,
                json.dumps(interests),
                other_interests,
                photo_data_url,
                quote,
                created_at,
            ),
        )

    profile = get_profile(email)
    assert profile is not None  # just upserted it
    return profile


def set_understanding(email: str, mood_summary: str, context_notes: str, narrative_focus: str) -> None:
    """Stores what ProfileAgent understood about this person from the conversation —

    every later SmartAgent call (reflect_moment, evolution_narrative, suggest_next_step)
    for this profile pulls this back out and folds it into its own prompt, so the
    understanding actually shapes what gets written from here on.
    """
    with get_connection() as conn:
        conn.execute(
            'UPDATE profiles SET mood_summary = ?, context_notes = ?, narrative_focus = ? WHERE email = ?',
            (mood_summary, context_notes, narrative_focus, email),
        )


def get_profile(email: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute('SELECT * FROM profiles WHERE email = ?', (email,)).fetchone()
    return _row_to_dict(row) if row else None


def list_profiles() -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute('SELECT * FROM profiles ORDER BY created_at DESC').fetchall()
    return [_row_to_dict(row) for row in rows]
