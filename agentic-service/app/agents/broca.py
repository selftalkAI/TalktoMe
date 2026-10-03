from __future__ import annotations

import json
from typing import Any

from ..model_gateway import get_model_provider
from ..workflow.models import PlanStep
from ..workflow.state import RiskClass
from ._graph import run, single_node_graph


def _profile_narrative(payload: dict[str, Any]) -> dict[str, Any]:
    """Composes the final spoken/written Profile entry (ADD §6.1/§8.2) —

    literally the speech-production job: everything upstream (Amygdala's
    noticing, Prefrontal Cortex's reasoning, Brain 1's own reflection) has
    already happened; this only turns it into words. A DRAFT, grounded only
    in what's given below; it is Orchestration's job (never this function's)
    to hold it as `proposed` until Brain 1 explicitly accepts it (ADR-014) —
    this has no opinion on acceptance and no path to write anything itself.

    Two grounding shapes feed this, and either or both may be present:
    - Intention grounding (the goal-adherence domain): title/target/streak/
      support_message, when this proposal came from a shortfall in a
      tracked intention.
    - Domain-memory grounding (every other domain — skill, emotion,
      learning, reading, ...): `domain_memories`, this domain's own
      durable, active memories, when there is no intention driving this.

    A third, optional input — `world_knowledge` (ADD §8.2 step 5-6) — is the
    one piece of outside information this function is allowed to use. It
    must be presented as outside information being offered, never folded in
    as if it were something Brain 1 already knew or said themselves.
    """
    domain = payload.get('domain', 'this')
    title = payload.get('title')
    target_minutes = payload.get('target_minutes')
    streak = payload.get('streak')
    support_message = (payload.get('support_message') or '').strip()
    user_reflection = (payload.get('user_reflection') or '').strip()
    previous_entry = (payload.get('previous_entry_content') or '').strip()
    pending_draft = (payload.get('pending_draft_content') or '').strip()
    domain_memories: list[str] = payload.get('domain_memories') or []
    world_knowledge = (payload.get('world_knowledge') or '').strip()

    grounding_lines: list[str] = []
    if title:
        grounding_lines.append(f'Intention: "{title}", target: {target_minutes} min/day')
        if streak is not None:
            grounding_lines.append(f'Consecutive days under target when this came up: {streak}')
        grounding_lines.append(f"Brain 2's support offer: {support_message or '(none offered)'}")
    if domain_memories:
        grounding_lines.append('What is durably known about them in this domain:')
        grounding_lines.extend(f'- {m}' for m in domain_memories)
    if not grounding_lines:
        grounding_lines.append('(no prior grounding for this domain — this is the first entry)')

    system_prompt = (
        "You are writing ONE short, durable entry for this person's own Profile in a "
        "specific life domain — a synthesized account of who they are or how they're "
        "growing in that domain, written so it could genuinely be read back to them, or "
        "one day to someone who loves them, and still ring true. Ground it ONLY in what is "
        "given below — the intention/shortfall history if given, the durable memories in "
        "this domain if given, and — most importantly — what this person actually said in "
        "their own words. Never invent a resolution, a feeling, a skill level, or a lesson "
        "they didn't actually express or that isn't in the memories given. If they didn't "
        "really resolve anything, say that honestly rather than manufacturing a tidy arc.\n\n"
        "If outside expert knowledge is given below, you may offer it as ONE concrete, "
        "optional idea — clearly framed as something you're bringing to them ('one thing "
        "that might help:', 'worth knowing:'), never stated as if it were their own "
        "conclusion or something they already tried. It is a suggestion, not an "
        "instruction — never phrase it as telling them what to do.\n\n"
        "Write in second person ('you'). HARD LIMIT: 2 sentences, under 40 words total — this "
        "renders as one chat bubble, not a paragraph; if you're restating what they already "
        "said, you've gone too long, cut it. Say the one thing that actually matters: the real "
        "pattern or the one concrete idea, not both elaborated. If a previous version of this "
        "domain's Profile is given, treat this as building on it, not repeating it.\n\n"
        + (
            "IMPORTANT — this is a follow-up: the draft below under 'Your last message (still "
            "unanswered)' is something you already said, and the person hasn't accepted it or "
            "replied to it yet. Do NOT repeat it or rephrase the same point. Either (a) briefly "
            "check in — acknowledge you're still there, no pressure — or (b), if their latest "
            "words below give you something new to go on, offer a genuinely DIFFERENT angle or "
            "a better, more specific idea than last time.\n\n"
            if pending_draft
            else ""
        )
        + 'Respond with strict JSON only, no markdown fencing, matching exactly this shape: {"content": "..."}.'
    )
    prompt = (
        f'Domain: {domain}\n'
        + '\n'.join(grounding_lines)
        + f"\nWhat this person actually said: {user_reflection or '(nothing recorded)'}"
        + (f'\n\nPrevious Profile entry for this domain:\n{previous_entry}' if previous_entry else '')
        + (f'\n\nYour last message (still unanswered — do not repeat it):\n{pending_draft}' if pending_draft else '')
        + (f'\n\nOutside expert knowledge available to offer (optional, not required to use):\n{world_knowledge}' if world_knowledge else '')
    )

    provider = get_model_provider()
    response = provider.chat([{'role': 'user', 'content': prompt}], system=system_prompt)

    try:
        parsed = json.loads(response)
    except json.JSONDecodeError:
        parsed = {'content': response.strip()}

    return {'content': parsed.get('content', '')}


_GRAPH = single_node_graph('profile_narrative', _profile_narrative)


class Broca:
    """Speech production (ADD §8) — turns an already-reasoned understanding

    into the words Brain 2 actually says. One node, one job:
    `profile_narrative`. What used to be `SmartAgent._brain2_profile_narrative`.
    """

    name = 'broca'

    def plan(self, goal: str) -> list[PlanStep]:
        payload = json.loads(goal)
        return [
            PlanStep(
                tool='broca',
                operation='profile_narrative',
                risk_class=RiskClass.READ_ONLY,
                args=payload,
            )
        ]

    def execute_step(self, step: PlanStep) -> dict[str, Any]:
        return run(_GRAPH, step.args)
