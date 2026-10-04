from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..model_gateway import get_model_provider
from ..workflow.models import PlanStep
from ..workflow.state import RiskClass
from . import _shared, persona
from ._graph import router_graph, run

_PROMPTS_DIR = Path(__file__).parent / 'prompts'


def _profile_narrative(payload: dict[str, Any]) -> dict[str, Any]:
    """Drafts ONE durable Profile entry for a life area (ADD §6.1) — the
    rare, separate artifact Brain 2's Remember step proposes when something
    lasting was learned (ADR-022). Not a chat reply: no question, no advice,
    no pep talk. A draft only; the person must accept it (ADR-014).

    Grounded only in what is given: who they are, what they've told us in
    this area (never T3 — the caller filters), their goal history if any, and
    what they just said. `rewrite_feedback` lists why the last draft failed
    Brain 2's Check.
    """
    who_lines = _shared.profile_lines(payload)
    first_name = (payload.get('full_name') or 'them').split()[0]
    memories: list[str] = payload.get('domain_memories') or []
    previous = (payload.get('previous_entry_content') or '').strip()
    feedback = (payload.get('rewrite_feedback') or '').strip()

    facts: list[str] = []
    if payload.get('title'):
        facts.append(f"Goal: {payload['title']}, aiming for {payload.get('target_minutes')} minutes a day.")
        if payload.get('streak'):
            facts.append(f"{payload['streak']} days in a row under the target at the time.")
    facts += [f'- {m}' for m in memories]
    if (payload.get('user_reflection') or '').strip():
        facts.append(f"What they said: {payload['user_reflection'].strip()}")

    system_prompt = (
        f"Write a short entry for {first_name}'s own profile about one area of their life "
        f"('{payload.get('domain', 'this area')}') — an honest snapshot of where they are and how they're "
        'growing, written to them in the second person, the way someone who knows them well would put it. '
        '2 or 3 sentences, under 80 words. Use only the facts given. No advice, no questions, no praise '
        'words like amazing or incredible, no headings or lists. If little is known, say so simply.'
        + (f'\n\nThe current accepted entry (build on it, do not repeat it):\n{previous}' if previous else '')
        + (f'\n\nYOUR LAST DRAFT WAS REJECTED BECAUSE: {feedback}. Fix this.' if feedback else '')
        + '\n\nReply with only the entry text.'
    )
    prompt = 'Who they are:\n' + '\n'.join(who_lines) + '\n\nWhat is known in this area:\n' + ('\n'.join(facts) or '(nothing yet)')
    response = get_model_provider('large').chat([{'role': 'user', 'content': prompt}], system=system_prompt)
    return {'content': _clean_reply(response, first_name)}


# The Context Pack sections Brain 1 compiles, in the fixed order of the Speak
# prompt's layers (Building_Brain2.md §9.2). Empty sections are left out.
_PACK_SECTIONS = (
    ('who', 'WHO THEY ARE'),
    ('goal', 'THEIR GOAL'),
    ('today', 'THEIR WORLD TODAY'),
    ('loves', 'WHAT YOU KNOW ABOUT THEIR LIFE'),
    ('story', 'STORY SO FAR'),
    ('understanding', 'WHAT YOU UNDERSTAND ABOUT THEIR SITUATION RIGHT NOW'),
    ('works', 'WHAT WORKS FOR THEM / WHAT TO AVOID'),
    ('principles', 'WHAT EXPERTS KNOW THAT MIGHT HELP (offer at most one, as an option, in your own words)'),
    ('hooks', 'WAYS TO TIE THIS TO THEIR LIFE TODAY (use at most one, only if it truly fits)'),
    ('unknowns', "THINGS YOU DON'T KNOW YET"),
)


def _speak(payload: dict[str, Any]) -> dict[str, Any]:
    """Brain 2's Speak step (Building_Brain2.md §9.3) — writes ONE chat reply,
    in the persona Brain 1 picked (`persona`: voice + expertise ids).

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
    voice, exp = persona.resolve(payload.get('persona'))

    base = (
        _prompt_file('base.md')
        .replace('{first_name}', first_name)
        .replace('{voice_identity}', voice['identity'].strip().replace('{first_name}', first_name))
        .replace('{expertise_in_words}', persona.expertise_text(exp))
    )
    sections = [f'{title}\n{pack[key].strip()}' for key, title in _PACK_SECTIONS if (pack.get(key) or '').strip()]
    system_prompt = '\n\n'.join(
        [base, *sections]
        + ([f'YOUR PLAN FOR THIS REPLY\n{plan}'] if plan else [])
        + [_prompt_file('style.md'), persona.examples_text(voice)]
        + ([f'YOUR LAST DRAFT WAS REJECTED BECAUSE: {feedback}. Write a new reply that fixes this.'] if feedback else [])
        + ['Reply with only the message itself.']
    )

    messages = _as_turns(payload.get('conversation') or [], payload.get('latest_message') or '')
    response = get_model_provider('large').chat(messages, system=system_prompt)
    return {
        'content': _clean_reply(response, first_name),
        'example_replies': persona.example_replies(voice),
        'persona': {'voice': voice['id'], 'expertise': exp['id']},
    }


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


_GRAPH = router_graph({'profile_narrative': _profile_narrative, 'speak': _speak}, default='profile_narrative')


class Broca:
    """Speech production (ADD §8) — turns an already-reasoned understanding

    into the words Brain 2 actually says. Two operations:
    - `speak`: the chat reply, in the chosen persona (Building_Brain2.md §9.3).
    - `profile_narrative`: a durable Profile entry draft — proposed rarely and
      separately from chat (ADR-022).
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
