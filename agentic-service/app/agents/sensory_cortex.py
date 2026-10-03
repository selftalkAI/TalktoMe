from __future__ import annotations

import json
from typing import Any

from ..model_gateway import get_model_provider
from ..workflow.models import PlanStep
from ..workflow.state import RiskClass
from . import _shared
from ._graph import run, single_node_graph


def _understand(payload: dict[str, Any]) -> dict[str, Any]:
    """Turns what Brain 1 just said into structured signal for other agents —

    never advice, never a decision, only interpretation. The sensory-cortex
    job: raw input in, structured perception out.
    """
    lines = _shared.profile_lines(payload)
    response_text = (payload.get('response_text') or '').strip()

    system_prompt = (
        "You are ONLY listening and understanding right now — you never give advice, "
        "suggest actions, or decide anything for this person. Given their profile and what "
        "they just said about how they're doing, produce structured understanding for "
        "another agent to act on later. Respond with strict JSON only, no markdown fencing, "
        'matching exactly this shape: {"mood_summary": "...", "context_notes": "...", '
        '"narrative_focus": "..."}.\n'
        "- mood_summary: a short, empathetic characterization of how they seem to be feeling "
        "right now, grounded only in their own words.\n"
        "- context_notes: anything specific they mentioned (an event, a worry, a win) that "
        "another agent should know about — empty string if nothing notable.\n"
        "- narrative_focus: 5-10 words naming the emotional/thematic lens their reflections "
        "should favor right now, grounded in both their stated interests and how they say "
        "they're feeling."
    )
    prompt = (
        'Profile:\n'
        + '\n'.join(lines)
        + '\n\nWhat they just said when asked how they\'re doing:\n'
        + (response_text or '(they didn\'t say anything)')
    )

    provider = get_model_provider()
    response = provider.chat([{'role': 'user', 'content': prompt}], system=system_prompt)

    try:
        parsed = json.loads(response)
    except json.JSONDecodeError:
        parsed = {'mood_summary': response.strip()}

    return {
        'mood_summary': parsed.get('mood_summary', ''),
        'context_notes': parsed.get('context_notes', ''),
        'narrative_focus': parsed.get('narrative_focus', ''),
    }


_GRAPH = single_node_graph('understand', _understand)


class SensoryCortex:
    """Interprets Brain 1's response into structured signal (ADD §8). One

    node, one job: `understand`. What used to be `ProfileAgent._understand`
    — split from Thalamus because relaying (first contact) and interpreting
    (making sense of what came back) are different jobs.
    """

    name = 'sensory_cortex'

    def plan(self, goal: str) -> list[PlanStep]:
        payload = json.loads(goal)
        return [
            PlanStep(
                tool='sensory_cortex',
                operation='understand',
                risk_class=RiskClass.READ_ONLY,
                args=payload,
            )
        ]

    def execute_step(self, step: PlanStep) -> dict[str, Any]:
        return run(_GRAPH, step.args)
