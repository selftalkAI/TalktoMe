from __future__ import annotations

from typing import Any

import pytest

from app.agents import broca


class FakeProvider:
    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.calls: list[dict[str, Any]] = []

    def chat(self, messages: list[dict[str, str]], *, system: str | None = None) -> str:
        self.calls.append({'messages': messages, 'system': system})
        return self.reply


@pytest.fixture
def provider(monkeypatch: pytest.MonkeyPatch) -> FakeProvider:
    fake = FakeProvider('Brain 2: "Two easy minutes tonight, or a rest night?"')
    tiers: list[str | None] = []
    monkeypatch.setattr(broca, 'get_model_provider', lambda tier=None: tiers.append(tier) or fake)
    fake.tiers = tiers  # type: ignore[attr-defined]
    return fake


def _speak(**overrides: Any) -> dict[str, Any]:
    payload = {
        'context_pack': {'first_name': 'Sam', 'who': 'Sam, 41.', 'goal': 'Gym 60 min/day.', 'today': 'Monday', 'loves': '', 'story': '', 'works': ''},
        'plan': 'Reflect first, then offer one small step.',
        'conversation': [{'role': 'user', 'content': 'hi'}, {'role': 'assistant', 'content': 'Hey Sam.'}],
        'latest_message': 'Missed the gym again.',
    }
    payload.update(overrides)
    return broca._speak(payload)


def test_speak_uses_the_large_model_and_real_turns(provider: FakeProvider) -> None:
    result = _speak()
    call = provider.calls[0]
    assert provider.tiers == ['large']  # type: ignore[attr-defined]
    assert [m['role'] for m in call['messages']] == ['user', 'assistant', 'user']
    assert call['messages'][-1]['content'] == 'Missed the gym again.'
    assert result['content'] == 'Two easy minutes tonight, or a rest night?'


def test_system_prompt_layers_are_in_order_and_empty_ones_skipped(provider: FakeProvider) -> None:
    _speak()
    system = provider.calls[0]['system']
    order = ['talking with Sam', 'WHO THEY ARE', 'THEIR GOAL', 'THEIR WORLD TODAY', 'YOUR PLAN FOR THIS REPLY', 'HOW YOU WRITE', 'EXAMPLES OF YOUR VOICE']
    positions = [system.index(marker) for marker in order]
    assert positions == sorted(positions)
    assert 'WHAT YOU KNOW ABOUT THEIR LIFE' not in system  # empty section left out
    assert '{first_name}' not in system


def test_rewrite_feedback_is_included(provider: FakeProvider) -> None:
    _speak(rewrite_feedback='too long (80 words)')
    assert 'REJECTED BECAUSE: too long (80 words)' in provider.calls[0]['system']


def test_proactive_turn_never_invents_their_words(provider: FakeProvider) -> None:
    _speak(conversation=[{'role': 'assistant', 'content': 'How did today go?'}], latest_message='')
    messages = provider.calls[0]['messages']
    assert messages[-1]['role'] == 'user' and "haven't replied" in messages[-1]['content']
    assert messages[0]['role'] == 'user'


def test_example_replies_are_exposed_for_copy_detection(provider: FakeProvider) -> None:
    assert len(_speak()['example_replies']) >= 3
