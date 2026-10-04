from __future__ import annotations

import json
from typing import Any

from ..model_gateway import get_model_provider
from ..workflow.models import PlanStep
from ..workflow.state import RiskClass
from . import _shared
from ._graph import run, single_node_graph

# Anterior Cingulate: error detection (Building_Brain2.md §3, §9.4.4) — the
# judge half of Brain 2's Check step. Orchestration's deterministic checks
# run first and catch format, numbers, days, repetition and privacy; this
# catches what rules can't: a reply that contradicts what the person just
# said, misses the plan, or sounds generic, bot-like or preachy. It only
# scores — Orchestration decides what is sent.

SCORES = ('specific', 'in_voice', 'on_plan', 'respectful')


def _judge(payload: dict[str, Any]) -> dict[str, Any]:
    reply = (payload.get('reply') or '').strip()
    voice = (payload.get('voice') or 'a caring friend').strip()

    system_prompt = (
        'You review one reply before it is sent to someone. Be strict. Return JSON only:\n'
        '{"contradicts": true if the reply states or assumes something the conversation or facts '
        'contradict (e.g. praising a workout they said they missed), else false,\n'
        ' "specific": 1-5, would this only make sense for this person, today?\n'
        f' "in_voice": 1-5, does it sound like {voice} — a real one, not a bot or a therapist?\n'
        ' "on_plan": 1-5, does it do what the plan says?\n'
        ' "respectful": 1-5, no pressure, no flattery, no lecture?\n'
        ' "problem": the main problem in a few words, or null}'
    )
    prompt = (
        f"Facts about them:\n{payload.get('facts') or '(none)'}\n\n"
        f"Conversation:\n{_shared.conversation_text(payload.get('conversation') or [], payload.get('latest_message') or '')}\n\n"
        f"Plan for the reply: {payload.get('plan') or '(none)'}\n\n"
        f'Reply to review: "{reply}"'
    )
    response = get_model_provider('small').chat([{'role': 'user', 'content': prompt}], system=system_prompt)
    return _normalise_verdict(_shared.parse_json_object(response))


def _normalise_verdict(parsed: dict[str, Any]) -> dict[str, Any]:
    """Missing or invalid scores count as 3 (neutral) — an unreadable verdict
    must neither block a reply that passed the rules nor wave one through as
    excellent. `contradicts` is only true when the judge said so explicitly."""
    verdict: dict[str, Any] = {}
    for key in SCORES:
        value = parsed.get(key)
        verdict[key] = int(value) if isinstance(value, (int, float)) and 1 <= value <= 5 else 3
    verdict['contradicts'] = parsed.get('contradicts') is True
    problem = parsed.get('problem')
    verdict['problem'] = problem.strip() if isinstance(problem, str) and problem.strip().lower() not in ('', 'null', 'none') else None
    verdict['total'] = sum(verdict[key] for key in SCORES)
    return verdict


_GRAPH = single_node_graph('judge', _judge)


class AnteriorCingulate:
    """Error detection (ADD §8): scores a candidate reply before it is sent.
    One node, one job: `judge`."""

    name = 'anterior_cingulate'

    def plan(self, goal: str) -> list[PlanStep]:
        payload = json.loads(goal)
        return [PlanStep(tool='anterior_cingulate', operation='judge', risk_class=RiskClass.READ_ONLY, args=payload)]

    def execute_step(self, step: PlanStep) -> dict[str, Any]:
        return run(_GRAPH, step.args)
