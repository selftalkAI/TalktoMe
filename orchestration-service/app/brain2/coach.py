from __future__ import annotations

import json
from typing import Any

from ..brain1 import context_pack, persona_selector
from ..config import settings
from ..spinal_cord import AgenticServiceClient, AgenticServiceError
from . import plan_rules
from .checks import check_reply

# Brain 2's turn (Building_Brain2.md §6–§9):
#   Context Pack (Brain 1) → Understand → Decide → plan rules → Speak ×N
#   → Check (rules, then judge) → best passing reply
#   → else one rewrite with the reasons → else a safe fallback.
# The contract: no reply reaches the person unless it passed Check
# (FSD BR-016). Remember (chat vs profile split) arrives in Phase E.

MIN_JUDGE_TOTAL = 10  # of 20: below this, a rule-passing draft still isn't good enough to send



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
    persona: dict[str, str] | None = None,
) -> dict[str, Any]:
    """One checked reply. Returns `content` plus the trace of how it was
    made: `reading`, `plan`, `verdict` (the judge's scores for the sent
    reply), `attempts` (Speak calls), `failures` (why drafts were rejected)
    and `fallback` (True when nothing passed and the safe fallback was sent).

    `conversation` is the thread so far as real turns
    (`{'role': 'user'|'assistant', 'content': ...}`), oldest first, NOT
    including `latest_message`. `trigger` is 'message' when the person just
    wrote, or 'silence'/'schedule' when Brain 2 reaches out on its own.
    `persona` overrides Brain 1's Persona Selector (scripts and tests only —
    the selector also records voice requests, which a dry run must not).
    """
    conversation = conversation or []
    pack = context_pack.compile_stub(
        profile_email, domain, intention=intention, checkins=checkins, streak=streak, support_message=support_message
    )
    turn = _Turn(profile_email, pack, conversation, latest_message)

    reading = turn.understand() if trigger == 'message' else {}
    turn.persona = persona or persona_selector.select(profile_email, domain, latest_message, reading)
    decided = turn.decide(reading) if trigger == 'message' else {}
    plan = plan_rules.apply(decided, reading, trigger=trigger, checkin_mode=checkin_mode, escalation_level=escalation_level)
    if persona_selector.detect_request(latest_message) not in (None, 'clear'):
        plan['words'] += (
            '\nThey just asked you to change how you talk to them. Agree warmly in your new voice in one short '
            "line, then ask what's going on."
        )

    best = turn.best_of(plan, settings.brain2_speak_candidates, feedback='')
    if best is None and turn.speak_available:
        best = turn.best_of(plan, 1, feedback=turn.rewrite_feedback())

    trace = {'reading': reading, 'plan': plan, 'persona': turn.persona, 'attempts': turn.attempts, 'failures': turn.failures}
    if best is not None:
        return {'content': best['content'], 'verdict': best['verdict'], 'fallback': False, **trace}
    return {'content': fallback_reply(pack['first_name'], trigger, turn.previous), 'verdict': None, 'fallback': True, **trace}


