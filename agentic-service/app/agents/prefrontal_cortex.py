from __future__ import annotations

import json
from typing import Any

from ..model_gateway import get_model_provider
from ..workflow.models import PlanStep
from ..workflow.state import RiskClass
from . import _shared
from ._graph import router_graph, run

# Prefrontal Cortex: higher-order reasoning (ADD §8) — connecting past to
# present and deciding what's needed next. Three genuinely different
# operations, not steps of one pipeline, so this agent's graph is a real
# router over three nodes rather than a single linear flow — the same
# distinction `router_graph` exists to express.


def _reflect_moment(payload: dict[str, Any]) -> dict[str, Any]:
    """Connects one new moment to this person's own past — grounded only in

    their own moments and durable memories, never outside facts or advice.

    Also grounded in who they actually are (age, location, interests — real,
    self-stated facts from their own profile, not outside knowledge) so the
    reflection can be calibrated to them, not generic. This is a different
    kind of input than World Knowledge: these are facts Brain 1 already gave
    us about themselves, not expertise fetched from outside.
    """
    moment = payload['moment']
    past_moments: list[dict[str, Any]] = payload.get('past_moments', [])
    relevant_memories: list[dict[str, Any]] = payload.get('relevant_memories', [])
    context_lines = [_shared.format_moment(m) for m in past_moments]
    memory_lines = [f"- ({m.get('type')}) {m.get('content')}" for m in relevant_memories]
    who_lines = _shared.profile_lines(payload)

    system_prompt = (
        "You are reflecting ONE person's own thoughts back to them. Everything you say must be "
        "grounded ONLY in the moments and durable memories listed below, which are all authored "
        "by or true of this same person, plus the basic facts about who they are (age, location, "
        "interests) also listed below — those are real, self-stated facts, not outside knowledge, "
        "so you may use them to calibrate tone and relevance, but NEVER to assume anything about "
        "their life you weren't actually told (e.g. knowing their age is not license to assume "
        "what a person that age is 'usually' going through). You must NEVER introduce outside "
        "facts, other people's opinions, general knowledge, or generic advice that isn't grounded "
        "in their own words. If nothing in their past connects to today's moment, say plainly that "
        "this feels new rather than inventing a connection. Write directly to them, in second "
        "person ('you').\n\n"
        "Before anything else: if today's moment carries real emotional weight (tired, sick, "
        "upset, anxious, low) — acknowledge that feeling directly and specifically, in your own "
        "words, before doing anything else. A pattern-connection ('this is new', 'this echoes "
        "X') is a secondary job; noticing how they actually feel comes first. Do not default to "
        "reporting on novelty when there's a real feeling sitting right there to respond to.\n\n"
        + (
            "THERE IS NO PAST HISTORY FOR THIS PERSON YET — the 'past moments' list below is "
            "empty. This means you MUST NOT reference any prior event, pattern, or occurrence, "
            "under any phrasing — no 'like when', 'again', 'lately', 'you've been', 'this time', "
            "or any implied history. You have exactly the one moment below and nothing else. "
            "Acknowledging their feeling means responding to what's written below, in this "
            "moment only — it does NOT mean inventing a past to make the feeling sound more "
            "understood. If you catch yourself describing any event, activity, or circumstance "
            "that isn't in the text below, delete it before responding.\n\n"
            if not context_lines
            else ""
        )
        + "Hard length limit: 1-2 sentences. Not three paragraphs compressed into one — actually "
        "1-2 sentences, short enough to read in three seconds. If you're restating what they just "
        "said in different words, you've already gone too long — cut it.\n\n"
        "Banned moves, because they're what makes a reflection feel padded and forgettable: "
        "restating their own moment back to them ('it sounds like you...', 'you're acknowledging "
        "...'), narrating your own reasoning process ('one observation is...', 'this could be "
        "influencing...'), and hedging ('might be', 'likely', 'could be a good foundation'). Just "
        "say the specific thing, plainly, like a friend who actually noticed something — not a "
        "therapist summarizing a session.\n\n"
        "Pick ONE real, specific move — acknowledge the feeling, or name a real connection to "
        "their own past, or (only if truly nothing fits) say plainly this is new — and either "
        "state it as a sharp observation or ask one direct question about it. Never stack more "
        "than one move. Never both a summary AND an observation AND a question — pick one and stop."
        + _shared.narrative_focus_clause(payload)
    )
    prompt = (
        (('Who they are:\n' + '\n'.join(who_lines) + '\n\n') if who_lines else '')
        + 'Your past moments (oldest to newest):\n'
        + ('\n'.join(context_lines) if context_lines else '(no earlier moments yet — this is your first.)')
        + ('\n\nWhat we durably know about them:\n' + '\n'.join(memory_lines) if memory_lines else '')
        + f"\n\nToday's moment (felt: {moment.get('mood') or 'unspecified'}): {moment['content']}"
        + "\n\nReflect on today's moment."
    )

    provider = get_model_provider()
    response_text = provider.chat([{'role': 'user', 'content': prompt}], system=system_prompt)
    return {'reflection': response_text, 'referenced_past_count': len(context_lines)}


