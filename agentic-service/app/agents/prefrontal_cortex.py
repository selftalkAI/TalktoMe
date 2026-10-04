from __future__ import annotations

import json
from typing import Any

from ..model_gateway import get_model_provider
from ..workflow.models import PlanStep
from ..workflow.state import RiskClass
from . import _shared, persona
from ._graph import router_graph, run

# Prefrontal Cortex: higher-order reasoning (ADD §8) — connecting past to
# present and deciding what's needed next. Three genuinely different
# operations, not steps of one pipeline, so this agent's graph is a real
# router over three nodes rather than a single linear flow — the same
# distinction `router_graph` exists to express.


def _suggest_next_step(payload: dict[str, Any]) -> dict[str, Any]:
    """Decides what this person actually needs right now, acting on Sensory

    Cortex's understanding — deciding and suggesting is this agent's job,
    not the interpreting agent's.
    """
    full_name = (payload.get('full_name') or '').strip() or 'there'
    interests: list[str] = payload.get('interests') or []
    mood_summary = (payload.get('mood_summary') or '').strip()
    context_notes = (payload.get('context_notes') or '').strip()

    lines = [f'Name: {full_name}']
    if interests:
        lines.append(f"Interests: {', '.join(interests)}")
    if mood_summary:
        lines.append(f'How they seem to be feeling right now: {mood_summary}')
    if context_notes:
        lines.append(f'Specific things they mentioned: {context_notes}')

    system_prompt = (
        "You are deciding what ONE person needs right now, using ONLY what another agent "
        "already understood about them below — their profile, how they currently seem to "
        "be feeling. Never introduce outside facts, "
        "other people, or generic self-help language; if they seem to be struggling, be "
        "gentle and specific rather than falsely upbeat. Respond with strict JSON only, no "
        'markdown fencing, matching exactly this shape: {"welcome_message": "...", '
        '"suggested_first_action": "..."}.\n'
        '- welcome_message: 1-2 sentences, second person, using their first name, that '
        "acknowledge how they say they're feeling right now (not a generic greeting).\n"
        '- suggested_first_action: one concrete, specific thing they could talk to Brain 2 about '
        "today, grounded in their interests and current mood/context — never generic advice."
    )
    prompt = 'What is understood about this person right now:\n' + '\n'.join(lines)

    provider = get_model_provider()
    response = provider.chat([{'role': 'user', 'content': prompt}], system=system_prompt)

    try:
        parsed = json.loads(response)
    except json.JSONDecodeError:
        parsed = {'welcome_message': response.strip()}

    return {
        'welcome_message': parsed.get('welcome_message', ''),
        'suggested_first_action': parsed.get('suggested_first_action', ''),
    }


STANCES = ('listen', 'motivate', 'plan', 'teach', 'challenge', 'celebrate', 'mirror', 'ask')
MOVES = (
    'reflect', 'affirm', 'open_question', 'summarize', 'ask_permission',
    'offer_idea', 'celebrate', 'answer_question', 'follow_up', 'care',
)


def _plan_reply(payload: dict[str, Any]) -> dict[str, Any]:
    """Brain 2's Decide step (Building_Brain2.md §9.4.2): plans — never
    writes — the next reply, in the persona Brain 1 picked. Output is a small
    plan the Speak step turns into words; Orchestration's plan rules then
    enforce the hard limits (safety, one question, answer their question
    first), so nothing here needs to be trusted for those.
    """
    voice, exp = persona.resolve(payload.get('persona'))
    allowed = [s for s in voice.get('allowed_stances') or STANCES if s in STANCES]
    pack: dict[str, str] = payload.get('context_pack') or {}
    reading = payload.get('reading') or {}
    known = '\n'.join(f'{k}: {v}' for k, v in pack.items() if k != 'first_name' and (v or '').strip())

    system_prompt = (
        "You plan — you do not write — the next reply to someone you know well. "
        f"You are speaking as {voice['name']}, with know-how in {exp['name']}. "
        "An excellent coach understands before advising, uses the person's own reasons, offers an idea "
        "only as an option, and asks at most one question. Pick what they need most right now.\n"
        "Return JSON only:\n"
        '{"stance": one of ' + '|'.join(allowed) + ',\n'
        ' "moves": one or two of ' + '|'.join(MOVES) + ',\n'
        ' "question": the one question to ask, or null,\n'
        ' "idea": one small concrete idea to offer as an option, or null,\n'
        ' "why": one short sentence}'
    )
    prompt = (
        f'What you know about them:\n{known or "(very little yet)"}\n\n'
        f'Conversation:\n{_shared.conversation_text(payload.get("conversation") or [], payload.get("latest_message") or "")}\n\n'
        f'Your reading of their latest message: {json.dumps(reading)}'
    )
    response = get_model_provider('large').chat([{'role': 'user', 'content': prompt}], system=system_prompt)
    plan = _normalise_plan(_shared.parse_json_object(response))
    if plan['stance'] not in allowed:
        plan['stance'] = None  # this voice doesn't take that stance; the plan rules choose
    return plan


