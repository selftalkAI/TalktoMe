from __future__ import annotations

import logging
from typing import Any

from .. import memory_repo
from . import episodes, learning, patterns, profile

logger = logging.getLogger(__name__)

# Brain 1's Reflective mode (Building_Brain1.md §14.3) — runs nightly from the
# scheduler, or on demand. Looks back across conversations and consolidates
# what the Learned layer has seen into durable "what works for them" memories
# (type `learned_strategy`), so the person can see them in their mirror view
# and correct or forget them like any memory. Each strategy is keyed (e.g.
# `card:AH-two-minute-rule`) and superseded — never silently overwritten —
# when the evidence changes. Then saves a new profile version if anything
# changed. Never writes a fact about their life; only how Brain 2 can help.

SOURCE_TYPE = 'brain1_reflection'


def run_for_profile(profile_email: str) -> dict[str, Any]:
    try:
        return _reflect(profile_email)
    except Exception:  # noqa: BLE001 - one person's reflection must never stop the nightly cycle
        logger.exception('Brain 1 Reflector failed for %s', profile_email)
        return {'strategies': [], 'retired': [], 'episodes': [], 'patterns': [], 'profile_version': None}


def _reflect(profile_email: str) -> dict[str, Any]:
    episodes_written = episodes.consolidate_finished(profile_email)
    patterns_found = patterns.detect(profile_email)
    w = learning.weights(profile_email)
    good, bad = learning.preferred(profile_email, w), learning.avoided(profile_email, w)

    wanted: dict[str, tuple[str, float]] = {}
    for kind in ('cards', 'voices', 'stances'):
        for key in good[kind] | bad[kind]:
            summary = w[kind][key]
            verdict = 'tends to help them' if key in good[kind] else 'tends not to land with them'
            content = f'{learning.describe(kind, key)} {verdict} ({learning.evidence(summary)}).'
            wanted[f'{kind[:-1]}:{key}'] = (content[0].upper() + content[1:], _confidence(summary['n']))

    existing = {
        m['source_id']: m
        for m in memory_repo.list_memories(profile_email, memory_type='learned_strategy')
        if m.get('source_type') == SOURCE_TYPE
    }
    written, retired = [], []
    for key, (content, confidence) in wanted.items():
        old = existing.get(key)
        if old and old['content'] == content:
            continue
        if old:
            memory_repo.suppress_memory(old['memory_id'], profile_email)
        memory_repo.create_memory(
            profile_email=profile_email, memory_type='learned_strategy', content=content, explicitness='inferred',
            confidence=confidence, sensitivity_tier='T2', status=memory_repo.ACTIVE, rationale_code='LEARNED_FROM_OUTCOMES',
            source_type=SOURCE_TYPE, source_id=key, supersedes_id=old['memory_id'] if old else None,
        )
        written.append(content)
    for key, old in existing.items():
        if key not in wanted:  # the evidence no longer supports it
            memory_repo.suppress_memory(old['memory_id'], profile_email)
            retired.append(old['content'])

    version = profile.save_version(profile_email, profile.build(profile_email), reason='reflection')
    return {'strategies': written, 'retired': retired, 'episodes': [e['content'] for e in episodes_written],
            'patterns': [p['content'] for p in patterns_found],
            'profile_version': version['version'] if version else None}


def _confidence(n: int) -> float:
    """More evidence, more confidence — capped below certainty: it is still an inference."""
    return round(min(0.9, 0.4 + 0.1 * n), 2)
