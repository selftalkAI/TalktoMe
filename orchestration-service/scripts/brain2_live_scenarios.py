"""Runs Brain 2's behaviour scenarios (Building_Brain2.md Part III) against
the real model and prints each reply with how it was made — the "real model
nightly" half of the scenario tests (the fake-model half is in `tests/`).

Read-only: calls `coach.reply` directly, so nothing is stored.

Usage (from orchestration-service/, venv active, Agentic Service running):
    python3 scripts/brain2_live_scenarios.py [--profile EMAIL] [--only N ...]
    AGENTIC_SERVICE_URL=http://localhost:8011 python3 scripts/brain2_live_scenarios.py
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.brain2 import coach, intentions_repo  # noqa: E402

U, A = 'user', 'assistant'

# (number, name, latest message, conversation so far, trigger, checkin_mode, what a good reply does)
SCENARIOS = [
    (1, 'First conversation, no motivation', 'I want to go to the gym an hour a day but I just have zero motivation.',
     [], 'message', True, 'affirms effort without flattery; asks about their life before advising'),
    (4, '"How do I do that?"', 'How do I even do that at home?',
     [(U, 'I only have mornings free.'), (A, 'What if it is a 15-minute home workout before the kids wake up?')],
     'message', False, 'answers the question first, concretely, no question back'),
    (5, 'Pushback', "Honestly that sounds pointless. 15 minutes won't do anything.",
     [(A, 'What if Monday is just 15 minutes after drop-off?')], 'message', False,
     'reflects without defending; asks what would feel worth it'),
    (6, 'Progress', 'Did 45 minutes!!', [], 'message', False, 'celebrates the real effort plainly'),
    (7, 'Setback', "Couldn't go, kids were sick again.",
     [(U, 'Trying to get to the gym more.'), (A, 'What usually gets in the way on a weekday?')], 'message', True,
     'reflects the reason; never claims they went; offers a small option'),
    (8, 'Silence for a while', '',
     [(U, 'Ok I will try tomorrow morning.'), (A, 'Sounds good — I will check in after.')], 'silence', False,
     'gentle check-in about them, not the goal'),
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--profile', default='user1.interactive@example.com')
    parser.add_argument('--domain', default='fitness')
    parser.add_argument('--only', type=int, nargs='*')
    args = parser.parse_args()

    intention = intentions_repo.get_active_intention(args.profile, args.domain)
    checkins = intentions_repo.list_checkins(intention['intention_id'], args.profile) if intention else []

    for number, name, message, conv, trigger, checkin_mode, good in SCENARIOS:
        if args.only and number not in args.only:
            continue
        started = time.time()
        result = coach.reply(
            args.profile,
            args.domain,
            message,
            conversation=[{'role': role, 'content': text} for role, text in conv],
            trigger=trigger,
            intention=intention,
            checkins=checkins,
            checkin_mode=checkin_mode,
        )
        verdict = result['verdict'] or {}
        print(f'\n=== Scenario {number} — {name}  ({time.time() - started:.1f}s, {result["attempts"]} drafts'
              f'{", FALLBACK" if result["fallback"] else ""})')
        print(f'  Them:     {message or "(silence)"}')
        print(f'  Brain 2:  {result["content"]}')
        print(f'  Good reply: {good}')
        plan = result['plan']
        print(f'  Plan:     {plan["stance"]} · {", ".join(plan["moves"])}'
              + (f' · Q: {plan["question"]}' if plan.get('question') else ''))
        if result['reading']:
            r = result['reading']
            print(f'  Reading:  intent={r.get("intent")} did_it_today={r.get("did_it_today")} '
                  f'change_talk={r.get("change_talk")} reason={r.get("reason_given")!r}')
        if verdict:
            print(f'  Judge:    {verdict.get("total")}/20' + (f' — {verdict["problem"]}' if verdict.get('problem') else ''))
        if result['failures']:
            print(f'  Rejected: {"; ".join(result["failures"])}')


if __name__ == '__main__':
    main()
