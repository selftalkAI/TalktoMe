from __future__ import annotations

from pathlib import Path

import pytest

from app import memory_repo, profiles_repo
from app.brain1 import context_pack, persona_selector

EMAIL = 'sam@example.com'
NOW = {'city': 'Langley', 'local_time': '6:05 AM', 'weekday': 'Monday', 'date': '5 October 2026', 'part_of_day': 'morning',
       'season': 'autumn', 'weather': {'words': 'rain', 'temperature_c': 9, 'high_c': 12, 'sunset': '6:40 PM'}}


@pytest.fixture
def sam(temp_db: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(context_pack.here_now, 'compute', lambda location, now_utc=None: dict(NOW))
    profiles_repo.upsert_profile(email=EMAIL, full_name='Sam Lee', password_hash='x', dob=None, location='Langley, BC, Canada',
                                 interests=[], other_interests=None, photo_data_url=None, quote=None)
    for content, type_, domain, tier in [
        ('Has two kids, 7 and 10', 'relationship', 'family', 'T2'),
        ('Loves rainy mornings and black coffee', 'preference', None, 'T2'),
        ('Back pain since second pregnancy', 'fact', 'health', 'T3'),
        ('Struggles to fit the gym in', 'constraint', None, 'T2'),
    ]:
        memory_repo.create_memory(profile_email=EMAIL, memory_type=type_, content=content, explicitness='explicit',
                                  confidence=0.9, sensitivity_tier=tier, status='active', domain=domain)
    persona_selector.set_preferred_voice(EMAIL, 'big_sister')


def test_pack_has_her_life_and_her_moment(sam: None) -> None:
    pack = context_pack.compile(EMAIL, 'fitness')
    assert pack['first_name'] == 'Sam'
    assert 'Has two kids' in pack['who']
    assert 'Monday 5 October 2026, 6:05 AM (morning), autumn in Langley. Weather: rain, 9°C' in pack['today']
    assert 'Loves rainy mornings and black coffee' in pack['loves']


def test_t3_and_system_fields_never_enter_the_pack(sam: None) -> None:
    text = ' '.join(str(v) for v in context_pack.compile(EMAIL, 'fitness').values())
    assert 'Back pain' not in text and 'pregnancy' not in text
    assert 'big_sister' not in text and 'big sister' not in text


def test_hooks_pair_the_moment_with_what_she_loves_not_her_struggles(sam: None) -> None:
    hooks = context_pack.compile(EMAIL, 'fitness')['hooks']
    assert 'Monday morning, rain, 9°C' in hooks and 'black coffee' in hooks
    assert 'Struggles' not in hooks


def test_unknowns_are_offered_as_optional_questions(sam: None) -> None:
    unknowns = context_pack.compile(EMAIL, 'fitness')['unknowns']
    assert unknowns.startswith('- Ask only if it fits naturally:') and "Who's at home" not in unknowns  # she told us


def test_numbers_and_days_in_the_pack_are_allowed_in_replies(sam: None) -> None:
    allowed = context_pack.compile(EMAIL, 'fitness')['allowed_text']
    assert 'Monday' in allowed and '9' in allowed


def test_facts_from_other_areas_stay_out(sam: None) -> None:
    memory_repo.create_memory(profile_email=EMAIL, memory_type='routine', content='Gym at 6am, 35 minutes', explicitness='explicit',
                              confidence=0.9, sensitivity_tier='T2', status='active', domain='fitness')
    assert 'Gym at 6am' not in context_pack.compile(EMAIL, 'career')['loves']
    assert 'Gym at 6am' in context_pack.compile(EMAIL, 'fitness')['loves']
    assert 'black coffee' in context_pack.compile(EMAIL, 'career')['loves']  # general facts still shared
