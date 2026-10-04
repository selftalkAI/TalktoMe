from __future__ import annotations

import json
from typing import Any

import pytest

from app.brain2 import coach
from app.brain2.checks import check_reply
from app.spinal_cord import AgenticServiceError

PACK = {
    'first_name': 'Sam',
    'who': 'Sam, 41, lives in Langley BC.',
    'goal': 'Gym: aiming for 60 minutes a day.',
    'today': 'Saturday',
    'loves': '- Two kids',
    'story': '',
    'works': '',
    'allowed_text': 'Gym: aiming for 60 minutes a day. Saturday',
    'blocked_terms': [],
}

GOOD_VERDICT = {'specific': 4, 'in_voice': 4, 'on_plan': 4, 'respectful': 5, 'contradicts': False, 'problem': None, 'total': 17}


class FakeAgentic:
    """Stands in for the Agentic Service, answering per agent: a reading,
    a plan, queued Broca drafts, and queued judge verdicts. Records every
    payload it was sent."""

    def __init__(
        self,
        drafts: list[str],
        *,
        reading: dict[str, Any] | None = None,
        plan: dict[str, Any] | None = None,
        verdicts: list[dict[str, Any]] | None = None,
    ) -> None:
        self.drafts = list(drafts)
        self.reading = reading if reading is not None else {'intent': 'sharing', 'did_it_today': None}
        self.plan = plan if plan is not None else {'stance': 'listen', 'moves': ['reflect', 'open_question']}
        self.verdicts = list(verdicts or [])
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def __call__(self) -> FakeAgentic:
        return self

    def create_agent_run(self, agent: str, user_id: str, goal: str) -> dict[str, Any]:
        payload = json.loads(goal)
        self.calls.append((agent, payload))
        if agent == 'sensory_cortex':
            result: dict[str, Any] = self.reading
        elif agent == 'prefrontal_cortex':
            result = self.plan
        elif agent == 'broca':
            result = {'content': self.drafts.pop(0), 'example_replies': ['Copy me exactly please.']}
        elif agent == 'anterior_cingulate':
            result = self.verdicts.pop(0) if self.verdicts else GOOD_VERDICT
        else:
            raise AssertionError(agent)
        return {'status': 'completed', 'steps': [{'result': result}]}

    def payloads(self, agent: str) -> list[dict[str, Any]]:
        return [p for a, p in self.calls if a == agent]


