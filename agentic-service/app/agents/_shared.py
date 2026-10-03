from __future__ import annotations

from datetime import date
from typing import Any

# Small formatting helpers shared by more than one cognitive agent's nodes —
# kept here rather than duplicated, since Thalamus and Sensory Cortex both
# need `profile_lines`/`age_from_dob`, and Prefrontal Cortex needs
# `format_moment`/`narrative_focus_clause` across all three of its
# operations. Nothing here calls a model or holds state.


def profile_lines(payload: dict[str, Any]) -> list[str]:
    full_name = (payload.get('full_name') or '').strip() or 'there'
    location = payload.get('location')
    interests: list[str] = payload.get('interests') or []
    other_interests = payload.get('other_interests')
    quote = payload.get('quote')
    age = age_from_dob(payload.get('dob'))

    lines = [f'Name: {full_name}']
    if age is not None:
        lines.append(f'Age: {age}')
    if location:
        lines.append(f'Location: {location}')
    if interests:
        lines.append(f"Selected interests: {', '.join(interests)}")
    if other_interests:
        lines.append(f'Other interests they typed in: {other_interests}')
    if quote:
        lines.append(f'Personal quote they chose: "{quote}"')
    return lines


def age_from_dob(dob: str | None) -> int | None:
    if not dob:
        return None
    try:
        birth = date.fromisoformat(dob[:10])
    except ValueError:
        return None
    today = date.today()
    return today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))


def format_moment(moment: dict[str, Any]) -> str:
    moment_date = str(moment.get('created_at', ''))[:10]
    mood = moment.get('mood') or 'unspecified'
    return f"- ({moment_date}, felt: {mood}) {moment['content']}"


def narrative_focus_clause(payload: dict[str, Any]) -> str:
    focus = (payload.get('narrative_focus') or '').strip()
    mood_summary = (payload.get('mood_summary') or '').strip()
    context_notes = (payload.get('context_notes') or '').strip()
    if not focus and not mood_summary and not context_notes:
        return ''

    clause = (
        ' Another agent has already gathered some understanding of this person that you '
        'should let shape your tone and emphasis — but keep grounding everything only in '
        'their actual moments above, never invent detail to fit it:'
    )
    if focus:
        clause += f' their reflections should favor this focus: "{focus}";'
    if mood_summary:
        clause += f' how they seemed to be feeling recently: "{mood_summary}";'
    if context_notes:
        clause += f' specific things they mentioned: "{context_notes}";'
    return clause
