from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app import conversations_repo, memory_manager, memory_repo, profiles_repo
from app.brain1 import consent, context_pack, patterns, profile, tools

EMAIL = 'sam@x'


@pytest.fixture
def sam(temp_db: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(context_pack.here_now, 'compute', lambda location, now_utc=None: {
        'city': None, 'local_time': '9:00 AM', 'weekday': 'Monday', 'date': '5 October 2026', 'part_of_day': 'morning',
        'season': 'autumn', 'weather': None})
    profiles_repo.upsert_profile(email=EMAIL, full_name='Sam Lee', password_hash='x', dob=None, location=None,
                                 interests=[], other_interests=None, photo_data_url=None, quote=None)


def _t3(content: str, domain: str = 'health', status: str = 'requires_confirmation') -> dict:
    return memory_repo.create_memory(profile_email=EMAIL, memory_type='fact', content=content, explicitness='explicit',
                                     confidence=0.9, sensitivity_tier='T3', status=status, domain=domain)


# --- consent -------------------------------------------------------------------------

@pytest.mark.parametrize(('item', 'category'), [
    ({'content': 'Back pain since pregnancy', 'domain': 'health'}, 'health'),
    ({'content': 'Has $20k of credit card debt'}, 'finances'),
    ({'value': 'Salary went down this year', 'area': 'work'}, 'finances'),
])
def test_categories(item: dict, category: str) -> None:
    assert consent.category_of(item) == category


def test_private_details_stay_out_until_she_opts_in(sam: None) -> None:
    back = _t3('Back pain since second pregnancy')
    assert 'Back pain' not in json.dumps(context_pack.compile(EMAIL, 'fitness'))
    assert 'Back pain' not in tools.search_memories(EMAIL, 'back pain')

    result = consent.set_consent(EMAIL, 'health', True)
    assert result['memories_changed'] == 1 and memory_repo.get_memory(back['memory_id'], EMAIL)['status'] == 'active'
    assert 'Back pain' in context_pack.compile(EMAIL, 'fitness')['loves']
    assert 'Back pain' in tools.search_memories(EMAIL, 'back pain')

    consent.set_consent(EMAIL, 'health', False)
    assert memory_repo.get_memory(back['memory_id'], EMAIL)['status'] == 'suppressed'
    assert 'Back pain' not in json.dumps(context_pack.compile(EMAIL, 'fitness'))


def test_consent_for_health_does_not_open_finances(sam: None) -> None:
    _t3('Has credit card debt', domain='money', status='active')
    consent.set_consent(EMAIL, 'health', True)
    assert 'debt' not in json.dumps(context_pack.compile(EMAIL, 'money'))


def test_write_gate_respects_consent(sam: None) -> None:
    candidate = {'type': 'fact', 'content': 'Has asthma', 'domain': 'health', 'confidence': 0.9,
                 'explicitness': 'explicit', 'sensitivity_tier': 'T3'}
    assert memory_manager._apply_write_gate(EMAIL, candidate, 'conversation', 't1')['status'] == 'requires_confirmation'
    consent.set_consent(EMAIL, 'health', True)
    candidate['content'] = 'Uses an inhaler before runs'
    assert memory_manager._apply_write_gate(EMAIL, candidate, 'conversation', 't2')['status'] == 'active'


def test_consent_is_asked_once_per_category(sam: None) -> None:
    new = [{'sensitivity_tier': 'T3', 'content': 'Back pain', 'domain': 'health'}, {'sensitivity_tier': 'T2', 'content': 'x'}]
    assert [r['category'] for r in consent.pending_requests(EMAIL, new)] == ['health']
    consent.set_consent(EMAIL, 'health', False)
    assert consent.pending_requests(EMAIL, new) == []


def test_unknown_category_is_refused(sam: None) -> None:
    with pytest.raises(ValueError):
        consent.set_consent(EMAIL, 'politics', True)


# --- patterns ---------------------------------------------------------------------------

def test_grounding_needs_two_real_quotes_from_two_notes() -> None:
    items = ["Mon: couldn't go, kids were sick", 'Wed: kids sick again, no gym', 'Fri: did 30 minutes']
    assert patterns.grounded(['kids were sick', 'kids sick again'], items)
    assert not patterns.grounded(['kids were sick', 'kids were sick'], items[:1] + items[2:])  # one note only
    assert not patterns.grounded(['kids were sick', 'work was crazy'], items)  # second quote invented


class FakeAgentic:
    def __init__(self, found: list[dict[str, Any]]) -> None:
        self.found = found

    def __call__(self) -> 'FakeAgentic':
        return self

    def create_agent_run(self, agent: str, user_id: str, goal: str) -> dict[str, Any]:
        return {'status': 'completed', 'steps': [{'result': {'patterns': self.found}}]}


def test_grounded_patterns_become_hypotheses_and_ungrounded_ones_are_dropped(sam: None, monkeypatch: pytest.MonkeyPatch) -> None:
    for text in ["couldn't go, kids were sick", 'kids sick again so no gym', 'did 30 minutes, felt good']:
        conversations_repo.append(EMAIL, 'fitness', 'user', text)
    monkeypatch.setattr(patterns, 'AgenticServiceClient', FakeAgentic([
        {'pattern': 'Your missed gym days tend to be sick-kid days.', 'evidence': ['kids were sick', 'kids sick again']},
        {'pattern': 'You skip when work is busy.', 'evidence': ['work is busy', 'deadline']},
    ]))
    created = patterns.detect(EMAIL)
    assert [m['content'] for m in created] == ['Your missed gym days tend to be sick-kid days.']
    assert created[0]['status'] == 'requires_confirmation' and created[0]['explicitness'] == 'inferred'
    assert patterns.detect(EMAIL) == []  # already known
    assert 'sick-kid days' in context_pack.compile(EMAIL, 'fitness')['unknowns']
    assert profile.route(created[0])[0] == 'goals'


def test_brain_strength_measures_patterns_and_corrections(sam: None) -> None:
    built = profile.build(EMAIL)['strength']
    assert built['prediction_accuracy'] is None and built['correction_rate'] is None
    a = memory_repo.create_memory(profile_email=EMAIL, memory_type='fact', content='p1', explicitness='inferred', confidence=0.6,
                                  sensitivity_tier='T2', status='requires_confirmation', source_type='pattern')
    b = memory_repo.create_memory(profile_email=EMAIL, memory_type='fact', content='p2', explicitness='inferred', confidence=0.6,
                                  sensitivity_tier='T2', status='requires_confirmation', source_type='pattern')
    memory_repo.confirm_memory(a['memory_id'], EMAIL)
    memory_repo.suppress_memory(b['memory_id'], EMAIL)
    fact = memory_repo.create_memory(profile_email=EMAIL, memory_type='fact', content='Works nights', explicitness='explicit',
                                     confidence=0.9, sensitivity_tier='T2', status='active')
    memory_repo.correct_memory(fact['memory_id'], EMAIL, 'Works evenings')
    strength = profile.build(EMAIL)['strength']
    assert strength['prediction_accuracy'] == 0.5
    assert strength['correction_rate'] == round(1 / 3, 2)  # 1 correction over 3 things Brain 1 recorded


def test_skipped_questions_stay_skipped(sam: None) -> None:
    question = profile.build(EMAIL)['sections']['open_questions'][0]
    assert profile.set_question_status(EMAIL, question['question_id'], 'dropped')
    assert question['value'] not in [q['value'] for q in profile.build(EMAIL)['sections']['open_questions']]
