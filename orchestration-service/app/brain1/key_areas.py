from __future__ import annotations

from typing import Any

from .. import memory_repo
from ..brain2 import intentions_repo, profile_store

# Brain 1's key areas (ADD §6.1) — the confirmed starter set of Profile
# domains Brain 2 organizes its understanding of a person around. This is a
# default, not a whitelist: ADD §6.1 is explicit that the domain set is
# "extensible per user, not fixed at four" (see `memories.domain` and
# `profile_entries.domain`, both open TEXT columns, not an enum). Every
# Brain 1 has these listed from creation — honestly, as empty/not-started —
# never seeded with fabricated content (see `key_areas_overview`).
KEY_AREAS: tuple[str, ...] = ('skill', 'emotion', 'learning', 'reading')


def key_areas_overview(email: str) -> list[dict[str, Any]]:
    """Every Profile domain relevant to this Brain 1 — the canonical starter

    set (`KEY_AREAS`) plus any custom domain they've actually used — each
    annotated with what Brain 2 currently, honestly knows: an accepted
    entry if one exists, how many active memories feed it, and whether
    something is waiting for review. A key area with zero activity is still
    listed as 'not started yet' rather than hidden — that is real status,
    not a gap to paper over with invented content.
    """
    domains = set(KEY_AREAS)
    domains.update(memory_repo.list_domains(email))
    domains.update(profile_store.list_domains(email))
    domains.update(intention['domain'] for intention in intentions_repo.list_active_intentions(email))

    overview: list[dict[str, Any]] = []
    for domain in sorted(domains):
        accepted = profile_store.get_accepted(email, domain)
        history = profile_store.history(email, domain)
        has_pending_proposal = bool(history) and history[-1]['status'] == profile_store.PROPOSED
        active_memory_count = len(memory_repo.list_memories(email, status=memory_repo.ACTIVE, domain=domain))

        overview.append(
            {
                'domain': domain,
                'is_key_area': domain in KEY_AREAS,
                'accepted_entry': accepted,
                'version': accepted['version'] if accepted else 0,
                'active_memory_count': active_memory_count,
                'has_pending_proposal': has_pending_proposal,
            }
        )
    return overview
