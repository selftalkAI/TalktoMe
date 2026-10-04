from __future__ import annotations

from datetime import datetime
from typing import Any

from .. import profiles_repo
from ..brain2 import profile_store
from . import consent, here_now, patterns, profile

# Brain 1's Context Pack (Building_Brain1.md §8.6) — what Brain 2 is told
# about the person before every reply. Brain 2 never sees the raw profile:
# this compiles only what matters for this moment, in plain language, with a
# fixed set of sections Brain 2's prompts expect.
#
# Privacy filter: T3 fields (health, finances) never enter the pack — there is
# no per-category opt-in yet (FSD BR-018) — nor do system-owned fields.

MAX_WHO = 8
MAX_LIFE_FACTS = 10
MAX_STORY = 3
MAX_UNKNOWNS = 2
MAX_CHECKINS = 7

_LIFE_SECTIONS = ('tastes', 'life_map', 'inner_world', 'body')
_HOOK_SECTIONS = ('tastes',)  # what they love and their rituals — not their struggles


def compile(  # noqa: A001 - the pack is "compiled", per the spec's vocabulary
    profile_email: str,
    domain: str,
    *,
    intention: dict[str, Any] | None = None,
    checkins: list[dict[str, Any]] | None = None,
    streak: int | None = None,
    support_message: str = '',
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    """Returns the pack: `first_name` plus the sections Brain 2's prompts use
    (`who`, `goal`, `today`, `loves`, `story`, `works`, `hooks`, `unknowns`),
    `allowed_text` (everything a reply may draw numbers and days from) and
    `blocked_terms` (privacy items a reply must never mention)."""
    person = profiles_repo.get_profile(profile_email) or {}
    first_name = ((person.get('full_name') or '').split() or ['there'])[0]
    built = profile.build(profile_email)
    allowed = consent.allowed_categories(profile_email)
    sections = {key: [f for f in fields if _shareable(f, allowed)] for key, fields in built['sections'].items()}
    now = here_now.compute(person.get('location'), now_utc)

    pack = {
        'first_name': first_name,
        'who': _lines(sections['identity'] + sections['people'] + _communication(sections), MAX_WHO),
        'goal': _goal(intention, checkins or [], streak),
        'today': here_now.describe(now),
        'loves': _lines(_relevant_to(domain, [f for s in _LIFE_SECTIONS for f in sections[s]]), MAX_LIFE_FACTS),
        'story': _story(profile_email, domain, sections['story'], support_message),
        'works': _lines(sections['what_works'], MAX_LIFE_FACTS),
        'hooks': _hooks(now, [f for s in _HOOK_SECTIONS for f in sections[s]]),
        'unknowns': '\n'.join(filter(None, [
            _lines(sections['open_questions'], MAX_UNKNOWNS, prefix='Ask only if it fits naturally: '),
            _pattern_to_check(profile_email),
        ])),
    }
    pack['allowed_text'] = '\n'.join(v for k, v in pack.items() if k != 'first_name')
    pack['blocked_terms'] = []
    return pack


def _pattern_to_check(profile_email: str) -> str:
    """One pattern Brain 1 noticed but she hasn't confirmed — offered as a
    gentle question, never stated as fact (Building_Brain1.md Scenario 8)."""
    waiting = patterns.pending(profile_email)
    if not waiting:
        return ''
    return f"- Something you may have noticed across your talks (check gently whether it rings true, only if it fits): {waiting[0]['content']}"


def _shareable(field: dict[str, Any], allowed: set[str]) -> bool:
    """T3 only with her consent for that category; system-owned fields never."""
    return consent.shareable(field, allowed) and not str(field.get('area') or '').startswith('brain1_')


def _lines(fields: list[dict[str, Any]], limit: int, prefix: str = '') -> str:
    seen: list[str] = []
    for f in fields:
        if f['value'] not in seen:
            seen.append(f['value'])
    return '\n'.join(f'- {prefix}{v}' for v in seen[:limit])


# Areas whose facts matter to each other (health matters to fitness; a gym routine doesn't matter to a job decision).
_RELATED_AREAS = (
    {'fitness', 'gym', 'exercise', 'health', 'sleep', 'nutrition', 'body', 'energy', 'running'},
    {'cooking', 'food', 'nutrition', 'recipes'},
    {'work', 'career', 'job'},
    {'money', 'finance', 'finances', 'budget', 'spending'},
    {'family', 'kids', 'children', 'parenting', 'partner', 'relationships'},
    {'feelings', 'emotion', 'emotions', 'stress', 'mood', 'mental'},
)


def _relevant_to(domain: str, fields: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Facts from this area, then related areas, then general ones — never
    facts from an unrelated area."""
    area = (domain or '').lower()
    related = set().union(*(group for group in _RELATED_AREAS if area in group)) - {area}
    general = (None, '', 'general')
    return ([f for f in fields if (f.get('area') or '').lower() == area]
            + [f for f in fields if (f.get('area') or '').lower() in related]
            + [f for f in fields if f.get('area') in general])


def _communication(sections: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    # The voice preference itself is Brain 1's business (Persona Selector), not a fact to mention.
    return [f for f in sections['communication'] if not f['value'].startswith('Prefers Brain 2 to talk like')]


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


def _story(profile_email: str, domain: str, story_fields: list[dict[str, Any]], support_message: str) -> str:
    lines: list[str] = []
    if support_message.strip():
        lines.append(f'Earlier you offered this support: "{support_message.strip()}" — build on it, don\'t repeat it.')
    accepted = profile_store.get_accepted(profile_email, domain)
    if accepted:
        lines.append(f"What they agreed is true about their {domain}: {accepted['content']}")
    events = [f['value'] for f in story_fields if f.get('source') != 'accepted'][:MAX_STORY]
    lines += [f'- {e}' for e in events]
    return '\n'.join(lines)


def _hooks(now: dict[str, Any], life_fields: list[dict[str, Any]]) -> str:
    """Where the moment meets their life (Building_Brain1.md §8.6): the
    moment plus the things from their life that could connect to it. Brain 2
    decides whether one fits; nothing here is invented."""
    if not life_fields:
        return ''
    moment = f"{now['weekday']} {now['part_of_day']}"
    if now.get('weather'):
        moment += f", {now['weather']['words']}, {now['weather']['temperature_c']}°C"
    things = '; '.join(f['value'].rstrip('.') for f in life_fields[:4])
    return f'The moment: {moment}.\nFrom their life, things that might connect to it: {things}.'
