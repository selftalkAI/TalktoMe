from __future__ import annotations

import pytest

from app.agents import amygdala, hippocampus


class Fake:
    def __init__(self, reply: str) -> None:
        self.reply = reply

    def chat(self, messages, *, system=None):  # noqa: ANN001
        return self.reply


def test_episode_keeps_only_verbatim_quotes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(hippocampus, 'get_model_provider', lambda tier=None: Fake(
        '{"summary": "Missed the gym.", "quotes": ["kids were sick", "I am a failure"], "commitments": ["walk tomorrow"], "open_thread": "null"}'))
    result = hippocampus._summarize_episode({'turns': [{'role': 'user', 'content': 'Ugh, kids were sick again'},
                                                       {'role': 'assistant', 'content': 'That sounds hard.'}]})
    assert result == {'summary': 'Missed the gym.', 'quotes': ['kids were sick'], 'commitments': ['walk tomorrow'], 'open_thread': None}


def test_empty_episode_needs_no_model() -> None:
    assert hippocampus._summarize_episode({'turns': []})['summary'] == ''


@pytest.mark.parametrize(('reply', 'level'), [('{"level": "crisis", "reason": "x"}', 'crisis'), ('{"level": "maybe"}', 'ok'), ('garbage', 'ok')])
def test_safety_check_normalises(monkeypatch: pytest.MonkeyPatch, reply: str, level: str) -> None:
    monkeypatch.setattr(amygdala, 'get_model_provider', lambda tier=None: Fake(reply))
    assert amygdala._safety_check({'message': 'something'})['level'] == level


def test_find_patterns_needs_enough_notes(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.agents import prefrontal_cortex
    called = []
    monkeypatch.setattr(prefrontal_cortex, 'get_model_provider', lambda tier=None: called.append(1) or Fake('{}'))
    assert prefrontal_cortex._find_patterns({'items': ['a', 'b']}) == {'patterns': []} and called == []


def test_find_patterns_normalises(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.agents import prefrontal_cortex
    monkeypatch.setattr(prefrontal_cortex, 'get_model_provider', lambda tier=None: Fake(
        '{"patterns": [{"pattern": " Misses follow sick-kid weeks. ", "evidence": ["kids sick", 3, "kids were sick again"]}, "junk"]}'))
    result = prefrontal_cortex._find_patterns({'items': ['n1', 'n2', 'n3']})
    assert result == {'patterns': [{'pattern': 'Misses follow sick-kid weeks.', 'evidence': ['kids sick', 'kids were sick again']}]}
