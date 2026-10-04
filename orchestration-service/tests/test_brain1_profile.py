from __future__ import annotations

from pathlib import Path

import pytest

from app import memory_repo, profiles_repo
from app.brain1 import profile

EMAIL = 'sam@example.com'


def _profile() -> None:
    profiles_repo.upsert_profile(
        email=EMAIL, full_name='Sam Lee', password_hash='x', dob='1985-03-12', location='Langley, BC, Canada',
        interests=['healthy_living'], other_interests=None, photo_data_url=None, quote='Kind people raise kind humans.',
    )


def _remember(content: str, *, type_: str = 'fact', domain: str | None = None, tier: str = 'T2',
              explicitness: str = 'explicit', status: str = 'active') -> dict:
    return memory_repo.create_memory(
        profile_email=EMAIL, memory_type=type_, content=content, explicitness=explicitness, confidence=0.9,
        sensitivity_tier=tier, status=status, domain=domain,
    )


def test_fields_land_in_their_sections_with_evidence(temp_db: Path) -> None:
    _profile()
    kids = _remember('Has two kids, 7 and 10', type_='relationship', domain='family')
    _remember('Loves black coffee', type_='preference')
    _remember('Walks at 6am before the kids wake', type_='routine')
    _remember('Back pain since second pregnancy', domain='health', tier='T3')

    built = profile.build(EMAIL)
    s = built['sections']
    people = s['people'][0]
    assert people['value'] == 'Has two kids, 7 and 10' and people['evidence'] == [kids['memory_id']]
    assert people['status'] == 'confirmed' and people['owner'] == 'relationships.family'
    assert [f['value'] for f in s['tastes']] == ['Loves black coffee']
    assert [f['value'] for f in s['life_map']] == ['Walks at 6am before the kids wake']
    assert s['body'][0]['tier'] == 'T3'  # visible to her in the mirror, filtered from the Context Pack
    assert any(f['value'] == 'Home: Langley, BC, Canada' and f['source'] == 'onboarding' for f in s['identity'])


def test_inferred_memories_are_hypotheses(temp_db: Path) -> None:
    _profile()
    _remember('Probably prefers mornings', type_='preference', explicitness='inferred', status='requires_confirmation')
    assert profile.build(EMAIL)['sections']['tastes'][0]['status'] == 'hypothesis'


def test_suppressed_memories_are_gone(temp_db: Path) -> None:
    _profile()
    m = _remember('Loves running', type_='preference')
    memory_repo.suppress_memory(m['memory_id'], EMAIL)
    assert profile.build(EMAIL)['sections']['tastes'] == []


def test_open_questions_appear_for_empty_sections_and_close_when_answered(temp_db: Path) -> None:
    _profile()
    questions = [q['value'] for q in profile.build(EMAIL)['sections']['open_questions']]
    assert "Who's at home with you?" in questions
    _remember('Lives with partner and two kids', type_='relationship', domain='family')
    questions = [q['value'] for q in profile.build(EMAIL)['sections']['open_questions']]
    assert "Who's at home with you?" not in questions


def test_versions_are_saved_only_when_something_changed(temp_db: Path) -> None:
    _profile()
    first = profile.save_version(EMAIL, profile.build(EMAIL), reason='test')
    assert first is not None and first['version'] == 1
    assert profile.save_version(EMAIL, profile.build(EMAIL)) is None
    _remember('Loves black coffee', type_='preference')
    assert profile.save_version(EMAIL, profile.build(EMAIL))['version'] == 2


def test_strength_counts_confirmed_sections(temp_db: Path) -> None:
    _profile()
    _remember('Loves black coffee', type_='preference')
    strength = profile.build(EMAIL)['strength']
    assert strength['sections_known'] == 2 and strength['sections_total'] == 11  # identity + tastes
    assert strength['prediction_accuracy'] is None


@pytest.mark.parametrize(
    ('memory', 'section'),
    [
        ({'type': 'fact', 'domain': 'cooking', 'content': 'x'}, 'tastes'),
        ({'type': 'goal', 'domain': None, 'content': 'x'}, 'goals'),
        ({'type': 'user_instruction', 'domain': None, 'content': "Don't mention my weight"}, 'boundaries'),
        ({'type': 'learned_strategy', 'domain': None, 'content': 'x'}, 'what_works'),
        ({'type': 'event', 'domain': None, 'content': 'x'}, 'story'),
    ],
)
def test_routing(memory: dict, section: str) -> None:
    assert profile.route(memory)[0] == section


def test_learned_strategy_memories_are_allowed_by_the_schema(temp_db: Path) -> None:
    _profile()
    assert _remember('Two-minute rule works for her (4 of 5)', type_='learned_strategy')['type'] == 'learned_strategy'
