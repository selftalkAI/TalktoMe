from __future__ import annotations

import json
from typing import Any

from ..brain1 import context_pack
from ..spinal_cord import AgenticServiceClient, AgenticServiceError
from .checks import check_reply

# Brain 2's turn (Building_Brain2.md §7–§9). Today: Context Pack → plan →
# Speak → Check → one rewrite → safe fallback. Understand and Decide replace
# `plan_for` with model-planned replies in Phase C; Remember (chat vs profile
# split) arrives in Phase E. The contract that matters already holds: no
# reply reaches the person unless it passed Check (FSD BR-016).

MAX_SPEAK_ATTEMPTS = 2


def reply(
    profile_email: str,
    domain: str,
    latest_message: str,
    *,
    conversation: list[dict[str, str]] | None = None,
    trigger: str = 'message',
    intention: dict[str, Any] | None = None,
    checkins: list[dict[str, Any]] | None = None,
    streak: int | None = None,
    support_message: str = '',
    checkin_mode: bool = False,
    escalation_level: int = 0,
) -> dict[str, Any]:
    """One checked reply. Returns `content` plus how it got there: `attempts`,
    `failures` (from every rejected draft) and `fallback` (True when no draft
    passed and the safe fallback was sent instead).

    `conversation` is this thread so far as real turns
    (`{'role': 'user'|'assistant', 'content': ...}`), oldest first, NOT
    including `latest_message`. `trigger` is 'message' when the person just
    wrote, or 'silence'/'schedule' when Brain 2 is reaching out on its own.
    """
    conversation = conversation or []
    pack = context_pack.compile_stub(
        profile_email, domain, intention=intention, checkins=checkins, streak=streak, support_message=support_message
    )
    plan = plan_for(latest_message, trigger=trigger, checkin_mode=checkin_mode, escalation_level=escalation_level)
    previous = [t['content'] for t in conversation if t.get('role') == 'assistant']
    allowed_text = '\n'.join([pack['allowed_text'], latest_message, *(t.get('content', '') for t in conversation)])

    failures: list[str] = []
    feedback = ''
    for attempt in range(1, MAX_SPEAK_ATTEMPTS + 1):
        try:
            spoken = _speak(profile_email, pack, plan, conversation, latest_message, feedback)
        except AgenticServiceError as exc:
            failures.append(f'speak unavailable: {exc}')
            break
        result = check_reply(
            spoken['content'],
            previous_replies=previous + spoken.get('example_replies', []),
            allowed_text=allowed_text,
            blocked_terms=pack['blocked_terms'],
        )
        if result.passed:
            return {'content': spoken['content'], 'attempts': attempt, 'failures': failures, 'fallback': False}
        failures.extend(result.failures)
        feedback = result.feedback()

    return {
        'content': fallback_reply(pack['first_name'], trigger, previous),
        'attempts': MAX_SPEAK_ATTEMPTS,
        'failures': failures,
        'fallback': True,
    }


def plan_for(latest_message: str, *, trigger: str, checkin_mode: bool, escalation_level: int) -> str:
    """A rule-based plan in plain words — the stand-in for the Decide step
    (Building_Brain2.md §8.4.2) until Phase C. It encodes the coaching
    behaviours of §4: understand before advising, answer their question
    first, one question at most, offer ideas only as options.
    """
    if trigger != 'message' or not latest_message.strip():
        plan = (
            "They haven't replied since your last message. Check in warmly and briefly — about them, "
            "not the goal. Don't repeat or rephrase your last message. No pressure."
        )
        if escalation_level > 0:
            plan += ' Your earlier check-ins got no answer, so keep this one even lighter and try a different angle.'
        return plan

    if '?' in latest_message:
        return 'They asked you something. Answer it first, briefly and concretely. Add nothing they did not ask for.'

    if checkin_mode:
        return (
            "They didn't manage it today, or didn't say how it went — never claim they did. First reflect what "
            "they said — and their reason, "
            'if they gave one — without judging. Then, only if it fits, offer one small, easy next step as an '
            'option they can choose. Ask at most one question.'
        )

    return (
        'Respond to what they just said. Show you understood it, using their life — not generic praise. '
        'If they made progress, name the real effort plainly. Offer an idea only as an option, and ask at '
        'most one question.'
    )


def fallback_reply(first_name: str, trigger: str, previous_replies: list[str]) -> str:
    """Honest, short, always passes Check — sent only when no draft did.
    Rotates so a fallback never repeats the one sent before."""
    if trigger != 'message':
        options = [f'Just checking in, {first_name} — how are things today?', 'Thinking of you. How has your day been?']
    else:
        options = [
            f'I hear you, {first_name}. What feels most important about this right now?',
            "Tell me a bit more — what's been the hardest part?",
            'That makes sense. What would help most today?',
        ]
    for option in options:
        if option not in previous_replies:
            return option
    return options[0]


def _speak(
    profile_email: str,
    pack: dict[str, Any],
    plan: str,
    conversation: list[dict[str, str]],
    latest_message: str,
    rewrite_feedback: str,
) -> dict[str, Any]:
    payload = {
        'operation': 'speak',
        'context_pack': {k: v for k, v in pack.items() if k not in ('allowed_text', 'blocked_terms')},
        'plan': plan,
        'conversation': conversation,
        'latest_message': latest_message,
        'rewrite_feedback': rewrite_feedback,
    }
    run = AgenticServiceClient().create_agent_run('broca', user_id=profile_email, goal=json.dumps(payload))
    steps = run.get('steps') or []
    result = steps[0].get('result') if run.get('status') == 'completed' and steps else None
    if not isinstance(result, dict) or not (result.get('content') or '').strip():
        raise AgenticServiceError(f"broca speak returned no reply (run status: {run.get('status')})")
    return result
