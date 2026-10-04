"""Brain 1 — the person (Human) and their Persona.

The Human is the only authority (ADD §1.1): `identity.py` is their account.
The Persona is Brain 1's agentic model of them: `profile.py` (the structured
profile), `context_pack.py`, `persona_selector.py`, `core_engine.py` and its
`cores/`, `knowledge.py` and its `knowledge/` cards, `safety.py`, `here_now.py`,
`learning.py`, `reflector.py`, `episodes.py`, `patterns.py`, `proactive.py`,
`consent.py`, `runs.py`, `tools.py` (Building_Brain1.md).
"""

from __future__ import annotations

from .identity import authenticate, create, get, list_all
__all__ = ['authenticate', 'create', 'get', 'list_all']
