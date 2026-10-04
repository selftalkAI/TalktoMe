from __future__ import annotations

import re
from typing import Any

# Code rules applied after Brain 2's Decide step (Building_Brain2.md §7):
# the model proposes a plan, these rules make the parts that must never be
# left to a model deterministic — answer their question first, at most one
# question, no celebrating a missed day, no arguing with pushback, gentle
# on proactive check-ins — and turn the plan into plain words for Speak.

STANCES = ('listen', 'motivate', 'plan', 'teach', 'challenge', 'celebrate', 'mirror', 'ask')
MOVES = (
    'reflect', 'affirm', 'open_question', 'summarize', 'ask_permission',
    'offer_idea', 'celebrate', 'answer_question', 'follow_up', 'care',
)

_ASKS_IF_HUMAN_RE = re.compile(r'\b(are|r)\s+(you|u)\b.*\b(real|human|a person|a bot|an ai|ai|a robot|a machine)\b', re.IGNORECASE)

_DEFAULT_MOVES = {
    'listen': ['reflect', 'open_question'],
    'motivate': ['affirm', 'open_question'],
    'plan': ['reflect', 'offer_idea'],
    'teach': ['answer_question'],
    'challenge': ['reflect', 'open_question'],
    'celebrate': ['celebrate', 'affirm'],
    'mirror': ['summarize', 'open_question'],
    'ask': ['open_question'],
}

_MOVE_WORDS = {
    'reflect': 'Say back, in a few words, what they mean — so they feel understood.',
    'affirm': 'Name one real effort or strength you can see in what they said — plainly, no hype.',
    'open_question': 'Ask one open question.',
    'summarize': 'Pull together what they have said into one short line.',
    'ask_permission': 'Ask whether they want an idea before giving one.',
    'offer_idea': 'Offer one small, concrete idea as an option they can take or leave.',
    'celebrate': 'Mark the progress plainly and warmly — effort, not talent.',
    'answer_question': 'Answer their question first, briefly and concretely.',
    'follow_up': 'Pick up something from earlier in the conversation.',
    'care': 'Just be there for them — no advice, no goals.',
}


def apply(
    decided: dict[str, Any],
    reading: dict[str, Any],
    *,
    trigger: str = 'message',
    checkin_mode: bool = False,
    escalation_level: int = 0,
) -> dict[str, Any]:
    """Returns the final plan: `stance`, `moves`, `question`, `idea`, and
    `words` (the plan in plain language for the Speak prompt)."""
    if trigger != 'message':
        return _proactive_plan(escalation_level)

    stance = decided.get('stance') if decided.get('stance') in STANCES else _default_stance(reading, checkin_mode)
    moves = [m for m in decided.get('moves') or [] if m in MOVES][:2]
    question = decided.get('question') or None
    idea = decided.get('idea') or None
    did_it = reading.get('did_it_today')

    if reading.get('change_talk') == 'discord' or reading.get('intent') == 'pushback':
        stance, moves, idea = 'listen', ['reflect', 'open_question'], None

    if did_it is False:
        if stance == 'celebrate':
            stance = 'listen'
        moves = [m for m in moves if m != 'celebrate']

    asks_if_human = bool(_ASKS_IF_HUMAN_RE.search(reading.get('asked_question') or ''))

    if reading.get('asked_question'):
        moves = ['answer_question'] + [m for m in moves if m not in ('answer_question', 'open_question')][:1]
        stance = 'teach' if stance in ('ask', 'listen', None) else stance

    if not moves:
        moves = list(_DEFAULT_MOVES[stance])
    if 'offer_idea' not in moves:
        idea = None
    if question is None and 'open_question' in moves and 'answer_question' in moves:
        moves.remove('open_question')

    words = _words(stance, moves, question, idea, reading)
    if asks_if_human:
        words += "\nFact: you are an AI — the assistant inside selfie.Me — not a person. Say so plainly and kindly, in your own words."
    return {'stance': stance, 'moves': moves, 'question': question, 'idea': idea, 'words': words}


def _default_stance(reading: dict[str, Any], checkin_mode: bool) -> str:
    intent = reading.get('intent')
    if reading.get('asked_question') or intent == 'asking':
        return 'teach'
    if intent == 'progress' and reading.get('did_it_today') is not False and not checkin_mode:
        return 'celebrate'
    return 'listen'


def _words(stance: str, moves: list[str], question: str | None, idea: str | None, reading: dict[str, Any]) -> str:
    lines = [f'Stance: {stance}.'] + [_MOVE_WORDS[m] for m in moves]
    if idea:
        lines.append(f'The idea to offer (as an option, not an instruction): {idea}')
    if question:
        lines.append(f'The one question to ask: {question}')
    else:
        lines.append('Ask at most one question.')

    if reading.get('did_it_today') is False:
        lines.append('Fact: they did NOT do it today — never say or imply that they did.')
    if reading.get('minutes_today') is not None:
        lines.append(f"Fact: today they did {reading['minutes_today']} minutes.")
    if reading.get('reason_given'):
        lines.append(f"Their reason, in their words: {reading['reason_given']}. Acknowledge it.")
    if reading.get('feeling') and reading['feeling'] != 'unknown':
        lines.append(f"They seem to feel: {reading['feeling']}.")
    return '\n'.join(lines)


def _proactive_plan(escalation_level: int) -> dict[str, Any]:
    words = (
        "Stance: listen.\nThey haven't replied since your last message. Check in warmly and briefly — about "
        "them, not the goal. Don't repeat or rephrase your last message. No pressure. Ask at most one question."
    )
    if escalation_level > 0:
        words += '\nYour earlier check-ins got no answer, so keep this one even lighter and try a different angle.'
    return {'stance': 'listen', 'moves': ['care', 'open_question'], 'question': None, 'idea': None, 'words': words}


def concern_plan() -> dict[str, Any]:
    """Safety `concern` (Building_Brain1.md §13): listen and be there — no
    goals, no advice, no challenge, no ideas."""
    words = (
        'Stance: listen.\nThey sound like they are really struggling. Just be there: say back gently what you hear, '
        'and ask one soft question about how they are. No goals, no advice, no ideas, no silver linings.'
    )
    return {'stance': 'listen', 'moves': ['reflect', 'care'], 'question': None, 'idea': None, 'words': words}
