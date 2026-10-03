"""Brain 2 — selfie.Me itself.

Brain 1 is the user: sovereign, the only one who ever decides or acts — see
`app/brain1/` for that package. Brain 1's package holds no reasoning or
memory of its own (a human doesn't need a model); it only wraps Brain 1's own
identity record and gives the Brain1<->Brain2 relationship a place to start
from. Everything below is Brain 2's side of that relationship.

Brain 2 is everything in this package: one orchestrator (`orchestrator.py`)
that takes on different jobs at different points in a conversation, plus the
tools it holds no memory of its own without — a versioned Profile Store
(`profile_store.py`), an intentions/check-ins ledger (`intentions_repo.py`)
that plays the same role goal tracking (US-004) did, rebuilt from scratch
against the settled Two Brains architecture rather than extending it, and a
Scheduler (`scheduler.py`, ADD §8.2 step 1) that keeps rechecking the Profile
Store on its own, with no new input, for as long as this service is running.

The one rule every function in this package answers to: Brain 2 may propose,
never write. Nothing here ever supersedes a Profile entry without an explicit
accept call from Brain 1.
"""
