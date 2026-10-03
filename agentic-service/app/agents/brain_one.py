from __future__ import annotations

import json
from typing import Any

from ..model_gateway import get_model_provider
from ..workflow.models import PlanStep
from ..workflow.state import RiskClass
from . import _shared
from ._graph import run, single_node_graph

# BrainOne is a SIMULATION-ONLY agent — it is not one of Brain 2's cognitive
# organs (ADD §8) and the real app never calls it. It exists to stand in for
# User 1 (Brain 1) during an unattended, scripted conversation with Brain 2
# (`orchestration-service/scripts/simulate_brain1_brain2_hour.py`), so the
# full propose/offer/accept loop can be exercised end-to-end over a long
# window without a human typing anything. Like every other agent here it
# never invents the ground-truth numbers (today's actual minutes, the target,
# the streak) — those are decided deterministically by the driver script,
# the same ADR-007 split as everywhere else. This agent only ever composes
# ONE thing: the words User 1 would say about that already-decided outcome.


def _simulate_user_turn(payload: dict[str, Any]) -> dict[str, Any]:
    """Speaks as User 1, reporting in on one simulated day's gym session.

    Grounded only in the structured facts handed to it below — their profile,
    today's actual vs. target minutes, yesterday's minutes, which phase of
    the journey this is, and whatever Brain 2 said last turn (if anything) —
    never anything outside that.
    """
    who_lines = _shared.profile_lines(payload)
    day_index = payload.get('day_index')
    target_minutes = payload.get('target_minutes')
    actual_minutes = payload.get('actual_minutes')
    yesterday_minutes = payload.get('yesterday_minutes')
    phase = payload.get('phase', 'struggling')
    last_brain2_message = (payload.get('last_brain2_message') or '').strip()

    phase_hint = {
        'struggling': 'You are currently falling short of your target most days and it is wearing on you.',
        'renegotiated': 'You and your companion just agreed on a smaller, more realistic target — you feel a mix of relief and mild guilt about it.',
        'meeting': 'You have been consistently meeting your current target for a few days and are building real confidence.',
        'pushing': 'You just asked to raise your own target again because you are feeling ready for more.',
        'achieved': 'You have been hitting or beating your original one-hour goal consistently — this is the payoff of the whole journey.',
    }.get(phase, '')

    system_prompt = (
        "You are playing ONE specific person (User 1) checking in with a companion about their daily "
        "gym session, as part of a long-running, honest, day-by-day relationship — NOT a one-off "
        "chat. Speak in first person, 1-2 sentences, like a real text message to someone who already "
        "knows your situation — not a journal entry and not a report. Ground every number you mention "
        "ONLY in the exact figures given below; never invent, round, or restate them differently. You "
        "may explain how you feel and why today went the way it did, in a way consistent with who you "
        "are (their interests/location/age if given) — but never invent an event, person, or excuse "
        "that isn't a plausible everyday reason (work, tiredness, motivation, weather, a small win, "
        "building confidence, etc.). Respond with strict JSON only, no markdown fencing, matching "
        'exactly this shape: {"user_message": "..."}.'
        + (f' Context for your tone: {phase_hint}' if phase_hint else '')
    )
    prompt = (
        (('Who you are:\n' + '\n'.join(who_lines) + '\n\n') if who_lines else '')
        + f'This is day {day_index} of trying to build this habit.\n'
        + f'Your target right now: {target_minutes} min/day.\n'
        + f"Yesterday you did: {yesterday_minutes} min.\n"
        + f'Today you did: {actual_minutes} min.\n'
        + (f'\nWhat your companion said last time: "{last_brain2_message}"\n' if last_brain2_message else '')
        + '\nCheck in about today in your own words.'
    )

    provider = get_model_provider()
    response = provider.chat([{'role': 'user', 'content': prompt}], system=system_prompt)

    try:
        parsed = json.loads(response)
    except json.JSONDecodeError:
        parsed = {'user_message': response.strip()}

    return {'user_message': parsed.get('user_message', '').strip()}


_GRAPH = single_node_graph('simulate_user_turn', _simulate_user_turn)


class BrainOne:
    """SIMULATION ONLY — see module docstring. Plays User 1's side of a

    conversation with Brain 2 so the propose/offer/accept loop can run
    unattended for a long scripted window. One node, one job:
    `simulate_user_turn`.
    """

    name = 'brain_one'

    def plan(self, goal: str) -> list[PlanStep]:
        payload = json.loads(goal)
        return [
            PlanStep(
                tool='brain_one',
                operation='simulate_user_turn',
                risk_class=RiskClass.READ_ONLY,
                args=payload,
            )
        ]

    def execute_step(self, step: PlanStep) -> dict[str, Any]:
        return run(_GRAPH, step.args)
