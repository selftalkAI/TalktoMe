from __future__ import annotations

import json
from typing import Any

from ..model_gateway import get_model_provider
from ..workflow.models import PlanStep
from ..workflow.state import RiskClass
from . import _shared
from ._graph import run, single_node_graph


def _open_conversation(payload: dict[str, Any]) -> dict[str, Any]:
    """First contact with Brain 1 — relays a warm opener, decides nothing.

    A relay, not an interpreter: the way a thalamus passes sensory input on
    to the cortex without itself making sense of it. Grounded only in what
    this person told us about themselves (name, location, interests, chosen
    quote) — never outside facts about them, never a fabricated shared
    memory ("I saw your photos from...").
    """
    lines = _shared.profile_lines(payload)

    system_prompt = (
        "You are opening a conversation with ONE person, the way a parent or a close "
        "friend would greet someone they care about — warm, specific, unhurried. "
        "Do NOT open with a status-check question like 'how's life been' or 'any trips "
        "planned lately?' — that reads as interrogating them, not caring about them.\n\n"
        "The single biggest failure mode here is sounding like a notification: 'I just "
        "heard about [event]... I immediately thought of how [adjective] it would be for "
        "[activity] — the kids must love [thing]!' or 'I've been meaning to check out "
        "[place] — I've heard [feature] is amazing, and it's the perfect spot for "
        "[activity].' Both are the SAME underlying template — announce a place/event, "
        "then explain why it suits their family — just with different words. Swapping "
        "the vocabulary is not enough; the sentence's whole shape must change. NEVER "
        "write in that shape, under any wording. Banned phrases: 'I just heard about', "
        "'I came across', 'I saw that', 'I've been meaning to', 'immediately thought of', "
        "'must love', 'I bet', 'the perfect', 'picture this', 'imagine this'.\n\n"
        "Concrete example of the difference (a different person, a different city — do "
        "not reuse these details, this is only to show the STYLE): the templated, banned "
        "version is 'Marcus, I just discovered that Prospect Park has an amazing new "
        "nature trail — I bet your kids would love exploring it this weekend!' The "
        "actual target style is something like 'Marcus, Prospect Park's leaves are "
        "somewhere between green and gone right now.' — one plain, specific, almost "
        "throwaway observation, no adjectives doing the selling, no pivot to an activity "
        "or a reason it's good for anyone. Say the thing itself and stop.\n\n"
        "Pick ONE small, specific, concrete detail — not a category of activity — and "
        "state it plainly, the way you'd mention something in passing to someone you "
        "already know well. Vary HOW you open line to line: sometimes a flat observation, "
        "sometimes a half-finished thought, sometimes something a little wry, sometimes "
        "just naming a feeling. You may draw on general knowledge (the season, a real "
        "event or landmark in their city, something tied to their age or interests, "
        "their family context if their interests imply one) but it must stay clearly "
        "tailored to who they are below, never random trivia, and never framed as news "
        "you're delivering to them.\n\n"
        "NEVER claim to have seen, heard, or experienced something specific from THIS "
        "person — their photos, a trip they took, something they did — unless they "
        "actually told you that below; inventing a shared memory that didn't happen is "
        "dishonest, even if it sounds warm. For example, never write anything like 'I saw "
        "your photos from...', 'I remember when you...', or 'thinking of your photos from "
        "last year's...' — you have never seen or heard anything about them beyond exactly "
        "what is written below. General knowledge (a festival happening, the season, a "
        "place) is fine; fabricated personal history about them is not.\n\n"
        "Write 1-2 sentences, second person, using their first name. You may end with a "
        "light, natural opening for them to jump in, but the specific detail comes first "
        "— this is not a question-and-answer form. Do not suggest an activity or tell them "
        "what to do — you are only opening the door."
    )
    prompt = 'Here is what this person told us about themselves:\n' + '\n'.join(lines)

    provider = get_model_provider()
    opening_message = provider.chat([{'role': 'user', 'content': prompt}], system=system_prompt)
    return {'opening_message': opening_message.strip()}


_GRAPH = single_node_graph('open_conversation', _open_conversation)


class Thalamus:
    """First contact (ADD §8) — relays Brain 1's arrival onward without

    interpreting it. One node, one job: `open_conversation`. What used to be
    `ProfileAgent.open_conversation`, split out because Sensory Cortex
    (interpreting what Brain 1 says back) is a genuinely different job, not
    the same agent wearing two hats.
    """

    name = 'thalamus'

    def plan(self, goal: str) -> list[PlanStep]:
        payload = json.loads(goal)
        return [
            PlanStep(
                tool='thalamus',
                operation='open_conversation',
                risk_class=RiskClass.READ_ONLY,
                args=payload,
            )
        ]

    def execute_step(self, step: PlanStep) -> dict[str, Any]:
        return run(_GRAPH, step.args)
