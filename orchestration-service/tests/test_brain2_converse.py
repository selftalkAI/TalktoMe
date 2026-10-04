from __future__ import annotations

from typing import Any

import pytest

from app.brain2 import orchestrator


class FakeStore:
    PROPOSED = 'proposed'

    def __init__(self, history: list[dict[str, Any]] | None = None) -> None:
        self._history = history or []
        self.proposed: list[dict[str, Any]] = []

    def history(self, profile_email: str, domain: str) -> list[dict[str, Any]]:
        return self._history

    def get_accepted(self, profile_email: str, domain: str) -> dict[str, Any] | None:
        return None

    def propose(self, **kwargs: Any) -> dict[str, Any]:
        row = {'profile_entry_id': 'p1', 'version': 1, 'status': 'proposed', **kwargs}
        self.proposed.append(row)
        return row


class FakeMemories:
    ACTIVE = 'active'

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows

    def list_memories(self, profile_email: str, status: str | None = 'active', domain: str | None = None, **_: Any) -> list[dict[str, Any]]:
        return [r for r in self.rows if domain is None or r['domain'] == domain]


def _mem(content: str, created_at: str = '2026-10-03T10:00:00', tier: str = 'T2') -> dict[str, Any]:
    return {'memory_id': content[:5], 'domain': 'fitness', 'content': content, 'created_at': created_at, 'sensitivity_tier': tier}


@pytest.fixture
def wired(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    store = FakeStore()
    memories = FakeMemories([])
    monkeypatch.setattr(orchestrator, 'profile_store', store)
    monkeypatch.setattr(orchestrator, 'memory_repo', memories)
    monkeypatch.setattr(orchestrator, '_profile_facts', lambda email: {'full_name': 'Sam Lee'})
    monkeypatch.setattr(orchestrator.intentions_repo, 'list_checkins', lambda *a, **k: [])
    monkeypatch.setattr(
        orchestrator.coach,
        'reply',
        lambda *a, **k: {'content': 'Rest night, or two easy minutes?', 'persona': {'voice': 'friend'}, 'reading': wired_reading['value'],
                         'plan': {}, 'verdict': None, 'fallback': False},
    )
    drafts: list[str] = []
    monkeypatch.setattr(orchestrator, '_run_broca', lambda email, payload: drafts.pop(0) if drafts else '')
    return {'store': store, 'memories': memories, 'drafts': drafts}


wired_reading: dict[str, Any] = {'value': {}}


@pytest.fixture(autouse=True)
def _reset_reading() -> None:
    wired_reading['value'] = {}


def test_an_ordinary_turn_is_chat_only(wired: dict[str, Any]) -> None:
    turn = orchestrator.converse('sam@x', 'fitness', 'Kids were sick.')
    assert turn['reply'] == 'Rest night, or two easy minutes?'
    assert turn['proposal'] is None and wired['store'].proposed == []


def test_a_goal_milestone_offers_a_proposal(wired: dict[str, Any]) -> None:
    wired_reading['value'] = {'did_it_today': True, 'minutes_today': 60}
    wired['drafts'].append('You reached your full hour today, after weeks of building up from shorter sessions.')
    turn = orchestrator.converse('sam@x', 'fitness', 'Did the full hour!', intention={'intention_id': 'i1', 'title': 'Gym', 'target_minutes': 60})
    assert turn['proposal'] is not None and turn['proposal']['status'] == 'proposed'


def test_enough_new_durable_facts_offer_a_proposal_but_t3_does_not_count(wired: dict[str, Any]) -> None:
    wired['memories'].rows = [_mem('Walks the dog daily'), _mem('Prefers mornings'), _mem('Back pain', tier='T3')]
    assert orchestrator.converse('sam@x', 'fitness', 'hi')['proposal'] is None
    wired['memories'].rows.append(_mem('Has two kids'))
    wired['drafts'].append('You fit movement around two kids, mornings, and daily dog walks.')
    assert orchestrator.converse('sam@x', 'fitness', 'hi')['proposal'] is not None


def test_never_two_pending_proposals_in_one_area(wired: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(orchestrator, 'profile_store', FakeStore([{'status': 'proposed', 'proposed_at': '2026-10-01'}]))
    wired_reading['value'] = {'did_it_today': True, 'minutes_today': 90}
    turn = orchestrator.converse('sam@x', 'fitness', 'Did 90!', intention={'intention_id': 'i1', 'title': 'Gym', 'target_minutes': 60})
    assert turn['proposal'] is None


def test_proactive_turns_never_propose(wired: dict[str, Any]) -> None:
    wired['memories'].rows = [_mem(f'fact {i}') for i in range(5)]
    assert orchestrator.converse('sam@x', 'fitness', '', trigger='silence')['proposal'] is None


def test_narratives_are_checked_and_rewritten(wired: dict[str, Any]) -> None:
    wired['drafts'] += ['**Fitness Journey**\n- great progress!', 'You train around a busy family life, mostly in short sessions.']
    proposal = orchestrator.propose_refinement('sam@x', 'fitness', 'Short sessions work for me.')
    assert proposal['content'] == 'You train around a busy family life, mostly in short sessions.'


def test_narrative_with_a_question_is_rejected_then_falls_back(wired: dict[str, Any]) -> None:
    wired['drafts'] += ['What will you try next?', 'How about tomorrow?']
    proposal = orchestrator.propose_refinement('sam@x', 'cooking', 'I keep burning rice.')
    assert proposal['content'].startswith('In cooking, you said')


def test_t3_memories_never_reach_a_narrative(wired: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[dict[str, Any]] = []
    monkeypatch.setattr(orchestrator, '_run_broca', lambda email, payload: sent.append(payload) or 'You keep showing up.')
    wired['memories'].rows = [_mem('Walks daily'), _mem('Has a heart condition', tier='T3')]
    orchestrator.propose_refinement('sam@x', 'fitness', '')
    assert sent[0]['domain_memories'] == ['Walks daily']
