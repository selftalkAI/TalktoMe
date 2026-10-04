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
    'allowed_text': 'Gym: aiming for 60 minutes a day.',
    'blocked_terms': [],
}


class FakeAgentic:
    """Stands in for the Agentic Service: returns queued Broca replies and
    records every payload it was sent."""

    def __init__(self, replies: list[str]) -> None:
        self.replies = list(replies)
        self.payloads: list[dict[str, Any]] = []

    def __call__(self) -> FakeAgentic:
        return self

    def create_agent_run(self, agent: str, user_id: str, goal: str) -> dict[str, Any]:
        assert agent == 'broca'
        self.payloads.append(json.loads(goal))
        content = self.replies.pop(0)
        return {'status': 'completed', 'steps': [{'result': {'content': content, 'example_replies': []}}]}


@pytest.fixture
def stub_pack(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(coach.context_pack, 'compile_stub', lambda *a, **k: dict(PACK))


def test_first_passing_draft_is_returned(stub_pack: None, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeAgentic(["Two sick kids this week is a lot. Rest night, or two easy minutes?"])
    monkeypatch.setattr(coach, 'AgenticServiceClient', fake)

    result = coach.reply('sam@example.com', 'fitness', 'Missed the gym, kids were sick.')

    assert result['fallback'] is False and result['attempts'] == 1
    assert fake.payloads[0]['operation'] == 'speak'
    assert fake.payloads[0]['latest_message'] == 'Missed the gym, kids were sick.'
    assert 'allowed_text' not in fake.payloads[0]['context_pack']


def test_failing_draft_is_rewritten_with_feedback(stub_pack: None, monkeypatch: pytest.MonkeyPatch) -> None:
    bad = 'I want to acknowledge your huge accomplishment!'
    good = 'Showing up three times in a sick-kid week is real effort.'
    fake = FakeAgentic([bad, good])
    monkeypatch.setattr(coach, 'AgenticServiceClient', fake)

    result = coach.reply('sam@example.com', 'fitness', 'Went three times this week.')

    assert result['content'] == good and result['attempts'] == 2
    assert 'hollow' in fake.payloads[1]['rewrite_feedback']


def test_two_failures_send_a_checked_fallback(stub_pack: None, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeAgentic(['- tip one\n- tip two', 'The user is doing great.'])
    monkeypatch.setattr(coach, 'AgenticServiceClient', fake)

    result = coach.reply('sam@example.com', 'fitness', 'Feeling stuck.')

    assert result['fallback'] is True
    assert check_reply(result['content']).passed
    assert len(result['failures']) >= 2


def test_unreachable_service_falls_back(stub_pack: None, monkeypatch: pytest.MonkeyPatch) -> None:
    class Down:
        def create_agent_run(self, *a: Any, **k: Any) -> dict[str, Any]:
            raise AgenticServiceError('down')

    monkeypatch.setattr(coach, 'AgenticServiceClient', Down)
    result = coach.reply('sam@example.com', 'fitness', '', trigger='silence')
    assert result['fallback'] is True and 'checking in' in result['content'].lower()


def test_repeating_an_earlier_reply_is_rejected(stub_pack: None, monkeypatch: pytest.MonkeyPatch) -> None:
    earlier = 'An hour at the gym would give you more energy for weekends with the kids.'
    fake = FakeAgentic([earlier, 'What would make tomorrow feel doable?'])
    monkeypatch.setattr(coach, 'AgenticServiceClient', fake)

    result = coach.reply(
        'sam@example.com',
        'fitness',
        'Not sure.',
        conversation=[{'role': 'user', 'content': 'hi'}, {'role': 'assistant', 'content': earlier}],
    )
    assert result['attempts'] == 2 and 'repeats' in fake.payloads[1]['rewrite_feedback']


@pytest.mark.parametrize(
    ('message', 'trigger', 'checkin_mode', 'expected'),
    [
        ('How do I do that at home?', 'message', False, 'Answer it first'),
        ("Didn't go today.", 'message', True, 'reflect what they said'),
        ('', 'silence', False, "haven't replied"),
        ('Did 45 minutes!', 'message', False, 'real effort'),
    ],
)
def test_plan_follows_the_coaching_rules(message: str, trigger: str, checkin_mode: bool, expected: str) -> None:
    assert expected in coach.plan_for(message, trigger=trigger, checkin_mode=checkin_mode, escalation_level=0)


def test_fallback_never_repeats_the_previous_fallback() -> None:
    first = coach.fallback_reply('Sam', 'message', [])
    second = coach.fallback_reply('Sam', 'message', [first])
    assert first != second