def _normalise_plan(parsed: dict[str, Any]) -> dict[str, Any]:
    moves = parsed.get('moves')
    if isinstance(moves, str):
        moves = [moves]
    moves = [m for m in (moves or []) if m in MOVES][:2]
    question = parsed.get('question')
    idea = parsed.get('idea')
    return {
        'stance': parsed.get('stance') if parsed.get('stance') in STANCES else None,
        'moves': moves,
        'question': question.strip() if isinstance(question, str) and question.strip().lower() not in ('', 'null') else None,
        'idea': idea.strip() if isinstance(idea, str) and idea.strip().lower() not in ('', 'null') else None,
        'why': parsed.get('why') if isinstance(parsed.get('why'), str) else '',
    }


def _find_patterns(payload: dict[str, Any]) -> dict[str, Any]:
    """Brain 1's Reflective mode (Building_Brain1.md §14.3, Scenario 8): looks
    across weeks of what the person said and did for a pattern THEY may not
    have noticed. Each pattern must be backed by at least two separate pieces
    of evidence quoted exactly from the items given; Orchestration re-checks
    those quotes and drops anything that isn't really there. A pattern is
    only ever a hypothesis to show them, never a fact about them.
    """
    items: list[str] = [i for i in payload.get('items') or [] if isinstance(i, str) and i.strip()]
    known: list[str] = payload.get('known_patterns') or []
    if len(items) < 3:
        return {'patterns': []}
    numbered = '\n'.join(f'[{n + 1}] {item}' for n, item in enumerate(items))
    system_prompt = (
        "You look across one person's notes from several weeks for a pattern they may not have noticed — "
        'e.g. a setback that keeps happening under the same circumstances, or something that reliably helps. '
        'Only report a pattern that at least two DIFFERENT notes clearly show. Never diagnose, never judge, '
        'never guess at causes the notes do not state. If there is no clear pattern, return none.\n'
        + (f'Already known (do not repeat): {"; ".join(known)}\n' if known else '')
        + 'Return JSON only: {"patterns": [{"pattern": "one plain sentence, written to them as you", '
        '"evidence": ["exact short phrase copied from a note", "exact short phrase from a different note"]}]} '
        '— at most 2 patterns.'
    )
    response = get_model_provider('large').chat([{'role': 'user', 'content': numbered}], system=system_prompt)
    parsed = _shared.parse_json_object(response)
    patterns = []
    for p in parsed.get('patterns') or []:
        if isinstance(p, dict) and isinstance(p.get('pattern'), str) and isinstance(p.get('evidence'), list):
            patterns.append({'pattern': p['pattern'].strip(), 'evidence': [e for e in p['evidence'] if isinstance(e, str)][:4]})
    return {'patterns': patterns[:2]}


_GRAPH = router_graph(
    {
        'suggest_next_step': _suggest_next_step,
        'plan_reply': _plan_reply,
        'find_patterns': _find_patterns,
    },
    default='suggest_next_step',
)


class PrefrontalCortex:
    """Higher-order reasoning (ADD §8): connects past to present, decides

    what's needed next. Routed by `operation`: `suggest_next_step` (the welcome), `plan_reply`
    (Brain 2's Decide step) and `find_patterns` (Brain 1's reflection).
    """

    name = 'prefrontal_cortex'

    def plan(self, goal: str) -> list[PlanStep]:
        payload = json.loads(goal)
        operation = payload.get('mode') or payload.get('operation') or 'suggest_next_step'
        return [
            PlanStep(
                tool='prefrontal_cortex',
                operation=operation,
                risk_class=RiskClass.READ_ONLY,
                args=payload,
            )
        ]

    def execute_step(self, step: PlanStep) -> dict[str, Any]:
        return run(_GRAPH, {**step.args, 'operation': step.operation})
