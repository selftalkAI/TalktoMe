from __future__ import annotations

import json
from typing import Any

from ..model_gateway import get_model_provider
from ..workflow.models import PlanStep
from ..workflow.state import RiskClass
from . import _shared
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
    who_lines = _shared.profile_lines(payload)
    domain = payload.get('domain', 'this')
    title = payload.get('title')
    target_minutes = payload.get('target_minutes')
    streak = payload.get('streak')
    support_message = (payload.get('support_message') or '').strip()
    user_reflection = (payload.get('user_reflection') or '').strip()
    previous_entry = (payload.get('previous_entry_content') or '').strip()
    conversation_history = (payload.get('conversation_history') or '').strip()
    domain_memories: list[str] = payload.get('domain_memories') or []
    world_knowledge = (payload.get('world_knowledge') or '').strip()
    checkin_mode = bool(payload.get('checkin_mode'))
    escalation_level = int(payload.get('escalation_level') or 0)

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
        "Tone: warm and specific, like someone who actually knows this person and is on their "
        "side — never clinical, curt, or scolding, and never a flat status report ('you have "
        "not done X, your commitment is unclear'). If a profile is given below, use their first "
        "name where it feels natural and let their actual context (age, location, interests, "
        "their own quote) shape the voice, not just the domain facts. Being short is not an "
        "excuse to be cold — a two-sentence message can still sound like it cares.\n\n"
        "Write in second person ('you'). LIMIT: "
        + ("3-4 short sentences, under 70 words total" if checkin_mode else "2-3 short sentences, under 55 words total")
        + " — this renders as one chat bubble, not a paragraph; if you're restating what they "
        "already said, you've gone too long, cut it. Say the one thing that actually matters: "
        "the real pattern or the one concrete idea, not both elaborated. If a previous version "
        "of this domain's Profile is given, treat this as building on it, not repeating it.\n\n"
        + (
            "IMPORTANT — a conversation so far is given below. Ground your reply in the WHOLE "
            "exchange, not just the latest line alone — if they just asked 'how do I do that?' "
            "or similar, answer in relation to whatever YOU said earlier that they're reacting "
            "to, don't treat their message as a standalone thought. If your own most recent "
            "message in it hasn't been responded to with anything new, don't just repeat it — "
            "build on it or offer a genuinely different, more specific angle.\n\n"
            if conversation_history
            else ""
        )
        + (
            "CHECK-IN MODE — this message either (a) follows a real silence from them, or (b) "
            "follows them saying they didn't/couldn't do it. Your job here is specifically to "
            "re-engage, not to log a status update. Do THREE things, briefly, in order: "
            "(1) using their actual profile below (age, health/fitness context, interests — only "
            "what's actually given, never invented), name ONE concrete, specific reason reaching "
            "this goal would genuinely matter to someone in their situation — a real benefit, not "
            "generic encouragement; (2) if they said why it didn't happen, acknowledge that "
            "specific reason, don't ignore it; (3) end with ONE direct, concrete question asking "
            "exactly what they actually did (or will do) — the question is mandatory, this message "
            "is incomplete without it.\n"
            + (
                f"This is attempt #{escalation_level + 1} to re-engage them — your last "
                f"{escalation_level} message(s) on this got no response. Do NOT reuse the same "
                "benefit, angle, or phrasing as before (check the conversation above for what "
                "you already tried) — find a genuinely different, more specific, more compelling "
                "angle this time. Repeating yourself is the one thing guaranteed not to work.\n\n"
                if escalation_level > 0
                else "\n"
            )
            if checkin_mode
            else ""
        )
        + 'Respond with strict JSON only, no markdown fencing, matching exactly this shape: {"content": "..."}.'
    )
    prompt = (
        (('Who they are:\n' + '\n'.join(who_lines) + '\n\n') if who_lines else '')
        + f'Domain: {domain}\n'
        + '\n'.join(grounding_lines)
        + (f'\n\nConversation so far (oldest to newest):\n{conversation_history}' if conversation_history else '')
        + f"\n\nWhat this person just said: {user_reflection or '(nothing recorded)'}"
        + (f'\n\nPrevious Profile entry for this domain:\n{previous_entry}' if previous_entry else '')
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