class _Turn:
    """The state of one reply being made: what was tried, what failed, why."""

    def __init__(self, profile_email: str, pack: dict[str, Any], conversation: list[dict[str, str]], latest_message: str) -> None:
        self.profile_email = profile_email
        self.pack = pack
        self.conversation = conversation
        self.latest_message = latest_message
        self.previous = [t['content'] for t in conversation if t.get('role') == 'assistant']
        self.allowed_text = '\n'.join([pack['allowed_text'], latest_message, *(t.get('content', '') for t in conversation)])
        self.public_pack = {k: v for k, v in pack.items() if k not in ('allowed_text', 'blocked_terms')}
        self.attempts = 0
        self.failures: list[str] = []
        self.speak_available = True
        self.persona: dict[str, str] = {'voice': persona_selector.DEFAULT_VOICE, 'expertise': 'general', 'source': 'default'}
        self.examples: list[str] = []  # the prompt's example replies, so a copied example is caught

    # --- Understand / Decide --------------------------------------------------

    def understand(self) -> dict[str, Any]:
        """Sensory Cortex `read_message`; on failure, only what code can tell."""
        result = self._run(
            'sensory_cortex',
            {'operation': 'read_message', 'latest_message': self.latest_message, 'conversation': self.conversation},
        )
        if result is not None:
            return result
        return {'asked_question': self.latest_message if '?' in self.latest_message else None}

    def decide(self, reading: dict[str, Any]) -> dict[str, Any]:
        """Prefrontal Cortex `plan_reply`; on failure the plan rules choose."""
        result = self._run(
            'prefrontal_cortex',
            {
                'operation': 'plan_reply',
                'persona': self.persona,
                'context_pack': self.public_pack,
                'conversation': self.conversation,
                'latest_message': self.latest_message,
                'reading': reading,
            },
        )
        return result or {}

    # --- Speak / Check --------------------------------------------------------

    def best_of(self, plan: dict[str, Any], candidates: int, feedback: str) -> dict[str, Any] | None:
        """Speaks `candidates` drafts; returns the best one that passes both
        the rules and the judge, or None."""
        passing: list[dict[str, Any]] = []
        for _ in range(candidates):
            draft = self._speak(plan, feedback)
            if draft is None:
                break
            verdict = self._check(draft, plan)
            if verdict is not None:
                passing.append({'content': draft, 'verdict': verdict})
        return max(passing, key=lambda p: p['verdict']['total']) if passing else None

    def rewrite_feedback(self) -> str:
        return '; '.join(dict.fromkeys(self.failures))[:600]

    def _speak(self, plan: dict[str, Any], feedback: str) -> str | None:
        result = self._run(
            'broca',
            {
                'operation': 'speak',
                'persona': self.persona,
                'context_pack': self.public_pack,
                'plan': plan['words'],
                'conversation': self.conversation,
                'latest_message': self.latest_message,
                'rewrite_feedback': feedback,
            },
        )
        self.attempts += 1
        if result is None or not (result.get('content') or '').strip():
            self.speak_available = False
            self.failures.append('speak unavailable')
            return None
        self.examples = result.get('example_replies') or self.examples
        return result['content'].strip()

    def _check(self, draft: str, plan: dict[str, Any]) -> dict[str, Any] | None:
        """Rules first (free, deterministic), then the judge. Returns the
        judge's verdict if the draft may be sent, else None."""
        rules = check_reply(
            draft,
            previous_replies=self.previous + self.examples,
            allowed_text=self.allowed_text,
            blocked_terms=self.pack['blocked_terms'],
        )
        if not rules.passed:
            self.failures.extend(rules.failures)
            return None

        verdict = self._run(
            'anterior_cingulate',
            {
                'reply': draft,
                'persona': self.persona,
                'plan': plan['words'],
                'facts': '\n'.join(v for k, v in self.public_pack.items() if k != 'first_name' and v),
                'conversation': self.conversation,
                'latest_message': self.latest_message,
            },
        )
        if verdict is None:  # judge unavailable: the rules already passed it
            return {'total': 0, 'contradicts': False, 'problem': None, 'judged': False}
        if verdict.get('contradicts'):
            self.failures.append(f"contradicts what they said ({verdict.get('problem') or 'judge'})")
            return None
        if verdict.get('total', 0) < MIN_JUDGE_TOTAL:
            self.failures.append(f"judged weak ({verdict.get('problem') or 'generic'})")
            return None
        return {**verdict, 'judged': True}

    # --- Agentic Service ------------------------------------------------------

    def _run(self, agent: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        """One agent call; None when the service or the agent fails."""
        try:
            run = AgenticServiceClient().create_agent_run(agent, user_id=self.profile_email, goal=json.dumps(payload))
        except AgenticServiceError:
            return None
        steps = run.get('steps') or []
        result = steps[0].get('result') if run.get('status') == 'completed' and steps else None
        return result if isinstance(result, dict) else None


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
