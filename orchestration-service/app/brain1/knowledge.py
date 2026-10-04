from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from .. import rag_manager

# Brain 1's Base knowledge (Building_Brain1.md §9; ADD ADR-020): principle
# cards distilled from the book library (knowledge/*.yaml), plus similarity
# search over the books themselves. Brain 1 picks the cards that fit this
# moment — deterministically, from Brain 2's reading of the message — and
# hands them to Brain 2 as options, never instructions. Every reply records
# which cards it used, so the Learned layer can later weigh them per person.

KNOWLEDGE_DIR = Path(__file__).parent / 'knowledge'
MAX_CARDS = 2
MIN_SCORE = 2


@lru_cache(maxsize=1)
def cards() -> tuple[dict[str, Any], ...]:
    loaded: list[dict[str, Any]] = []
    for path in sorted(KNOWLEDGE_DIR.glob('*.yaml')):
        data = yaml.safe_load(path.read_text()) or {}
        for card in data.get('cards') or []:
            loaded.append({**card, 'core': data.get('core')})
    return tuple(loaded)


def select(
    reading: dict[str, Any], message: str, domain: str, safety_level: str = 'ok', limit: int = MAX_CARDS
) -> list[dict[str, Any]]:
    """The cards that fit this moment, best first. A card's `avoid_when`
    always wins; a `did_it_today` condition must match exactly."""
    text = (message or '').lower()
    reason = f"{reading.get('reason_given') or ''} {text}".lower()
    feeling = (reading.get('feeling') or '').lower()

    scored: list[tuple[int, int, dict[str, Any]]] = []
    for order, card in enumerate(cards()):
        when, avoid = card.get('use_when') or {}, card.get('avoid_when') or {}
        if safety_level in (avoid.get('safety') or []):
            continue
        if any(_has_word(reason, w) for w in avoid.get('reason_words') or []):
            continue
        if any(f in feeling for f in avoid.get('feelings') or []):
            continue
        if 'did_it_today' in when and reading.get('did_it_today') is not when['did_it_today']:
            continue

        score = 0
        if reading.get('intent') in (when.get('intents') or []):
            score += 2
        if reading.get('change_talk') in (when.get('change_talk') or []):
            score += 2
        if feeling and any(f in feeling for f in when.get('feelings') or []):
            score += 2
        if any(_has_word(text, w) for w in when.get('words') or []):
            score += 3  # their exact words are a more specific signal than a general intent
        if (domain or '').lower() in (when.get('domains') or []):
            score += 1
        if score >= MIN_SCORE:
            scored.append((score, -order, card))

    scored.sort(key=lambda s: (s[0], s[1]), reverse=True)
    return [card for _, _, card in scored[:limit]]


def as_text(selected: list[dict[str, Any]]) -> str:
    """Cards as Context Pack text — the principle, how to use it, and the
    source, without internal ids."""
    lines = []
    for card in selected:
        src = card.get('source') or {}
        lines.append(f"- {card['principle']} How to use it here: {card['offer']} ({src.get('book')})")
    return '\n'.join(lines)


def search_books(query: str, top_k: int = 3, book: str | None = None) -> list[dict[str, Any]]:
    """Similarity-only search over the ingested book library."""
    return rag_manager.search_books(query, top_k=top_k, book=book)


def _has_word(text: str, phrase: str) -> bool:
    return re.search(r'(?<![a-z])' + re.escape(phrase.lower()) + r'(?![a-z])', text) is not None
