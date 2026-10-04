from __future__ import annotations

import json
from typing import Any

from ..model_gateway import get_model_provider
from ..workflow.models import PlanStep
from ..workflow.state import RiskClass
from pathlib import Path

from . import _shared
from ._graph import router_graph, run

_PROMPTS_DIR = Path(__file__).parent / 'prompts'


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


# The Context Pack sections Brain 1 compiles, in the fixed order of the Speak
# prompt's layers (Building_Brain2.md §9.2). Empty sections are left out.
_PACK_SECTIONS = (
    ('who', 'WHO THEY ARE'),
    ('goal', 'THEIR GOAL'),
    ('today', 'THEIR WORLD TODAY'),
    ('loves', 'WHAT YOU KNOW ABOUT THEIR LIFE'),
    ('story', 'STORY SO FAR'),
    ('works', 'WHAT WORKS FOR THEM / WHAT TO AVOID'),
)


def _speak(payload: dict[str, Any]) -> dict[str, Any]:
    """Brain 2's Speak step (Building_Brain2.md §9.3) — writes ONE chat reply.

    Everything about *what* to say has already been decided: Brain 1's
    Context Pack says who this person is and what's going on; the plan says
    what this reply should do. This node only turns that into a short,
    natural message in the persona's voice. The conversation is sent as real
    user/assistant turns so the model can see what it already said. Plain
    text out — no JSON — so there is no format for the model to fight.

    `rewrite_feedback`, when present, lists why the previous attempt failed
    Brain 2's Check; the model gets exactly one chance to fix it.
    """
    pack: dict[str, str] = payload.get('context_pack') or {}
    first_name = (pack.get('first_name') or 'them').strip()
    plan = (payload.get('plan') or '').strip()
    feedback = (payload.get('rewrite_feedback') or '').strip()

    voice = _prompt_file('voice.md').replace('{first_name}', first_name)
    sections = [f'{title}\n{pack[key].strip()}' for key, title in _PACK_SECTIONS if (pack.get(key) or '').strip()]
    system_prompt = '\n\n'.join(
        [voice, *sections]
        + ([f'YOUR PLAN FOR THIS REPLY\n{plan}'] if plan else [])
        + [_prompt_file('style.md'), _prompt_file('examples/default.md')]
        + ([f'YOUR LAST DRAFT WAS REJECTED BECAUSE: {feedback}. Write a new reply that fixes this.'] if feedback else [])
        + ['Reply with only the message itself.']
    )

    messages = _as_turns(payload.get('conversation') or [], payload.get('latest_message') or '')
    response = get_model_provider('large').chat(messages, system=system_prompt)
    return {'content': _clean_reply(response, first_name), 'example_replies': _example_replies()}


def _as_turns(conversation: list[dict[str, str]], latest_message: str) -> list[dict[str, str]]:
    """Real chat turns: alternating, starting and ending with the person.

    Consecutive same-role turns are merged (some providers reject them). When
    there is no new message from the person — a proactive check-in — the last
    turn says so plainly instead of inventing words for them.
    """
    turns = [
        {'role': 'assistant' if t.get('role') == 'assistant' else 'user', 'content': (t.get('content') or '').strip()}
        for t in conversation
        if (t.get('content') or '').strip()
    ]
    latest = latest_message.strip()
    turns.append({'role': 'user', 'content': latest or "(They haven't replied since your last message.)"})

    merged: list[dict[str, str]] = []
    for turn in turns:
        if merged and merged[-1]['role'] == turn['role']:
            merged[-1]['content'] += '\n' + turn['content']
        else:
            merged.append(dict(turn))
    if merged[0]['role'] == 'assistant':
        merged.insert(0, {'role': 'user', 'content': '(Conversation start.)'})
    return merged


def _clean_reply(text: str, first_name: str) -> str:
    """Strips wrapping the model sometimes adds around the message itself."""
    reply = (text or '').strip()
    for prefix in ('Brain 2:', 'You:', 'Reply:', f'{first_name}:'):
        if reply.lower().startswith(prefix.lower()):
            reply = reply[len(prefix):].strip()
    if len(reply) >= 2 and reply[0] == reply[-1] and reply[0] in '"“”\'':
        reply = reply[1:-1].strip()
    return reply


def _prompt_file(name: str) -> str:
    return (_PROMPTS_DIR / name).read_text().strip()


def _example_replies() -> list[str]:
    """The example lines, so Brain 2's Check can reject a copied example."""
    return [line[len('You:'):].strip().strip('"') for line in _prompt_file('examples/default.md').splitlines() if line.startswith('You:')]


_GRAPH = router_graph({'profile_narrative': _profile_narrative, 'speak': _speak}, default='profile_narrative')


class Broca:
    """Speech production (ADD §8) — turns an already-reasoned understanding

    into the words Brain 2 actually says. Two operations:
    - `speak`: the chat reply (Brain 2's Speak step, Building_Brain2.md §9.3).
    - `profile_narrative`: a durable Profile entry draft (kept for profile
      proposals, which become separate from chat in Brain 2 Phase E).
    """

    name = 'broca'

    def plan(self, goal: str) -> list[PlanStep]:
        payload = json.loads(goal)
        return [
            PlanStep(
                tool='broca',
                operation=payload.get('operation', 'profile_narrative'),
                risk_class=RiskClass.READ_ONLY,
                args=payload,
            )
        ]

    def execute_step(self, step: PlanStep) -> dict[str, Any]:
        return run(_GRAPH, step.args)
