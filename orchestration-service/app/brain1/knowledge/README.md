# Brain 1 principle cards (Base knowledge)

Each card is one piece of expert knowledge from the book library in `Docs/ASSETS/BOOKS/`
(Building_Brain1.md §9.2, ADD ADR-020): what the principle is, when it applies, how Brain 2
should use it, when NOT to use it, and where it comes from.

- `review: draft` — written from the books, **not yet approved by the founder**. Draft cards are
  used, and every reply records which cards it used, so a bad card is easy to trace.
  Change to `review: approved` once checked, or delete the card.
- `use_when` keys match Brain 2's Understand step (`intents`, `change_talk`, `did_it_today`,
  `feelings`, `words`) and the area of life (`domains`). A card is chosen when enough match.
- `avoid_when` always wins (e.g. `reason_words: [sick]` — rest is the right call when ill).
- New cards: write them by hand, or draft them with `scripts/distill_principles.py` and review.
