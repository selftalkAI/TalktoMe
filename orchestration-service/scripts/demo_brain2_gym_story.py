"""Runs the "one hour gym" user story end to end against Brain 2, printing

each step so the propose/accept/refine/reject mechanism is directly
observable without any frontend. This is the story that started the whole
Two Brains conversation: Brain 1 wants to gym for an hour, Brain 1's own
willpower doesn't show up for a few days, Brain 2 notices and offers support
(never a command), and — only once Brain 1 says so — that whole arc becomes
a durable, versioned Profile entry: "brain strength."

If the Agentic Service (agentic-service/, `uvicorn app.main:app --port 8001`)
isn't running, Brain 2 falls back to plain deterministic language instead of
calling the model — the mechanism (propose/accept/reject, supersede-not-
overwrite) is what this script proves, not prompt quality.

Usage (from orchestration-service/, with its venv active):
    python3 scripts/demo_brain2_gym_story.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.brain2 import intentions_repo, orchestrator, profile_store  # noqa: E402

PROFILE_EMAIL = 'demo-brain1@example.com'
DOMAIN = 'fitness'


def line(label: str, text: str = '') -> None:
    print(f'\n[{label}] {text}' if text else f'\n[{label}]')


def main() -> None:
    line('BRAIN 1', 'I want to do gym for one hour a day.')
    intention = orchestrator.set_intention(PROFILE_EMAIL, DOMAIN, title='Gym', target_minutes=60)
    line('BRAIN 2 (Memory Store)', f"Intention recorded: '{intention['title']}', target {intention['target_minutes']} min/day.")

    # Three days in a row, Brain 1's own willpower doesn't show up — a real
    # streak, not a single bad day (SHORTFALL_STREAK_THRESHOLD = 3).
    days = [
        ('2026-09-24', 0, 'skipped, work ran late'),
        ('2026-09-25', 0, "didn't go, just tired"),
        ('2026-09-26', 0, 'meant to but never left the house'),
    ]
    result: dict = {}
    for checkin_date, minutes, note in days:
        line('BRAIN 1', f'{checkin_date}: {note} ({minutes} min)')
        result = orchestrator.log_checkin(PROFILE_EMAIL, intention['intention_id'], minutes, checkin_date, note)
        line('BRAIN 2 (deterministic gate)', f"streak under target: {result['streak']} day(s); needs_support={result['needs_support']}")

    if not result.get('needs_support'):
        line('BRAIN 2', 'No pattern yet — staying quiet. (Should not happen with the three days above.)')
        return

    support = orchestrator.offer_support(PROFILE_EMAIL, result['intention'], result['streak'], result['checkins'])
    line('BRAIN 2 (offers, does not command)', support['message'])
    if support.get('suggested_target_minutes'):
        line('BRAIN 2', f"(also suggested a smaller target: {support['suggested_target_minutes']} min/day)")

    # Brain 1 responds in their own words — this becomes the reflection that
    # makes the moment eligible to become a memory at all (FSD FR-PROF-002).
    user_reflection = (
        "Honestly work has been brutal this week and by the time I'm done I have zero energy left. "
        "I don't want to give up on this though - maybe 20 minutes is more realistic for now."
    )
    line('BRAIN 1', user_reflection)

    proposal = orchestrator.propose_refinement(
        profile_email=PROFILE_EMAIL,
        domain=result['intention']['domain'],
        user_reflection=user_reflection,
        intention=result['intention'],
        streak=result['streak'],
        support_message=support['message'],
    )
    line('BRAIN 2 (proposes, does not write)', f"Profile draft for domain '{proposal['domain']}' (v{proposal['version']}, status={proposal['status']}):")
    print(f"    {proposal['content']}")

    # Brain 1 decides. This is the only call in the whole script that can
    # ever change what the Profile durably says.
    line('BRAIN 1', 'Yes, that\'s right — accept it, and let\'s adjust the target to 20 min for now.')
    accepted = orchestrator.accept_proposal(proposal['profile_entry_id'], PROFILE_EMAIL)
    line('BRAIN 2 (writes, only now)', f"Profile entry v{accepted['version']} for '{accepted['domain']}' is now ACCEPTED.")

    new_intention = orchestrator.adjust_intention(PROFILE_EMAIL, result['intention']['intention_id'], new_target_minutes=20)
    line('BRAIN 2 (Memory Store)', f"Intention superseded: new target {new_intention['target_minutes']} min/day (old target kept in history).")

    line('VERIFY — full Profile history for this domain (nothing ever deleted)')
    for entry in profile_store.history(PROFILE_EMAIL, DOMAIN):
        print(f"    v{entry['version']} [{entry['status']}] {entry['content'][:90]}...")

    line('VERIFY — full intention history for this domain (nothing ever mutated in place)')
    with_supersession = [new_intention['intention_id'], new_intention['supersedes_intention_id']]
    for intention_id in with_supersession:
        if intention_id:
            row = intentions_repo.get_intention(intention_id, PROFILE_EMAIL)
            print(f"    {row['intention_id']} [{row['status']}] target={row['target_minutes']} min/day")


if __name__ == '__main__':
    main()
