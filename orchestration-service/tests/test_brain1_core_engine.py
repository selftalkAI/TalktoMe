from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app import memory_repo
from app.brain1 import core_engine, profile, tools


def test_cores_load() -> None:
    assert set(core_engine.cores()) == {'body', 'relationships', 'mind', 'behaviour', 'lifestyle'}
    for core in core_engine.cores().values():
        assert core['goal'] and core['sub_agents'] and set(core['sections']) <= {k for k, _ in profile.SECTIONS}


@pytest.mark.parametrize(
    ('domain', 'message', 'reading', 'expected'),
    [
        ('fitness', "Couldn't go to the gym, kids were sick again", {'intent': 'setback'}, ['body', 'behaviour', 'relationships']),
        ('general', 'I always mess things up and feel so guilty', {'intent': 'venting'}, ['mind']),
        ('general', 'what a nice day', {}, []),
    ],
)
def test_router(domain: str, message: str, reading: dict, expected: list) -> None:
    assert core_engine.route(domain, message, reading) == expected


class FakeAgentic:
    def __init__(self, steps: list[dict[str, Any]]) -> None:
        self.steps, self.payloads = list(steps), []

    def __call__(self) -> 'FakeAgentic':
        return self

    def create_agent_run(self, agent: str, user_id: str, goal: str) -> dict[str, Any]:
        assert agent == 'core_agent'
        self.payloads.append(json.loads(goal))
        return {'status': 'completed', 'steps': [{'result': self.steps.pop(0)}]}


def _remember(content: str, tier: str = 'T2') -> None:
    memory_repo.create_memory(profile_email='sam@x', memory_type='fact', content=content, explicitness='explicit',
                              confidence=0.9, sensitivity_tier=tier, status='active')


def test_a_core_investigates_then_concludes_and_is_remembered(temp_db: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _remember('The kids were up all night coughing')
    _remember('Has a heart condition', tier='T3')
    fake = FakeAgentic([
        {'action': 'tool', 'tool': 'search_memories', 'args': {'query': 'kids night sleep'}},
        {'action': 'done', 'summary': 'Short on sleep from caring for sick kids.', 'open_question': 'How are you sleeping?', 'confidence': 0.8},
    ])
    monkeypatch.setattr(core_engine, 'AgenticServiceClient', fake)

    result = core_engine.run_core('sam@x', 'body', 'So tired', {'intent': 'venting'})

    assert result['summary'] == 'Short on sleep from caring for sick kids.'
    tool_output = fake.payloads[1]['findings'][0]['result']
    assert 'coughing' in tool_output and 'heart' not in tool_output  # T3 never reaches the model
    assert core_engine.latest_summaries('sam@x')[0]['summary'] == result['summary']
    assert any(q['question'] == 'How are you sleeping?' for q in profile.open_questions('sam@x'))


def test_the_loop_is_bounded(temp_db: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(core_engine.settings, 'brain1_core_max_steps', 2)
    endless = [{'action': 'tool', 'tool': 'get_checkins', 'args': {}}] * 2 + [{'action': 'done', 'summary': 'Not much known yet.', 'confidence': 0.3}]
    fake = FakeAgentic(endless)
    monkeypatch.setattr(core_engine, 'AgenticServiceClient', fake)
    core_engine.run_core('sam@x', 'behaviour', 'hi', {})
    assert len(fake.payloads) == 3 and fake.payloads[-1]['must_finish'] is True


def test_no_summary_is_stored_when_the_model_is_down(temp_db: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    class Down:
        def create_agent_run(self, *a: Any, **k: Any) -> dict[str, Any]:
            from app.spinal_cord import AgenticServiceError
            raise AgenticServiceError('down')

    monkeypatch.setattr(core_engine, 'AgenticServiceClient', Down)
    assert core_engine.run_core('sam@x', 'mind', 'hi', {})['summary'] == ''
    assert core_engine.latest_summaries('sam@x') == []


def test_unknown_tools_are_refused(temp_db: Path) -> None:
    assert tools.run('drop_tables', 'sam@x', {}) == "Unknown tool 'drop_tables'."


def test_ask_core_reads_another_cores_summary(temp_db: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(core_engine, 'AgenticServiceClient', FakeAgentic([{'action': 'done', 'summary': 'Kids sick all week.', 'confidence': 0.9}]))
    core_engine.run_core('sam@x', 'relationships', 'kids sick', {})
    assert 'Kids sick all week.' in tools.run('ask_core', 'sam@x', {'core': 'relationships'})


def test_cores_only_get_person_evidence_tools() -> None:
    assert set(tools.describe()) == {'search_memories', 'get_checkins', 'ask_core'}