@pytest.fixture(autouse=True)
def stub_pack(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(coach.context_pack, 'compile_stub', lambda *a, **k: dict(PACK))
    monkeypatch.setattr(coach.settings, 'brain2_speak_candidates', 2)
    monkeypatch.setattr(
        coach.persona_selector, 'select', lambda *a, **k: {'voice': 'friend', 'expertise': 'general', 'source': 'selected'}
    )


def _install(monkeypatch: pytest.MonkeyPatch, fake: FakeAgentic) -> FakeAgentic:
    monkeypatch.setattr(coach, 'AgenticServiceClient', fake)
    return fake


def test_full_turn_runs_every_step_in_order(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _install(monkeypatch, FakeAgentic(['Two sick kids is a lot. Rest night, or two easy minutes?', 'Rough week. What helps most tonight?']))

    result = coach.reply('sam@example.com', 'fitness', 'Missed the gym, kids were sick.')

    agents = [a for a, _ in fake.calls]
    assert agents[:2] == ['sensory_cortex', 'prefrontal_cortex']
    assert agents.count('broca') == 2 and agents.count('anterior_cingulate') == 2
    assert fake.payloads('prefrontal_cortex')[0]['operation'] == 'plan_reply'
    assert 'allowed_text' not in fake.payloads('broca')[0]['context_pack']
    assert result['fallback'] is False and result['verdict']['total'] == 17


def test_the_best_judged_draft_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    weak_but_ok = {**GOOD_VERDICT, 'total': 12}
    _install(monkeypatch, FakeAgentic(['Okay. How was it?', 'Three times in a sick-kid week is real effort.'], verdicts=[weak_but_ok, GOOD_VERDICT]))

    result = coach.reply('sam@example.com', 'fitness', 'Went three times this week.')

    assert result['content'] == 'Three times in a sick-kid week is real effort.'


def test_contradicting_drafts_are_rejected_then_rewritten(monkeypatch: pytest.MonkeyPatch) -> None:
    contradiction = {**GOOD_VERDICT, 'contradicts': True, 'problem': 'praises a missed workout'}
    fake = _install(
        monkeypatch,
        FakeAgentic(
            ['Great workout today!', 'Nice session today!', 'Sick kids again — that is a full house. Rest night?'],
            reading={'intent': 'setback', 'did_it_today': False},
            verdicts=[contradiction, contradiction, GOOD_VERDICT],
        ),
    )

    result = coach.reply('sam@example.com', 'fitness', "Couldn't go, kids sick.")

    assert result['content'].startswith('Sick kids again') and result['attempts'] == 3
    assert 'praises a missed workout' in fake.payloads('broca')[2]['rewrite_feedback']
    assert 'did NOT do it today' in fake.payloads('broca')[0]['plan']


def test_rule_failures_never_reach_the_judge(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _install(monkeypatch, FakeAgentic(['- tip one\n- tip two', 'The user is doing great.', 'I want to acknowledge your huge accomplishment.']))

    result = coach.reply('sam@example.com', 'fitness', 'Feeling stuck.')

    assert fake.payloads('anterior_cingulate') == []
    assert result['fallback'] is True and check_reply(result['content']).passed


def test_copied_prompt_example_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch, FakeAgentic(['Copy me exactly please.', 'Copy me exactly please.', 'What would make tomorrow easier?']))
    result = coach.reply('sam@example.com', 'fitness', 'Not sure.')
    assert result['content'] == 'What would make tomorrow easier?'


def test_weak_drafts_are_not_sent(monkeypatch: pytest.MonkeyPatch) -> None:
    weak = {**GOOD_VERDICT, 'total': 8, 'problem': 'generic'}
    _install(monkeypatch, FakeAgentic(['Keep going!', 'You got this!', 'Stay positive!'], verdicts=[weak, weak, weak]))
    result = coach.reply('sam@example.com', 'fitness', 'Meh.')
    assert result['fallback'] is True and 'judged weak (generic)' in result['failures']


def test_unavailable_judge_still_sends_rule_passing_reply(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeAgentic(['Rough week. What helps most tonight?', 'Rest night, or two easy minutes?'])
    original = fake.create_agent_run

    def no_judge(agent: str, user_id: str, goal: str) -> dict[str, Any]:
        if agent == 'anterior_cingulate':
            return {'status': 'failed', 'steps': []}
        return original(agent, user_id, goal)

    fake.create_agent_run = no_judge  # type: ignore[method-assign]
    _install(monkeypatch, fake)
    result = coach.reply('sam@example.com', 'fitness', 'Long week.')
    assert result['fallback'] is False and result['verdict']['judged'] is False


def test_unreachable_service_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    class Down:
        def create_agent_run(self, *a: Any, **k: Any) -> dict[str, Any]:
            raise AgenticServiceError('down')

    monkeypatch.setattr(coach, 'AgenticServiceClient', Down)
    result = coach.reply('sam@example.com', 'fitness', '', trigger='silence')
    assert result['fallback'] is True and 'checking in' in result['content'].lower()


def test_proactive_turn_skips_understand_and_decide(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _install(monkeypatch, FakeAgentic(['How are the kids doing?', 'Thinking of you today.']))
    coach.reply('sam@example.com', 'fitness', '', trigger='silence')
    assert fake.payloads('sensory_cortex') == [] and fake.payloads('prefrontal_cortex') == []
    assert "haven't replied" in fake.payloads('broca')[0]['plan']


def test_fallback_never_repeats_the_previous_fallback() -> None:
    first = coach.fallback_reply('Sam', 'message', [])
    second = coach.fallback_reply('Sam', 'message', [first])
    assert first != second


def test_the_selected_persona_reaches_decide_speak_and_judge(monkeypatch: pytest.MonkeyPatch) -> None:
    sister = {'voice': 'big_sister', 'expertise': 'general', 'source': 'her_choice'}
    monkeypatch.setattr(coach.persona_selector, 'select', lambda *a, **k: sister)
    fake = _install(monkeypatch, FakeAgentic(['Okay, spill. What happened?', 'Tell me everything.']))

    result = coach.reply('sam@example.com', 'general', 'Talk to me like my sister would.')

    assert result['persona'] == sister
    for agent in ('prefrontal_cortex', 'broca', 'anterior_cingulate'):
        assert fake.payloads(agent)[0]['persona'] == sister


def test_a_voice_request_is_acknowledged_in_the_plan(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _install(monkeypatch, FakeAgentic(["Deal — just me now. So what's going on?", 'Okay, sister mode. Talk to me.']))
    coach.reply('sam@example.com', 'general', 'Can you talk to me like my sister would?')
    assert 'asked you to change how you talk' in fake.payloads('broca')[0]['plan']
