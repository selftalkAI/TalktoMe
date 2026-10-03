from __future__ import annotations

import json
from typing import Any

from ..model_gateway import get_model_provider
from ..workflow.models import PlanStep
from ..workflow.state import RiskClass
from ._graph import run, single_node_graph


def _extract_memories(payload: dict[str, Any]) -> dict[str, Any]:
    """Encodes raw text into candidate durable memories (TDD §5 step 2) — the

    hippocampus job: turning an experience into something that could become
    long-term memory. This only proposes candidates; it never decides what
    actually becomes durable. That write-gate decision (confidence/
    sensitivity thresholds, dedup) is deterministic logic in Orchestration's
    memory_manager, kept outside the model per ADR-007: the model proposes,
    it never authorizes a write.
    """
    source_text = (payload.get('source_text') or '').strip()
    existing: list[str] = payload.get('existing_active_memories') or []
    full_name = (payload.get('full_name') or '').strip() or 'this person'

    if not source_text:
        return {'candidates': []}

    existing_block = (
        (
            '\n\nThings already remembered about them (do not repeat these, propose only '
            'genuinely new information):\n' + '\n'.join(f'- {m}' for m in existing)
        )
        if existing
        else ''
    )

    system_prompt = (
        "You extract durable, reusable personal facts about ONE person from something they "
        "just said, for a personal memory system. Favor precision over volume: it is safer to "
        "propose nothing than to invent or overreach. Only propose a candidate if it would "
        "genuinely be useful to recall in a FUTURE, unrelated conversation — not one-off "
        "conversational filler. Never propose anything about a third party (someone other than "
        "the person speaking) as if it were their own memory. Respond with strict JSON only, no "
        'markdown fencing, matching exactly this shape: {"candidates": [{"type": "...", '
        '"domain": "..." or null, "content": "...", "explicitness": "...", "confidence": 0.0, '
        '"sensitivity_tier": "...", "rationale_code": "..."}]}. Return {"candidates": []} if '
        'nothing qualifies.\n'
        "- type: one of fact, preference, goal, relationship, event, routine, constraint, "
        "project_context, user_instruction.\n"
        "- domain: the life area this belongs to for a personal Profile — e.g. skill, emotion, "
        "learning, reading, relationship, goal — or null if it doesn't clearly belong to one. "
        "This is independent of type: a fact can belong to a skill domain, a goal can belong to "
        "an emotion domain, etc.\n"
        "- content: a short, self-contained statement written in third person about them "
        '(e.g. "Prefers concise, direct communication.").\n'
        "- explicitness: 'explicit' if they stated it directly, 'inferred' if you are reading "
        "between the lines.\n"
        "- confidence: 0.0-1.0, how sure you are this is true and durable.\n"
        "- sensitivity_tier: T2 for ordinary preferences/goals/routines; T3 for health, "
        "financial account detail, government ID, sexual orientation, immigration status, or "
        "legal matters — when in doubt between T2 and T3, choose T3.\n"
        "- rationale_code: one of USER_EXPLICIT, REPEATED_PREFERENCE, INFERRED_FROM_OUTCOME."
    )
    prompt = f'Person: {full_name}\n\nWhat they just said:\n{source_text}' + existing_block

    provider = get_model_provider()
    response = provider.chat([{'role': 'user', 'content': prompt}], system=system_prompt)

    try:
        parsed = json.loads(response)
        candidates = parsed.get('candidates', [])
        if not isinstance(candidates, list):
            candidates = []
    except json.JSONDecodeError:
        candidates = []

    return {'candidates': candidates}


_GRAPH = single_node_graph('extract_memories', _extract_memories)


class Hippocampus:
    """Encodes experience into candidate durable memory (ADD §8). One node,

    one job: `extract_memories`. What used to be `SmartAgent._extract_memories`.
    """

    name = 'hippocampus'

    def plan(self, goal: str) -> list[PlanStep]:
        payload = json.loads(goal)
        return [
            PlanStep(
                tool='hippocampus',
                operation='extract_memories',
                risk_class=RiskClass.READ_ONLY,
                args=payload,
            )
        ]

    def execute_step(self, step: PlanStep) -> dict[str, Any]:
        return run(_GRAPH, step.args)
