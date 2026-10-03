"""Brain 1 — the user.

Sovereign, biological, the only actor who ever decides or acts (ADD §1.1).
Brain 1 has no reasoning or memory of its own to implement here — it IS the
person behind `profile_email` everywhere else in this service (moments,
memories, intentions, every accept/reject decision). This package gives that
concept an explicit home in the code, the same way `brain2/` is Brain 2's
home, even though the data underneath is the same `profiles` table it always
was: `identity.py` wraps that record and the one thing that matters
architecturally at creation time (Brain 2's Scheduler going live immediately,
not on its next cycle); `key_areas.py` is the confirmed starter set of
Profile domains (ADD §6.1) this Brain 1's life is organized around.
"""

from __future__ import annotations

from .identity import authenticate, create, get, list_all
from .key_areas import KEY_AREAS, key_areas_overview

__all__ = ['authenticate', 'create', 'get', 'list_all', 'KEY_AREAS', 'key_areas_overview']
