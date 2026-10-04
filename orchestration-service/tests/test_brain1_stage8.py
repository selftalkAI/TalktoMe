from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from app import conversations_repo, memory_repo
from app.brain1 import episodes, proactive, safety
from app.db import get_connection

EMAIL = 'sam@x'


def _turn(role: str, content: str, minutes_ago: float, domain: str = 'fitness', proactive_: bool = False) -> dict:
    row = conversations_repo.append(EMAIL, domain, role, content, proactive=proactive_)
    when = (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat()
    with get_connection() as conn:
        conn.execute('UPDATE conversation_turns SET created_at = ? WHERE turn_id = ?', (when, row['turn_id']))
    return {**row, 'created_at': when}


class FakeAgentic:
    def __init__(self, results: dict[str, Any]) -> None:
        self.results, self.calls = results, []

    def __call__(self) -> 'FakeAgentic':
        return self

    def create_agent_run(self, agent: str, user_id: str, goal: str) -> dict[str, Any]:
        self.calls.append((agent, json.loads(goal)))
        return {'status': 'completed', 'steps': [{'result': self.results[agent]}]}


# --- conversations -------------------------------------------------------------

def test_the_current_session_stops_at_a_long_gap(temp_db: Path) -> None:
    _turn('user', 'old', 300)
    _turn('assistant', 'old reply', 299)
    _turn('user', 'new', 10)
    _turn('assistant', 'new reply', 9)
    assert [t['content'] for t in conversations_repo.current_session(EMAIL, 'fitness')] == ['new', 'new reply']


def test_areas_awaiting_their_reply(temp_db: Path) -> None:
    _turn('user', 'hi', 30)
    _turn('assistant', 'hey', 29)
    _turn('assistant', 'checking in', 5, proactive_=True)
    _turn('user', 'cooking q', 5, domain='cooking')
    waiting = conversations_repo.domains_awaiting_reply(EMAIL)
    assert [(w['domain'], w['proactive_since_reply']) for w in waiting] == [('fitness', 1)]


# --- episodes --------------------------------------------------------------------

def test_a_finished_session_becomes_one_episodic_memory(temp_db: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _turn('user', 'Kids were sick, missed the gym', 200)
    _turn('assistant', 'That is a lot. Two minutes tonight?', 199)
    _turn('user', 'I will try a walk tomorrow', 198)
    fake = FakeAgentic({'hippocampus': {'summary': 'Missed the gym because the kids were sick; felt guilty.',
                                        'quotes': ['Kids were sick'], 'commitments': ['a walk tomorrow'],
                                        'open_thread': 'whether the walk happened'}})
    monkeypatch.setattr(episodes, 'AgenticServiceClient', fake)

    memory = episodes.consolidate(EMAIL, 'fitness')

    assert memory['type'] == 'event' and memory['source_type'] == 'episode'
    assert '"Kids were sick"' in memory['content'] and 'a walk tomorrow' in memory['content']
    assert conversations_repo.unsummarised(EMAIL, 'fitness') == []
    assert episodes.consolidate(EMAIL, 'fitness') is None  # nothing left to summarise
    with get_connection() as conn:
        follow = conn.execute("SELECT question FROM brain1_open_questions WHERE core = 'life_story'").fetchone()
    assert follow['question'] == 'Follow up: whether the walk happened'


def test_the_ongoing_session_is_not_summarised_yet(temp_db: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _turn('user', 'hi', 5)
    _turn('assistant', 'hey', 4)
    monkeypatch.setattr(episodes, 'AgenticServiceClient', FakeAgentic({'hippocampus': {'summary': 'x'}}))
    assert episodes.consolidate(EMAIL, 'fitness') is None
    assert memory_repo.list_memories(EMAIL, memory_type='event') == []


# --- proactive ---------------------------------------------------------------------

def _waiting(hours: float, unanswered: int = 0) -> dict[str, Any]:
    _turn('user', 'hi', hours * 60 + 1)
    _turn('assistant', 'how did it go?', hours * 60)
    for i in range(unanswered):
        _turn('assistant', f'checking in {i}', hours * 60 - 1 - i, proactive_=True)
    return conversations_repo.domains_awaiting_reply(EMAIL)[0]


@pytest.fixture
def daytime(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(proactive.here_now, 'compute', lambda location, now_utc=None: {'part_of_day': 'morning'})


def test_reaches_out_after_a_long_enough_silence(temp_db: Path, daytime: None) -> None:
    assert proactive.decide(EMAIL, _waiting(hours=30))['reach_out'] is True


def test_not_too_soon(temp_db: Path, daytime: None) -> None:
    decision = proactive.decide(EMAIL, _waiting(hours=2))
    assert decision == {'reach_out': False, 'reason': 'only 2.0h since the last message'}


def test_never_more_than_two_unanswered_check_ins(temp_db: Path, daytime: None) -> None:
    assert 'already unanswered' in proactive.decide(EMAIL, _waiting(hours=30, unanswered=2), respect_timing=False)['reason']


def test_one_check_in_per_day(temp_db: Path, daytime: None) -> None:
    _waiting(hours=30)
    _turn('assistant', 'earlier check-in', 1, domain='cooking', proactive_=True)
    fitness = next(w for w in conversations_repo.domains_awaiting_reply(EMAIL) if w['domain'] == 'fitness')
    assert proactive.decide(EMAIL, fitness)['reason'] == 'already checked in today'


def test_quiet_hours(temp_db: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(proactive.here_now, 'compute', lambda location, now_utc=None: {'part_of_day': 'night'})
    assert proactive.decide(EMAIL, _waiting(hours=30))['reason'] == "it's night where they are"
    assert proactive.decide(EMAIL, conversations_repo.domains_awaiting_reply(EMAIL)[0], respect_quiet_hours=False)['reach_out']


def test_never_after_a_crisis(temp_db: Path, daytime: None) -> None:
    from app.brain1 import runs
    runs.record(EMAIL, 'message', 'crisis', {}, 1)
    assert 'crisis' in proactive.decide(EMAIL, _waiting(hours=30))['reason']


def test_stops_when_check_ins_keep_being_ignored(temp_db: Path, daytime: None) -> None:
    from app.brain1 import learning, runs
    for _ in range(3):
        run_id = runs.record(EMAIL, 'silence', 'ok', {'persona': {'voice': 'friend'}, 'plan': {'stance': 'listen'}}, 1)
        learning.record(EMAIL, {'run_id': run_id, 'trace_json': '{}'}, 'silence')
    assert 'went unanswered' in proactive.decide(EMAIL, _waiting(hours=30))['reason']


# --- safety: the model only escalates ---------------------------------------------

@pytest.mark.parametrize(
    ('message', 'model_level', 'expected', 'source'),
    [
        ('I feel like disappearing, nothing matters', 'crisis', 'crisis', 'model'),
        ('Long day, so tired', 'ok', 'ok', 'rules'),
        ("I can't do this anymore", 'ok', 'concern', 'rules'),  # the model never lowers a rule's level
        ('Long day', 'nonsense', 'ok', 'rules'),
    ],
)
def test_model_layer_escalates_only(monkeypatch: pytest.MonkeyPatch, message: str, model_level: str, expected: str, source: str) -> None:
    monkeypatch.setattr(safety.settings, 'brain1_safety_model_enabled', True)
    monkeypatch.setattr(safety, 'AgenticServiceClient', FakeAgentic({'amygdala': {'level': model_level, 'reason': 'r'}}))
    result = safety.assess_deep(EMAIL, message)
    assert (result['level'], result['source']) == (expected, source)


def test_rules_crisis_never_waits_for_the_model(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeAgentic({'amygdala': {'level': 'ok'}})
    monkeypatch.setattr(safety, 'AgenticServiceClient', fake)
    assert safety.assess_deep(EMAIL, 'I want to kill myself')['level'] == 'crisis' and fake.calls == []


def test_model_down_means_rules_stand(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.spinal_cord import AgenticServiceError

    class Down:
        def create_agent_run(self, *a: Any, **k: Any) -> dict[str, Any]:
            raise AgenticServiceError('down')

    monkeypatch.setattr(safety.settings, 'brain1_safety_model_enabled', True)
    monkeypatch.setattr(safety, 'AgenticServiceClient', Down)
    assert safety.assess_deep(EMAIL, "what's the point")['level'] == 'concern'
