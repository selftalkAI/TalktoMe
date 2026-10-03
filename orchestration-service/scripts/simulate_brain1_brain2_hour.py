"""Runs an unattended, hour-long, real-time conversation between a simulated

Brain 1 (User 1 — `BrainOne`, the simulation-only agent in
`agentic-service/app/agents/brain_one.py`) and the real Brain 2 (the actual
`orchestration-service/app/brain2` orchestrator + the real cognitive agents:
Amygdala for support, Broca for Profile narratives). No human types anything;
BrainOne speaks for User 1 every simulated day, Brain 2's deterministic gates
(`intentions_repo.shortfall_streak`) decide when something is actually worth
saying back, and BrainOne also "decides" (a scripted policy, not an LLM
guess) when to accept a smaller target or push for a bigger one — so the
whole propose/offer/accept loop runs end to end without anyone pausing it for
approval.

One simulated day = one real minute by default: a lightweight heartbeat
prints every `--tick-seconds` (30s default) showing how state is evolving
between turns, and the full Brain1<->Brain2 exchange for that day happens
once per minute. Ground-truth numbers (today's actual minutes, the target,
the streak) are always decided by this script, never invented by a model —
same ADR-007 split as the rest of this codebase; the model only ever composes
the words around a number already decided.

The story arc is scripted to go somewhere: User 1 starts clearly short of a
60 min/day gym goal, Brain 2 notices within the first few simulated days and
offers a smaller target, User 1 accepts it, builds a streak of actually
meeting it, and progressively raises the target back toward the original 60
as confidence grows — ending with the original goal durably met.

Usage (from orchestration-service/, with its venv active; agentic-service
must be running on :8001 for real LLM-composed language, else this falls
back to plain deterministic text, same contract as orchestrator.py):

    python3 scripts/simulate_brain1_brain2_hour.py
    python3 scripts/simulate_brain1_brain2_hour.py --minutes 5 --tick-seconds 5 --no-sleep   # fast smoke test
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import brain1  # noqa: E402
from app.brain2 import orchestrator  # noqa: E402
from app.paths import REPO_ROOT  # noqa: E402
from app.spinal_cord import AgenticServiceClient, AgenticServiceError  # noqa: E402

PROFILE_EMAIL = 'user1.sim@example.com'
DOMAIN = 'fitness'
ORIGINAL_TARGET_MINUTES = 60
SHORTFALL_RENEGOTIATION_FLOOR = 10
TARGET_RAISE_STEP = 15
MEETS_BEFORE_MILESTONE = 5

PROFILE_FACTS = {
    'full_name': 'User One',
    'dob': '1991-04-12',
    'location': 'Austin, TX',
    'interests': ['healthy_living', 'mindfulness'],
    'other_interests': 'cycling on weekends',
    'quote': 'Small steps still move you forward.',
}


def _log(log_file, line: str) -> None:
    print(line)
    log_file.write(line + '\n')
    log_file.flush()


def _ensure_profile() -> dict:
    existing = brain1.get(PROFILE_EMAIL)
    if existing is not None:
        return existing
    return brain1.create(
        email=PROFILE_EMAIL,
        full_name=PROFILE_FACTS['full_name'],
        password='simulation-only-123',
        dob=PROFILE_FACTS['dob'],
        location=PROFILE_FACTS['location'],
        interests=PROFILE_FACTS['interests'],
        other_interests=PROFILE_FACTS['other_interests'],
        photo_data_url=None,
        quote=PROFILE_FACTS['quote'],
    )


def _ensure_intention() -> dict:
    from app.brain2 import intentions_repo

    active = intentions_repo.get_active_intention(PROFILE_EMAIL, DOMAIN)
    if active is not None:
        return active
    return orchestrator.set_intention(PROFILE_EMAIL, DOMAIN, title='Gym', target_minutes=ORIGINAL_TARGET_MINUTES)


def _call_brain_one(
    day_index: int,
    target_minutes: int,
    actual_minutes: int,
    yesterday_minutes: int,
    phase: str,
    last_brain2_message: str,
) -> str:
    payload = {
        **PROFILE_FACTS,
        'day_index': day_index,
        'target_minutes': target_minutes,
        'actual_minutes': actual_minutes,
        'yesterday_minutes': yesterday_minutes,
        'phase': phase,
        'last_brain2_message': last_brain2_message,
    }
    try:
        client = AgenticServiceClient()
        run = client.create_agent_run('brain_one', user_id=PROFILE_EMAIL, goal=json.dumps(payload))
    except AgenticServiceError:
        return _fallback_user_message(day_index, target_minutes, actual_minutes, phase)

    if run.get('status') != 'completed':
        return _fallback_user_message(day_index, target_minutes, actual_minutes, phase)
    steps = run.get('steps') or []
    result = steps[0].get('result') if steps else None
    message = (result or {}).get('user_message')
    return message.strip() if message else _fallback_user_message(day_index, target_minutes, actual_minutes, phase)


def _fallback_user_message(day_index: int, target_minutes: int, actual_minutes: int, phase: str) -> str:
    mood = {
        'struggling': "didn't manage it again, feeling a bit defeated.",
        'renegotiated': 'this smaller number actually felt doable today.',
        'meeting': "keeping up with it — feels like it's sticking.",
        'pushing': 'ready to push a bit further.',
        'achieved': 'this is just part of my day now.',
    }.get(phase, 'checking in.')
    return f'Day {day_index}: did {actual_minutes} of my {target_minutes} min target — {mood}'


def _actual_minutes(rng: random.Random, target_minutes: int, phase: str) -> int:
    if phase == 'struggling':
        return max(5, round(target_minutes * rng.uniform(0.15, 0.45)))
    return max(5, round(target_minutes * rng.uniform(0.85, 1.35)))


def run_simulation(total_minutes: int, tick_seconds: int, do_sleep: bool) -> None:
    REPO_ROOT.joinpath('Docs', 'DEMO').mkdir(parents=True, exist_ok=True)
    log_path = REPO_ROOT / 'Docs' / 'DEMO' / f"brain1_brain2_hour_{time.strftime('%Y%m%d_%H%M%S')}.log"

    with open(log_path, 'w') as log_file:
        _log(log_file, f'=== Brain 1 <-> Brain 2 simulation starting — {total_minutes} simulated day(s), log: {log_path} ===')

        _ensure_profile()
        intention = _ensure_intention()
        _log(log_file, f"Brain 1 (profile): {PROFILE_FACTS['full_name']} — intention '{intention['title']}', target {intention['target_minutes']} min/day, domain '{DOMAIN}'.")

        rng = random.Random(42)
        base_date = date.today() - timedelta(days=total_minutes + 5)

        phase = 'struggling'
        last_brain2_message = ''
        yesterday_minutes = 0
        consecutive_meets = 0
        achieved_goal = False
        proposals_accepted = 0
        ticks_per_minute = max(1, round(60 / tick_seconds))

        start = time.monotonic()
        for day_index in range(1, total_minutes + 1):
            minute_start = time.monotonic()

            # Heartbeat tick(s) before the day's exchange — "how it evolves"
            # between turns, independent of whether anything new was said.
            for _ in range(ticks_per_minute - 1):
                if do_sleep:
                    time.sleep(tick_seconds)
                elapsed = time.monotonic() - start
                _log(
                    log_file,
                    f'  [t={elapsed:6.1f}s] heartbeat — day {day_index}/{total_minutes}, '
                    f"target={intention['target_minutes']}min, phase={phase}, "
                    f'consecutive_meets={consecutive_meets}, proposals_accepted={proposals_accepted}',
                )

            target = intention['target_minutes']
            actual = _actual_minutes(rng, target, phase)
            checkin_date = (base_date + timedelta(days=day_index)).isoformat()

            user_message = _call_brain_one(day_index, target, actual, yesterday_minutes, phase, last_brain2_message)
            _log(log_file, f'BRAIN 1 (User 1): {user_message}')

            result = orchestrator.log_checkin(PROFILE_EMAIL, intention['intention_id'], actual, checkin_date, note=user_message[:200])
            streak = result['streak']
            intention = result['intention']

            if result['needs_support']:
                support = orchestrator.offer_support(PROFILE_EMAIL, intention, streak, result['checkins'])
                _log(log_file, f"BRAIN 2 (notices, offers support): {support['message']}")
                last_brain2_message = support['message']

                proposal = orchestrator.propose_refinement(
                    profile_email=PROFILE_EMAIL,
                    domain=DOMAIN,
                    user_reflection=user_message,
                    intention=intention,
                    streak=streak,
                    support_message=support['message'],
                )
                accepted = orchestrator.accept_proposal(proposal['profile_entry_id'], PROFILE_EMAIL)
                proposals_accepted += 1
                _log(log_file, f"BRAIN 2 (Profile '{DOMAIN}' v{accepted['version']}, accepted): {accepted['content']}")

                suggested = support.get('suggested_target_minutes')
                new_target = suggested if isinstance(suggested, int) and suggested > 0 else max(
                    SHORTFALL_RENEGOTIATION_FLOOR, round(target * 0.5)
                )
                intention = orchestrator.adjust_intention(PROFILE_EMAIL, intention['intention_id'], new_target)
                _log(log_file, f'BRAIN 1 (User 1): agrees — smaller target of {new_target} min/day for now.')
                phase = 'renegotiated'
                consecutive_meets = 0
            else:
                _log(
                    log_file,
                    f"BRAIN 2 (ack, no model call): logged {actual}min vs {target}min target; "
                    f'consecutive shortfall streak={streak}.',
                )

                if phase == 'renegotiated' and actual >= target:
                    phase = 'meeting'

                consecutive_meets = consecutive_meets + 1 if actual >= target else 0

                if phase in ('meeting', 'pushing', 'achieved') and consecutive_meets > 0 and consecutive_meets % MEETS_BEFORE_MILESTONE == 0:
                    proposal = orchestrator.propose_refinement(
                        profile_email=PROFILE_EMAIL,
                        domain=DOMAIN,
                        user_reflection=user_message,
                        intention=intention,
                        streak=0,
                        support_message='',
                    )
                    accepted = orchestrator.accept_proposal(proposal['profile_entry_id'], PROFILE_EMAIL)
                    proposals_accepted += 1
                    _log(log_file, f"BRAIN 2 (Profile '{DOMAIN}' v{accepted['version']}, accepted): {accepted['content']}")

                    if intention['target_minutes'] < ORIGINAL_TARGET_MINUTES:
                        new_target = min(ORIGINAL_TARGET_MINUTES, intention['target_minutes'] + TARGET_RAISE_STEP)
                        intention = orchestrator.adjust_intention(PROFILE_EMAIL, intention['intention_id'], new_target)
                        _log(log_file, f'BRAIN 1 (User 1): feeling ready for more — raises target to {new_target} min/day.')
                        phase = 'pushing'
                    elif not achieved_goal:
                        achieved_goal = True
                        phase = 'achieved'
                        _log(log_file, f'*** GOAL ACHIEVED on day {day_index}: sustaining the original {ORIGINAL_TARGET_MINUTES} min/day gym target. ***')
                    consecutive_meets = 0

            yesterday_minutes = actual

            elapsed_in_minute = time.monotonic() - minute_start
            remaining = tick_seconds - elapsed_in_minute
            if do_sleep and remaining > 0:
                time.sleep(remaining)

        total_elapsed = time.monotonic() - start
        _log(log_file, '')
        _log(log_file, f'=== Simulation complete after {total_elapsed:.1f}s real time, {total_minutes} simulated day(s) ===')
        _log(log_file, f"Final target: {intention['target_minutes']} min/day | Goal achieved: {achieved_goal} | Profile proposals accepted: {proposals_accepted}")
        final_entry = orchestrator.accept_proposal  # noqa: F841  (kept for readability of the summary above only)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--minutes', type=int, default=60, help='Number of simulated days / real minutes (default 60).')
    parser.add_argument('--tick-seconds', type=int, default=30, help='Heartbeat interval in seconds (default 30).')
    parser.add_argument('--no-sleep', action='store_true', help='Skip real sleeping, for fast smoke-testing the logic.')
    args = parser.parse_args()

    run_simulation(total_minutes=args.minutes, tick_seconds=args.tick_seconds, do_sleep=not args.no_sleep)


if __name__ == '__main__':
    main()
