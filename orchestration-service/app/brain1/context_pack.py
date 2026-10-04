from __future__ import annotations

from datetime import date, datetime
from typing import Any

from .. import memory_repo, profiles_repo

# Brain 1's Context Pack (Building_Brain1.md §8.6) — what Brain 2 is told
# about the person before every reply. This is the STUB compiler (Brain 2
# Phase A): it builds the pack from what exists today — the `profiles` row,
# active memories, and the goal's check-ins. The full compiler (12-section
# profile, Here & Now, episodic memory, hooks, learned strategies) replaces
# it in the Brain 1 Profile stage; the pack's shape stays the same so Brain 2
# never has to change.
#
# Privacy: T3 memories (health, finances) are never included — there is no
# per-category opt-in yet (FSD BR-018), so the safe default is exclusion.

MAX_LIFE_FACTS = 10
MAX_CHECKINS = 7


def compile_stub(
    profile_email: str,
    domain: str,
    *,
    intention: dict[str, Any] | None = None,
    checkins: list[dict[str, Any]] | None = None,
    streak: int | None = None,
    support_message: str = '',
    now: datetime | None = None,
) -> dict[str, Any]:
    """Returns the pack: plain-language sections keyed as Brain 2's Speak
    prompt expects (`first_name`, `who`, `goal`, `today`, `loves`, `story`,
    `works`), plus `allowed_text` (everything a reply may draw numbers from)
    and `blocked_terms` (privacy items a reply must never mention).
    """
    profile = profiles_repo.get_profile(profile_email) or {}
    first_name = ((profile.get('full_name') or '').split() or ['there'])[0]

    pack = {
        'first_name': first_name,
        'who': _who(profile),
        'goal': _goal(intention, checkins or [], streak),
        'today': _today(now or datetime.now()),
        'loves': _life_facts(profile, profile_email, domain),
        'story': f'Earlier you offered this support: "{support_message.strip()}" — build on it, don\'t repeat it.'
        if support_message.strip()
        else '',
        'works': '',
    }
    pack['allowed_text'] = '\n'.join(v for k, v in pack.items() if k != 'first_name')
    pack['blocked_terms'] = []
    return pack


def _who(profile: dict[str, Any]) -> str:
    if not profile:
        return ''
    parts = [profile.get('full_name') or '']
    age = _age(profile.get('dob'))
    if age is not None:
        parts.append(f'{age} years old')
    if profile.get('location'):
        parts.append(f"lives in {profile['location']}")
    lines = [', '.join(p for p in parts if p) + '.']
    if profile.get('quote'):
        lines.append(f'A line they chose for themselves: "{profile["quote"]}"')
    return '\n'.join(lines)


def _goal(intention: dict[str, Any] | None, checkins: list[dict[str, Any]], streak: int | None) -> str:
    if intention is None:
        return ''
    lines = [f"{intention['title']}: aiming for {intention['target_minutes']} minutes a day."]
    recent = sorted(checkins, key=lambda c: c['checkin_date'])[-MAX_CHECKINS:]
    if recent:
        lines.append('Past check-ins (history — not what happened today unless they say so):')
    for c in recent:
        note = f' — they said: "{c["note"]}"' if c.get('note') else ''
        lines.append(f"{c['checkin_date']}: {c['actual_minutes']} min{note}")
    if streak:
        lines.append(f'{streak} days in a row under the target.')
    return '\n'.join(lines)


def _today(now: datetime) -> str:
    return now.strftime('%A, %d %B %Y, %I:%M %p').replace(' 0', ' ')


def _life_facts(profile: dict[str, Any], profile_email: str, domain: str) -> str:
    """What they have told us, this domain first — never T3."""
    memories = [m for m in memory_repo.list_memories(profile_email) if m.get('sensitivity_tier') != 'T3']
    memories.sort(key=lambda m: m.get('domain') != domain)
    facts = [f"- {m['content']}" for m in memories[:MAX_LIFE_FACTS]]

    interests = ', '.join(i.replace('_', ' ') for i in profile.get('interests') or [])
    if interests:
        facts.append(f'- Interests they picked: {interests}')
    if profile.get('other_interests'):
        facts.append(f"- Also into: {profile['other_interests']}")
    return '\n'.join(facts)


def _age(dob: str | None) -> int | None:
    if not dob:
        return None
    try:
        birth = date.fromisoformat(dob[:10])
    except ValueError:
        return None
    today = date.today()
    return today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))
