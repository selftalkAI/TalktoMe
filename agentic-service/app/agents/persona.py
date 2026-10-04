from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

# Brain 2's personas are config, not code (Building_Brain2.md §5.3): a voice
# (how Brain 2 relates to them) and an expertise (what it knows for this
# reply), each a YAML file under prompts/. Brain 1's Persona Selector picks
# the ids; this module turns them into prompt material. Unknown ids fall
# back to the friend voice and general expertise rather than failing a turn.

_PROMPTS = Path(__file__).parent / 'prompts'
DEFAULT_VOICE = 'friend'
DEFAULT_EXPERTISE = 'general'


@lru_cache(maxsize=None)
def voice(voice_id: str | None) -> dict[str, Any]:
    return _load('voices', voice_id, DEFAULT_VOICE)


@lru_cache(maxsize=None)
def expertise(expertise_id: str | None) -> dict[str, Any]:
    return _load('expertise', expertise_id, DEFAULT_EXPERTISE)


def resolve(persona: dict[str, Any] | None) -> tuple[dict[str, Any], dict[str, Any]]:
    persona = persona or {}
    return voice(persona.get('voice')), expertise(persona.get('expertise'))


def expertise_text(exp: dict[str, Any]) -> str:
    """The expertise as prompt text, including what it must not do."""
    parts = [(exp.get('in_words') or '').strip()]
    if exp.get('cannot'):
        parts.append(f"You never give: {', '.join(exp['cannot'])}.")
    if exp.get('always'):
        parts.append(exp['always'].strip())
    return ' '.join(p for p in parts if p)


def examples_text(v: dict[str, Any]) -> str:
    lines = ['EXAMPLES OF YOUR VOICE (other people, other situations — learn the tone, never reuse the words)']
    for ex in v.get('examples') or []:
        lines += [f'Them: "{ex["them"]}"', f'You: "{ex["you"]}"', '']
    return '\n'.join(lines).strip()


def example_replies(v: dict[str, Any]) -> list[str]:
    return [ex['you'] for ex in v.get('examples') or []]


def _load(kind: str, item_id: str | None, default: str) -> dict[str, Any]:
    path = _PROMPTS / kind / f'{item_id}.yaml'
    if not item_id or not path.is_file() or '/' in item_id or '..' in item_id:
        path = _PROMPTS / kind / f'{default}.yaml'
    return yaml.safe_load(path.read_text())
