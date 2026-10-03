from __future__ import annotations

import json
from typing import Any

from ..model_gateway import get_model_provider
from ..workflow.models import PlanStep
from ..workflow.state import RiskClass
from ._graph import run, single_node_graph


def _benchmark(payload: dict[str, Any]) -> dict[str, Any]:
    """Looks up outside expert knowledge for one domain (ADD §8.2 step 5) —

    the one place in this whole system that is ALLOWED to bring in general
    knowledge rather than stay grounded only in Brain 1's own words. Every
    other agent (Prefrontal Cortex especially) is forbidden from doing this;
    this agent's entire job is the opposite — go compare Brain 1's own
    stated experience against real, established expertise, so Broca's Area
    can later synthesize the two into a genuine proposal, not a pep talk.

    This does not know or care who Brain 1 is beyond the domain + a short
    summary of what they said — it must never address them directly or
    assume anything about them beyond that summary. It only ever produces
    a candidate; per ADR-007 it has no authority over what Brain 1 sees or
    what becomes durable, the same as every other agent's output here.
    """
    domain = (payload.get('domain') or '').strip() or 'this'
    context = (payload.get('context') or '').strip()

    if not context:
        return {'benchmark': ''}

    system_prompt = (
        "You are researching established, real-world expertise for ONE specific life domain, "
        "so it can be compared against what a person has said about their own experience in "
        "that domain. This is NOT motivational writing and not a lecture — you are finding ONE "
        "concrete, genuinely useful idea or fact from real expertise in this domain that a "
        "person in their situation might not have considered. Ground it in something real and "
        "specific: known research, a well-established technique, a concrete alternative "
        "approach — never vague encouragement like 'stay motivated', 'consistency is key', or "
        "'you can do it'. If you don't know something specific and well-established for this "
        "domain, say so plainly rather than inventing generic advice dressed up as expertise.\n\n"
        "Write in third person / general terms — describe what the expertise says, do not "
        "address the person directly ('you should...') and do not assume any fact about them "
        "beyond what's given below. Someone else (not you) will decide whether and how to bring "
        "this to the person's attention. 2-3 sentences, no more. Respond with strict JSON only, "
        'no markdown fencing, matching exactly this shape: {"benchmark": "..."}.'
    )
    prompt = f'Domain: {domain}\nWhat this person has said about it: {context}'

    provider = get_model_provider()
    response = provider.chat([{'role': 'user', 'content': prompt}], system=system_prompt)

    try:
        parsed = json.loads(response)
    except json.JSONDecodeError:
        parsed = {'benchmark': response.strip()}

    return {'benchmark': parsed.get('benchmark', '')}


_GRAPH = single_node_graph('benchmark', _benchmark)


class WorldKnowledge:
    """Outside expert knowledge lookup (ADD §4 Intelligence plane, §8.2 step

    5) — a gateway, not one of Brain 2's own cognitive organs, the same
    distinction the architecture draws between the Model Gateway and the
    reasoning agents that call it. One node, one job: `benchmark`.
    """

    name = 'world_knowledge'

    def plan(self, goal: str) -> list[PlanStep]:
        payload = json.loads(goal)
        return [
            PlanStep(
                tool='world_knowledge',
                operation='benchmark',
                risk_class=RiskClass.READ_ONLY,
                args=payload,
            )
        ]

    def execute_step(self, step: PlanStep) -> dict[str, Any]:
        return run(_GRAPH, step.args)
