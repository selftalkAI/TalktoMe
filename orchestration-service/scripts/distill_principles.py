"""Drafts new principle cards from one book in the knowledge base, for the
founder to review (Building_Brain1.md §9.2 / build phase 1).

Walks the book's ingested chunks in order, a few at a time, and asks the model
to extract at most one practical, evidence-based principle per window, in the
card format of `app/brain1/knowledge/*.yaml`. Drafts are written to
`app/brain1/knowledge/drafts/<book>.yaml` — a folder Brain 1 never loads. To
use a card: check it against the book, fix it, set `review: approved`, and move
it into the right core's file.

Usage (from orchestration-service/, venv active, Agentic Service running):
    python3 scripts/distill_principles.py --list
    python3 scripts/distill_principles.py --book "atomic habits" [--windows 10] [--window-size 6]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import rag_documents_repo, rag_manager  # noqa: E402
from app.spinal_cord import AgenticServiceClient, AgenticServiceError  # noqa: E402

DRAFTS_DIR = Path(__file__).resolve().parents[1] / 'app' / 'brain1' / 'knowledge' / 'drafts'
SCOPE = rag_manager.KNOWLEDGE_BASE_SCOPE

SYSTEM = (
    'You extract practical principles from a book passage for a personal coaching assistant. '
    'Only extract a principle the passage itself clearly states — never invent one. If the passage '
    'is a story, an index, front matter, or has no clear practical principle, return {"card": null}. '
    'Return JSON only: {"card": null} or {"card": {"principle": one sentence, "offer": how a coach '
    'would use it in one short sentence, "words": [3-6 words a person might say when this applies], '
    '"intents": [any of sharing, asking, progress, setback, venting, pushback], "quote": a short '
    'exact phrase from the passage that supports it}}'
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--book', help='Part of the book title, e.g. "atomic habits"')
    parser.add_argument('--windows', type=int, default=10, help='How many passages to read (each is one model call)')
    parser.add_argument('--window-size', type=int, default=6, help='Chunks per passage')
    parser.add_argument('--list', action='store_true', help='List the books in the knowledge base')
    args = parser.parse_args()

    books = rag_documents_repo.list_documents(SCOPE)
    if args.list or not args.book:
        for doc in books:
            print(f"- {doc['title']}")
        return

    matches = [d for d in books if args.book.lower() in (d.get('title') or '').lower()]
    if not matches:
        sys.exit(f'No book matching {args.book!r}. Use --list.')
    doc = matches[0]
    chunks = rag_documents_repo.list_chunks(doc['document_id'], SCOPE)
    step = max(1, len(chunks) // max(1, args.windows))

    drafts = []
    client = AgenticServiceClient()
    for start in range(0, len(chunks), step)[: args.windows]:
        window = chunks[start : start + args.window_size]
        passage = '\n'.join(c['content'] for c in window)[:6000]
        try:
            response = client.complete(passage, SYSTEM).get('response', '')
        except AgenticServiceError as exc:
            sys.exit(f'Agentic Service unavailable: {exc}')
        card = _parse(response)
        if card and card.get('quote') and _normalise(card['quote']) in _normalise(passage):
            drafts.append(_as_card(doc['title'], start, card, len(drafts)))
            print(f"  + {card['principle']}")
        else:
            print(f'  · chunks {start}-{start + len(window)}: no supported principle')

    DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
    out = DRAFTS_DIR / f"{re.sub(r'[^a-z0-9]+', '_', doc['title'].lower()).strip('_')}.yaml"
    out.write_text(yaml.safe_dump({'core': 'TODO-assign-core', 'cards': drafts}, sort_keys=False, allow_unicode=True))
    print(f'\n{len(drafts)} draft card(s) written to {out} — review each against the book before using it.')


def _parse(response: str) -> dict | None:
    match = re.search(r'\{.*\}', response or '', re.DOTALL)
    if not match:
        return None
    try:
        card = json.loads(match.group(0)).get('card')
    except (json.JSONDecodeError, AttributeError):
        return None
    return card if isinstance(card, dict) and card.get('principle') and card.get('offer') else None


def _normalise(text: str) -> str:
    return re.sub(r'\s+', ' ', text).strip().lower()


def _as_card(title: str, start: int, card: dict, n: int) -> dict:
    """A draft only keeps a principle whose supporting quote really is in the
    passage (checked above) — the cheapest guard against invented content."""
    return {
        'id': f"DRAFT-{re.sub(r'[^A-Z]', '', title.upper())[:4]}-{n + 1}",
        'source': {'book': title, 'chapter': f'around chunk {start} (check the chapter)', 'quote': card['quote']},
        'principle': card['principle'],
        'use_when': {
            'intents': [i for i in card.get('intents') or [] if i in ('sharing', 'asking', 'progress', 'setback', 'venting', 'pushback')],
            'words': [w for w in card.get('words') or [] if isinstance(w, str)][:6],
        },
        'offer': card['offer'],
        'review': 'draft',
    }


if __name__ == '__main__':
    main()