def _evolution_narrative(payload: dict[str, Any]) -> dict[str, Any]:
    """Summarizes how this person has changed over a period — grounded only

    in their own moments from that period.
    """
    moments: list[dict[str, Any]] = payload.get('moments', [])
    if len(moments) < 2:
        return {
            'narrative': (
                "There isn't enough history yet to see a pattern — keep capturing moments "
                "and this will fill in."
            )
        }

    context_lines = [_shared.format_moment(m) for m in moments]
    system_prompt = (
        "You are summarizing how ONE person has changed over a period of time, using ONLY the "
        "moments they themselves recorded below. Never introduce outside facts, other people, or "
        "generic self-help language. Write 3-5 sentences, directly to them ('you'), noting any real "
        "shifts in mood, recurring themes, or a change in how they talk about the same topic over "
        "time. If there's no clear shift, say so honestly instead of inventing one."
        + _shared.narrative_focus_clause(payload)
    )
    prompt = 'Moments from this period (oldest to newest):\n' + '\n'.join(context_lines)

    provider = get_model_provider()
    response_text = provider.chat([{'role': 'user', 'content': prompt}], system=system_prompt)
    return {'narrative': response_text}


def _suggest_next_step(payload: dict[str, Any]) -> dict[str, Any]:
    """Decides what this person actually needs right now, acting on Sensory

    Cortex's understanding — deciding and suggesting is this agent's job,
    not the interpreting agent's.
    """
    full_name = (payload.get('full_name') or '').strip() or 'there'
    interests: list[str] = payload.get('interests') or []
    mood_summary = (payload.get('mood_summary') or '').strip()
    context_notes = (payload.get('context_notes') or '').strip()
    recent_moments: list[dict[str, Any]] = payload.get('recent_moments') or []

    lines = [f'Name: {full_name}']
    if interests:
        lines.append(f"Interests: {', '.join(interests)}")
    if mood_summary:
        lines.append(f'How they seem to be feeling right now: {mood_summary}')
    if context_notes:
        lines.append(f'Specific things they mentioned: {context_notes}')
    if recent_moments:
        lines.append('Their own recent moments (oldest to newest):')
        lines.extend(_shared.format_moment(m) for m in recent_moments)

    system_prompt = (
        "You are deciding what ONE person needs right now, using ONLY what another agent "
        "already understood about them below — their profile, how they currently seem to "
        "be feeling, and their own past moments if any. Never introduce outside facts, "
        "other people, or generic self-help language; if they seem to be struggling, be "
        "gentle and specific rather than falsely upbeat. Respond with strict JSON only, no "
        'markdown fencing, matching exactly this shape: {"welcome_message": "...", '
        '"suggested_first_action": "..."}.\n'
        '- welcome_message: 1-2 sentences, second person, using their first name, that '
        "acknowledge how they say they're feeling right now (not a generic greeting).\n"
        '- suggested_first_action: one concrete, specific thing to capture as a moment '
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
    persona = payload.get('persona') or {}
    pack: dict[str, str] = payload.get('context_pack') or {}
    reading = payload.get('reading') or {}
    known = '\n'.join(f'{k}: {v}' for k, v in pack.items() if k != 'first_name' and (v or '').strip())

    system_prompt = (
        "You plan — you do not write — the next reply to someone you know well. "
        f"You are speaking as: {persona.get('voice', 'friend')}, with {persona.get('expertise', 'general life')} know-how. "
        "An excellent coach understands before advising, uses the person's own reasons, offers an idea "
        "only as an option, and asks at most one question. Pick what they need most right now.\n"
        "Return JSON only:\n"
        '{"stance": one of ' + '|'.join(STANCES) + ',\n'
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
    return _normalise_plan(_shared.parse_json_object(response))


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


_GRAPH = router_graph(
    {
        'reflect_moment': _reflect_moment,
        'evolution_narrative': _evolution_narrative,
        'suggest_next_step': _suggest_next_step,
        'plan_reply': _plan_reply,
    },
    default='reflect_moment',
)


class PrefrontalCortex:
    """Higher-order reasoning (ADD §8): connects past to present, decides

    what's needed next. Four nodes routed by `operation`: `reflect_moment`,
    `evolution_narrative`, `suggest_next_step`, and `plan_reply` (Brain 2's
    Decide step).
    """

    name = 'prefrontal_cortex'

    def plan(self, goal: str) -> list[PlanStep]:
        payload = json.loads(goal)
        operation = payload.get('mode') or payload.get('operation') or 'reflect_moment'
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
