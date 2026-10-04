from __future__ import annotations

import json
from typing import Any

from ..model_gateway import get_model_provider
from ..workflow.models import PlanStep
from ..workflow.state import RiskClass
from . import _shared
from ._graph import router_graph, run


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


INTENTS = ('sharing', 'asking', 'progress', 'setback', 'venting', 'pushback', 'smalltalk')
CHANGE_TALK = (
    'desire', 'ability', 'reason', 'need', 'commitment', 'activation', 'taking_steps', 'sustain', 'discord', 'none'
)


def _read_message(payload: dict[str, Any]) -> dict[str, Any]:
    """Brain 2's Understand step (Building_Brain2.md §9.4.1): a structured
    read of the person's latest message, so the Decide step plans from what
    they actually said — including whether they did the thing today, which is
    what stops a reply from congratulating someone who just said they missed it.

    Interpretation only: no advice, no decisions. Unknowns stay unknown.
    """
    latest = (payload.get('latest_message') or '').strip()
    if not latest:
        return _empty_reading()

    system_prompt = (
        'Read the latest message in this conversation and describe it. You are only '
        'understanding — never advising. Return JSON only:\n'
        '{"intent": one of ' + '|'.join(INTENTS) + ',\n'
        ' "feeling": one or two words, or "unknown",\n'
        ' "change_talk": one of ' + '|'.join(CHANGE_TALK) + ',\n'
        ' "asked_question": their question in their words, or null,\n'
        ' "did_it_today": true, false, or null if they did not say,\n'
        ' "minutes_today": a number only if they said one for today, else null,\n'
        ' "reason_given": why it did or did not happen in their words, or null,\n'
        ' "new_facts": [facts about their life they just shared, in their words]}'
    )
    prompt = _shared.conversation_text(payload.get('conversation') or [], latest)
    response = get_model_provider('small').chat([{'role': 'user', 'content': prompt}], system=system_prompt)
    return _normalise_reading(_shared.parse_json_object(response), latest)


def _empty_reading() -> dict[str, Any]:
    return {
        'intent': 'smalltalk', 'feeling': 'unknown', 'change_talk': 'none', 'asked_question': None,
        'did_it_today': None, 'minutes_today': None, 'reason_given': None, 'new_facts': [],
    }


def _normalise_reading(parsed: dict[str, Any], latest: str) -> dict[str, Any]:
    """Keeps only valid values; anything the model got wrong falls back to
    'unknown' rather than a guess. A literal '?' in the message always counts
    as a question, whatever the model said."""
    reading = _empty_reading()
    if parsed.get('intent') in INTENTS:
        reading['intent'] = parsed['intent']
    if parsed.get('change_talk') in CHANGE_TALK:
        reading['change_talk'] = parsed['change_talk']
    if isinstance(parsed.get('feeling'), str) and parsed['feeling'].strip():
        reading['feeling'] = parsed['feeling'].strip()[:40]
    question = parsed.get('asked_question')
    if isinstance(question, str) and question.strip() and question.strip().lower() != 'null':
        reading['asked_question'] = question.strip()
    elif '?' in latest:
        reading['asked_question'] = latest
    if isinstance(parsed.get('did_it_today'), bool):
        reading['did_it_today'] = parsed['did_it_today']
    if isinstance(parsed.get('minutes_today'), (int, float)) and parsed['minutes_today'] >= 0:
        reading['minutes_today'] = int(parsed['minutes_today'])
    if isinstance(parsed.get('reason_given'), str) and parsed['reason_given'].strip().lower() not in ('', 'null'):
        reading['reason_given'] = parsed['reason_given'].strip()
    if isinstance(parsed.get('new_facts'), list):
        reading['new_facts'] = [f.strip() for f in parsed['new_facts'] if isinstance(f, str) and f.strip()][:5]
    if reading['intent'] == 'setback' and reading['did_it_today'] is None:
        reading['did_it_today'] = False
    return reading


_GRAPH = router_graph({'understand': _understand, 'read_message': _read_message}, default='understand')


class SensoryCortex:
    """Interprets what the person said into structured signal (ADD §8).

    Two operations: `understand` (the onboarding check-in's mood/context/
    focus) and `read_message` (Brain 2's Understand step for every reply).
    Split from Thalamus because relaying and interpreting are different jobs.
    """

    name = 'sensory_cortex'

    def plan(self, goal: str) -> list[PlanStep]:
        payload = json.loads(goal)
        return [
            PlanStep(
                tool='sensory_cortex',
                operation=payload.get('operation', 'understand'),
                risk_class=RiskClass.READ_ONLY,
                args=payload,
            )
        ]

    def execute_step(self, step: PlanStep) -> dict[str, Any]:
        return run(_GRAPH, step.args)
