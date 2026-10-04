from __future__ import annotations

import json
from typing import Any

from ..model_gateway import get_model_provider
from ..workflow.models import PlanStep
from ..workflow.state import RiskClass
from . import _shared
from ._graph import run, single_node_graph

# One step of a Brain 1 core agent's think → act → check loop
# (Building_Brain1.md §10). The loop itself runs in Orchestration, where the
# person's data lives and the tools execute; this node only decides the next
# move: call one tool, or finish with what this area of their life looks
# like right now. Grounded only in what the tools returned.


def _think(payload: dict[str, Any]) -> dict[str, Any]:
    core = payload.get('core') or {}
    tools: dict[str, str] = payload.get('tools') or {}
    findings: list[dict[str, Any]] = payload.get('findings') or []
    must_finish = bool(payload.get('must_finish'))

    lenses = '\n'.join(f"- {s.get('id')}: {s.get('lens')}" for s in core.get('sub_agents') or [])
    tool_lines = '\n'.join(f'- {name}: {help_text}' for name, help_text in tools.items())
    found = '\n\n'.join(f"[{f['tool']} {json.dumps(f.get('args') or {})}]\n{f['result']}" for f in findings) or '(nothing yet)'

    system_prompt = (
        f"You are the {core.get('name', 'area')} part of one person's second brain. Your goal: {core.get('goal', '')}\n"
        f'Look at it through these lenses:\n{lenses}\n\n'
        + ('' if must_finish else f'You can use one tool at a time:\n{tool_lines}\n\n')
        + 'Your summary may only state what THIS person said, did, or told us before (their message, their '
        'memories, their check-ins). No guesses about causes, no general knowledge, no diagnoses. If the '
        'evidence is thin, say only what is known — a short, plain summary is better than a speculative one.\n'
        + 'Return JSON only, either\n'
        + ('' if must_finish else '{"tool": "<tool name>", "args": {...}}  to look something up, or\n')
        + '{"done": true, "summary": "1-2 sentences on what is going on in this area for them right now", '
        '"open_question": "one thing worth asking them, or null", "confidence": 0.0-1.0}'
    )
    prompt = (
        f"Their latest message: {payload.get('message') or '(none)'}\n"
        f"Reading of it: {json.dumps(payload.get('reading') or {})}\n\n"
        f'Findings so far:\n{found}'
    )
    response = get_model_provider('large').chat([{'role': 'user', 'content': prompt}], system=system_prompt)
    return _normalise(_shared.parse_json_object(response), tools, must_finish)


def _normalise(parsed: dict[str, Any], tools: dict[str, str], must_finish: bool) -> dict[str, Any]:
    tool = parsed.get('tool')
    if not must_finish and isinstance(tool, str) and tool in tools and not parsed.get('done'):
        args = parsed.get('args') if isinstance(parsed.get('args'), dict) else {}
        return {'action': 'tool', 'tool': tool, 'args': {k: str(v) for k, v in args.items()}}
    summary = parsed.get('summary') if isinstance(parsed.get('summary'), str) else ''
    question = parsed.get('open_question')
    confidence = parsed.get('confidence')
    return {
        'action': 'done',
        'summary': summary.strip(),
        'open_question': question.strip() if isinstance(question, str) and question.strip().lower() not in ('', 'null') else None,
        'confidence': float(confidence) if isinstance(confidence, (int, float)) and 0 <= confidence <= 1 else 0.5,
    }


_GRAPH = single_node_graph('think', _think)


class CoreAgent:
    """One step of a Brain 1 core agent (Building_Brain1.md §10). One node: `think`."""

    name = 'core_agent'

    def plan(self, goal: str) -> list[PlanStep]:
        return [PlanStep(tool='core_agent', operation='think', risk_class=RiskClass.READ_ONLY, args=json.loads(goal))]

    def execute_step(self, step: PlanStep) -> dict[str, Any]:
        return run(_GRAPH, step.args)
