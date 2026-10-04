from __future__ import annotations

from typing import Any

import pytest

from app.agents import _shared, anterior_cingulate, prefrontal_cortex, sensory_cortex


class FakeProvider:
    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.system = ''

    def chat(self, messages: list[dict[str, str]], *, system: str | None = None) -> str:
        self.system = system or ''
        return self.reply


def _patch(monkeypatch: pytest.MonkeyPatch, module: Any, reply: str) -> FakeProvider:
    fake = FakeProvider(reply)
    tiers: list[str | None] = []
    monkeypatch.setattr(module, 'get_model_provider', lambda tier=None: tiers.append(tier) or fake)
    fake.tiers = tiers  # type: ignore[attr-defined]
    return fake


@pytest.mark.parametrize(
    ('text', 'expected'),
    [
        ('{"a": 1}', {'a': 1}),
        ('Sure! ```json\n{"a": 1}\n``` hope that helps', {'a': 1}),
        ('no json here', {}),
        ('{broken', {}),
    ],
)
def test_parse_json_object_is_forgiving(text: str, expected: dict[str, Any]) -> None:
    assert _shared.parse_json_object(text) == expected


def test_read_message_normalises_and_uses_small_model(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _patch(monkeypatch, sensory_cortex, 'Here: {"intent": "setback", "feeling": "tired", "change_talk": "bogus", '
                  '"asked_question": "null", "did_it_today": null, "minutes_today": null, '
                  '"reason_given": "kids were sick", "new_facts": ["two kids", 3]}')
    reading = sensory_cortex._read_message({'latest_message': "Couldn't go, kids were sick.", 'conversation': []})
    assert fake.tiers == ['small']  # type: ignore[attr-defined]
    assert reading['intent'] == 'setback'
    assert reading['change_talk'] == 'none'  # invalid value dropped
    assert reading['asked_question'] is None
    assert reading['did_it_today'] is False  # a setback with no answer means they didn't
    assert reading['reason_given'] == 'kids were sick'
    assert reading['new_facts'] == ['two kids']


def test_read_message_detects_a_question_even_if_the_model_misses_it(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, sensory_cortex, '{"intent": "sharing"}')
    reading = sensory_cortex._read_message({'latest_message': 'How do I do that at home?'})
    assert reading['asked_question'] == 'How do I do that at home?'


def test_read_message_without_input_never_calls_the_model(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _patch(monkeypatch, sensory_cortex, '{}')
    assert sensory_cortex._read_message({'latest_message': ''})['intent'] == 'smalltalk'
    assert fake.tiers == []  # type: ignore[attr-defined]


def test_plan_reply_keeps_only_valid_choices(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _patch(monkeypatch, prefrontal_cortex, '{"stance": "lecture", "moves": ["reflect", "dance", "offer_idea", "affirm"], '
                  '"question": "Which days could work?", "idea": "null", "why": "x"}')
    plan = prefrontal_cortex._plan_reply({'persona': {'voice': 'big_sister'}, 'context_pack': {'who': 'Sam'}, 'latest_message': 'hi'})
    assert fake.tiers == ['large']  # type: ignore[attr-defined]
    assert 'loving big sister' in fake.system
    assert plan == {'stance': None, 'moves': ['reflect', 'offer_idea'], 'question': 'Which days could work?', 'idea': None, 'why': 'x'}


def test_judge_scores_and_flags_contradictions(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, anterior_cingulate, '{"contradicts": true, "specific": 4, "in_voice": 9, "on_plan": "x", "respectful": 5, "problem": "praises a missed workout"}')
    verdict = anterior_cingulate._judge({'reply': 'Great job today!', 'latest_message': 'Missed it.'})
    assert verdict['contradicts'] is True
    assert (verdict['specific'], verdict['in_voice'], verdict['on_plan'], verdict['respectful']) == (4, 3, 3, 5)
    assert verdict['total'] == 15 and verdict['problem'] == 'praises a missed workout'


def test_unreadable_verdict_is_neutral(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, anterior_cingulate, 'I think it is fine.')
    verdict = anterior_cingulate._judge({'reply': 'ok'})
    assert verdict['contradicts'] is False and verdict['total'] == 12


def test_plan_reply_drops_a_stance_the_voice_does_not_take(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _patch(monkeypatch, prefrontal_cortex, '{"stance": "challenge", "moves": ["reflect"]}')
    plan = prefrontal_cortex._plan_reply({'persona': {'voice': 'mother_like'}, 'latest_message': 'Tired.'})
    assert plan['stance'] is None
    assert 'challenge' not in fake.system.split('"stance": one of ')[1].split(',')[0]
