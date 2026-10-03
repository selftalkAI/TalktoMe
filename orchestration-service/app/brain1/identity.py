from __future__ import annotations

from typing import Any

import bcrypt

from .. import profiles_repo
from ..brain2 import scheduler as brain2_scheduler


def create(
    email: str,
    full_name: str,
    password: str,
    dob: str | None,
    location: str | None,
    interests: list[str],
    other_interests: str | None,
    photo_data_url: str | None,
    quote: str | None,
) -> dict[str, Any]:
    """Creates Brain 1's own record — the one and only place a plaintext

    password is ever handled; it's hashed here and never stored, logged, or
    passed any further as plaintext (`_hash_password`, bcrypt).

    The first time this email is ever seen, also runs Brain 2's recheck pass
    for them immediately (`brain2_scheduler.run_for_profile`) — it will
    correctly find nothing to propose yet (a brand-new Brain 1 has no
    memories or intentions), but it proves the architecture is wired from
    creation, rather than fabricating placeholder Profile content that
    nobody actually said (which every other part of this system refuses to
    do — see the grounding rules in `agentic-service/app/agents/`).
    """
    is_new = profiles_repo.get_profile(email) is None

    profile = profiles_repo.upsert_profile(
        email=email,
        full_name=full_name,
        password_hash=_hash_password(password),
        dob=dob,
        location=location,
        interests=interests,
        other_interests=other_interests,
        photo_data_url=photo_data_url,
        quote=quote,
    )

    if is_new:
        brain2_scheduler.run_for_profile(email)

    return profile


def authenticate(email: str, password: str) -> dict[str, Any] | None:
    """Returns the profile if `password` matches what's on file, else None —

    covering both a wrong password and a profile with no password set at all
    (e.g. one that predates this check). A wrong password is an ordinary,
    expected outcome here, never an exception.
    """
    profile = profiles_repo.get_profile(email)
    stored_hash = profile.get('password_hash') if profile else None
    if profile is None or not stored_hash:
        return None
    if not bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8')):
        return None
    return profile


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def get(email: str) -> dict[str, Any] | None:
    return profiles_repo.get_profile(email)


def list_all() -> list[dict[str, Any]]:
    return profiles_repo.list_profiles()
