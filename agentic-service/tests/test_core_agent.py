from __future__ import annotations

from typing import Any

import pytest

from app.agents import core_agent

TOOLS = {'search_memories': 'search', 'get_checkins': 'checkins'}


class Fake:
    def __init__(self, reply: str) -> None:
        self.reply, self.system = reply, ''

    def chat(self, messages: list[dict[str, str]], *, system: str | None = None) -> str:
        self.system = system or ''
        return self.reply


def _think(monkeypatch: pytest.MonkeyPatch, reply: str, **payload: Any) -> tuple[dict[str, Any], Fake]:
    fake = Fake(reply)
    monkeypatch.setattr(core_agent, 'get_model_provider', lambda tier=None: fake)
    base = {'core': {'name': 'Body', 'goal': 'g', 'sub_agents': [{'id': 'sleep', 'lens': 'sleep'}]}, 'tools': TOOLS, 'message': 'tired'}
    return core_agent._think({**base, **payload}), fake


def test_a_valid_tool_call_is_returned(monkeypatch: pytest.MonkeyPatch) -> None:
    step, fake = _think(monkeypatch, '{"tool": "search_memories", "args": {"query": "sleep kids", "n": 3}}')
    assert step == {'action': 'tool', 'tool': 'search_memories', 'args': {'query': 'sleep kids', 'n': '3'}}
    assert 'search_memories' in fake.system and 'sleep: sleep' in fake.system


def test_an_unknown_tool_ends_the_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    step, _ = _think(monkeypatch, '{"tool": "delete_everything", "args": {}}')
    assert step['action'] == 'done' and step['summary'] == ''


def test_finishing_is_normalised(monkeypatch: pytest.MonkeyPatch) -> None:
    step, _ = _think(monkeypatch, '{"done": true, "summary": " Sleep is poor. ", "open_question": "null", "confidence": 3}')
    assert step == {'action': 'done', 'summary': 'Sleep is poor.', 'open_question': None, 'confidence': 0.5}


def test_must_finish_hides_the_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    step, fake = _think(monkeypatch, '{"tool": "search_memories"}', must_finish=True)
    assert step['action'] == 'done' and 'search_memories' not in fake.system
