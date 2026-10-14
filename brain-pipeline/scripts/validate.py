"""Checks Brain 2's files against the schema before the next stage trusts them.

Usage:
  python validate.py draft <user>      # Stage 2 output: brain2/<user>/draft/ins-*.md
  python validate.py final <user>      # Stage 3 output: brain2/<user>/ins-*.md + profile/*.md

Insight file (one distinct thing Brain 1 actually said/showed):
  ---
  id: ins-<user>-0007
  domain: learning                # key area or custom
  type: goal                      # one of the app's memory types
  title: Wants to finish the Flow book by November
  explicitness: explicit          # explicit = they said it; inferred = pattern across evidence
  confidence: 0.9                 # 0..1
  sensitivity_tier: T1            # T0..T3
  evidence:
    - source: moments-2026-10__moments__app.txt
      ref: mom_0012                # record id, "page 3", or "line 40"
      quote: "I want to be done with Flow before November"
  summary: ""                      # draft: may be empty; final: 2-3 sentences
  tags: []                         # final: 3-8 lowercase-hyphenated
  related: []                      # final: other insight ids
  ---
  Free-text notes (optional).

Profile entry (profile/<domain>.md): front matter `domain`, `insight_ids`,
`sensitivity_tier`; body = the proposed Profile text for that domain.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from _common import MEMORY_TYPES, SENSITIVITY_TIERS, brain2_dir, parse_front_matter, sources_dir

TAG_RE = re.compile(r'^[a-z0-9]+(-[a-z0-9]+)*$')
ID_RE = re.compile(r'^ins-[a-z0-9-]+-\d{4}$')


def check_insight(path: Path, user: str, final: bool, known_ids: set[str]) -> list[str]:
    fm, _ = parse_front_matter(path.read_text(encoding='utf-8'))
    errs: list[str] = []
    need = ('id', 'domain', 'type', 'title', 'explicitness', 'confidence', 'sensitivity_tier', 'evidence')
    for key in need:
        if fm.get(key) in (None, '', []):
            errs.append(f'missing {key}')
    if errs:
        return errs
    if not ID_RE.match(str(fm['id'])) or path.stem != fm['id']:
        errs.append(f"id {fm['id']!r} must look like ins-{user}-0001 and match the filename")
    if fm['type'] not in MEMORY_TYPES:
        errs.append(f"type {fm['type']!r} not in {sorted(MEMORY_TYPES)}")
    if fm['explicitness'] not in ('explicit', 'inferred'):
        errs.append('explicitness must be explicit|inferred')
    if not isinstance(fm['confidence'], (int, float)) or not 0 <= fm['confidence'] <= 1:
        errs.append('confidence must be a number 0..1')
    if fm['sensitivity_tier'] not in SENSITIVITY_TIERS:
        errs.append('sensitivity_tier must be T0..T3')
    for ev in fm['evidence'] if isinstance(fm['evidence'], list) else []:
        if not isinstance(ev, dict) or not ev.get('source') or not ev.get('quote'):
            errs.append('every evidence item needs source + quote')
        elif not (sources_dir(user) / ev['source']).exists():
            errs.append(f"evidence source not found: {ev['source']}")
        elif len(str(ev['quote']).split()) > 40:
            errs.append(f"evidence quote over 40 words in {ev['source']}")
    if final:
        if not str(fm.get('summary') or '').strip():
            errs.append('final insight needs a summary')
        tags = fm.get('tags') or []
        if not 3 <= len(tags) <= 8 or not all(TAG_RE.match(str(t)) for t in tags):
            errs.append('final insight needs 3-8 lowercase-hyphenated tags')
        for rid in fm.get('related') or []:
            if rid not in known_ids:
                errs.append(f'related id {rid} does not exist')
    return errs


def check_profile(path: Path, known_ids: set[str]) -> list[str]:
    fm, body = parse_front_matter(path.read_text(encoding='utf-8'))
    errs = []
    if fm.get('domain') != path.stem:
        errs.append('front matter domain must match the filename')
    ids = fm.get('insight_ids') or []
    if not ids:
        errs.append('insight_ids is empty — a Profile entry must be grounded in at least one insight')
    errs += [f'unknown insight id {i}' for i in ids if i not in known_ids]
    if fm.get('sensitivity_tier') not in SENSITIVITY_TIERS:
        errs.append('sensitivity_tier must be T0..T3')
    if len(body.strip()) < 40:
        errs.append('body is empty or too short')
    return errs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('which', choices=['draft', 'final'])
    parser.add_argument('user')
    args = parser.parse_args()

    root = brain2_dir(args.user) / ('draft' if args.which == 'draft' else '')
    files = sorted(root.glob('ins-*.md'))
    known = {p.stem for p in files}
    failures = 0
    for p in files:
        for e in check_insight(p, args.user, args.which == 'final', known):
            print(f'{p.name}: {e}'); failures += 1
    if args.which == 'final':
        for p in sorted((brain2_dir(args.user) / 'profile').glob('*.md')):
            for e in check_profile(p, known):
                print(f'profile/{p.name}: {e}'); failures += 1
    print(f'{args.which}: {len(files)} insight files checked, {failures} problems')
    sys.exit(1 if failures else 0)


if __name__ == '__main__':
    main()
