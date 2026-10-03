from __future__ import annotations

import json
from typing import Any

from ..model_gateway import get_model_provider
from ..workflow.models import PlanStep
from ..workflow.state import RiskClass
from . import _shared
from ._graph import run, single_node_graph


def _support_message(payload: dict[str, Any]) -> dict[str, Any]:
    """Notices a struggle and responds with real, targeted help toward the

    person's own original goal — the amygdala job: salience detection ("this
    matters, something's off") plus an attuned, still-never-commanding
    response. Orchestration's `brain2/intentions_repo.shortfall_streak` has
    already deterministically decided a shortfall exists; this only composes
    how to talk about one it's handed, and it must never decide, command, or
    judge. Every number here (target, dates, streak) comes from the caller
    and must never be invented, rounded, or estimated.

    This is not a one-line check-in — the job is: collect the actual reasons
    the person gave on each logged day (`note`, when present), find the real
    pattern behind them (not just restate each day's excuse), and offer ONE
    concrete, specific strategy aimed at that pattern — genuinely in service
    of them reaching their stated goal, not settling permanently for less. A
    smaller interim target is still allowed when warranted, but it must be
    framed as a stepping stone back toward the original number, never a
    replacement for it.
    """
    who_lines = _shared.profile_lines(payload)
    domain = payload.get('domain', 'this')
    title = payload.get('title', 'this intention')
    target_minutes = payload.get('target_minutes')
    streak = payload.get('streak')
    checkins: list[dict[str, Any]] = payload.get('checkins', [])
    checkin_lines = [
        f"- {c.get('checkin_date')}: {c.get('actual_minutes')} min"
        + (f" — they said: \"{c['note']}\"" if c.get('note') else '')
        for c in checkins
    ]

    system_prompt = (
        "You are Brain 2 — a second brain whose entire purpose is to help ONE specific person "
        "actually reach a goal they set for themselves. They have fallen short of it for "
        "several days running. Everything you say must be grounded ONLY in the exact domain, "
        "title, target, dates, minutes, and what they actually said on each day, all given "
        "below — never invent, round, or estimate a number, and never invent a reason they "
        "didn't give you.\n\n"
        "Do this in order:\n"
        "1. Read what they actually said on each logged day below (when given). Do not just "
        "summarize each day separately — find the REAL, underlying pattern connecting them "
        "(e.g. always failing in the evening, no fixed time slot, a specific recurring "
        "obstacle, the target itself being unrealistic for their actual schedule). If the "
        "days given don't actually share a pattern, say that honestly instead of inventing one.\n"
        "2. Name that pattern back to them plainly — this is the one thing that actually helps, "
        "more than any generic encouragement.\n"
        "3. Give ONE concrete, specific, genuinely useful strategy or adjustment that directly "
        "addresses THAT pattern — not generic motivation ('stay consistent', 'you can do it'), "
        "and not a vague question. You are trying to help them actually close the gap, not just "
        "make them feel heard.\n"
        "4. You may NEVER phrase anything as a command or instruction ('you must', 'you need "
        "to') — frame your strategy as a genuine offer ('one thing that might actually help, "
        "given what's been getting in the way:'), never as telling them what to do. But a "
        "specific, well-reasoned offer is not the same as a vague question — do not retreat "
        "into only asking 'what got in the way?' when the days already given you tell you what "
        "got in the way.\n"
        "5. If a smaller daily target is genuinely warranted given the pattern, offer it "
        "explicitly as a deliberate stepping stone BACK toward their original target — say so "
        "plainly, so it reads as a path to the real goal, not as giving up on it. Never be "
        "shaming, falsely upbeat, or clinical.\n\n"
        "Tone: warm, like a companion who's actually paying attention to this one person — not "
        "a progress-tracker reading out numbers at them. If a profile is given below, use their "
        "first name where it feels natural and let their actual context shape the voice. Short "
        "does not mean cold.\n\n"
        "Respond with strict JSON only, no markdown fencing, matching exactly this shape: "
        '{"message": "...", "suggested_target_minutes": <int or null>}.\n'
        "- message: HARD LIMIT 3 short sentences, under 55 words total — this renders as one "
        "chat bubble, not an essay. One clause for the pattern, one for the strategy, one "
        "(only if needed) for the stepping-stone target. Cut every extra clause, second person.\n"
        "- suggested_target_minutes: a smaller, more achievable daily target if the pattern "
        "genuinely warrants one (close to what they've actually been managing, framed as "
        "temporary), or null if no target change is warranted."
    )
    prompt = (
        (('Who they are:\n' + '\n'.join(who_lines) + '\n\n') if who_lines else '')
        + f'Domain: {domain}\n'
        f'Intention: "{title}", target: {target_minutes} min/day\n'
        f'Consecutive days under target: {streak}\n'
        f'Logged check-ins, oldest to newest (what they actually did, and what they said about it):\n'
        + '\n'.join(checkin_lines)
    )

    provider = get_model_provider()
    response = provider.chat([{'role': 'user', 'content': prompt}], system=system_prompt)

    try:
        parsed = json.loads(response)
    except json.JSONDecodeError:
        parsed = {'message': response.strip(), 'suggested_target_minutes': None}

    suggested = parsed.get('suggested_target_minutes')
    if not isinstance(suggested, int):
        suggested = None

    return {'message': parsed.get('message', ''), 'suggested_target_minutes': suggested}


_GRAPH = single_node_graph('support_message', _support_message)


class Amygdala:
    """Emotional salience + attuned response (ADD §8). One node, one job:

    `support_message`. What used to be `SmartAgent._brain2_support_message`.
    """

    name = 'amygdala'

    def plan(self, goal: str) -> list[PlanStep]:
        payload = json.loads(goal)
        return [
            PlanStep(
                tool='amygdala',
                operation='support_message',
                risk_class=RiskClass.READ_ONLY,
                args=payload,
            )
        ]

    def execute_step(self, step: PlanStep) -> dict[str, Any]:
        return run(_GRAPH, step.args)
