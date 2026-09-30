"""Brain 2 — selfie.Me itself.

Brain 1 is the user: sovereign, the only one who ever decides or acts. Brain 1
gets no code here — a human doesn't need a module.

Brain 2 is everything in this package: one orchestrator (`orchestrator.py`)
that takes on different jobs at different points in a conversation, plus the
tools it holds no memory of its own without — a versioned Profile Store
(`profile_store.py`) and an intentions/check-ins ledger (`intentions_repo.py`)
that plays the same role goal tracking (US-004) did, rebuilt from scratch
against the settled Two Brains architecture rather than extending it.

The one rule every function in this package answers to: Brain 2 may propose,
never write. Nothing here ever supersedes a Profile entry without an explicit
accept call from Brain 1.
"""
