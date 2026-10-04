from __future__ import annotations

from typing import Any

import pytest

from app.agents import broca, persona


@pytest.mark.parametrize('voice_id', ['friend', 'coach', 'big_sister', 'big_brother', 'mother_like', 'father_like', 'grandparent_like', 'mentor', 'buddy'])
def test_every_voice_is_complete(voice_id: str) -> None:
    v = persona.voice(voice_id)
    assert v['id'] == voice_id and v['name'] and '{first_name}' in v['identity']
    assert len(v['examples']) >= 3 and set(v['allowed_stances']) <= set(persona_stances())


def persona_stances() -> tuple[str, ...]:
    from app.agents.prefrontal_cortex import STANCES

    return STANCES


@pytest.mark.parametrize('expertise_id', ['general', 'fitness_coach', 'mind_emotions', 'nutritionist', 'sleep_guide', 'financial_analyst', 'career_mentor', 'parenting_guide', 'relationship_guide', 'skills_tutor', 'chef', 'life_designer', 'meaning_companion'])
def test_every_expertise_loads(expertise_id: str) -> None:
    assert persona.expertise(expertise_id)['id'] == expertise_id


@pytest.mark.parametrize('bad', [None, '', 'nonexistent', '../../config', 'voices/../friend'])
def test_unknown_or_unsafe_ids_fall_back(bad: Any) -> None:
    assert persona.voice(bad)['id'] == 'friend'
    assert persona.expertise(bad)['id'] == 'general'


def test_expert_limits_reach_the_prompt() -> None:
    text = persona.expertise_text(persona.expertise('fitness_coach'))
    assert 'medical diagnosis' in text and 'doctor' in text


class FakeProvider:
    def __init__(self) -> None:
        self.system = ''

    def chat(self, messages: list[dict[str, str]], *, system: str | None = None) -> str:
        self.system = system or ''
        return 'Okay. Breathe. What happened?'


def test_speak_wears_the_chosen_persona(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeProvider()
    monkeypatch.setattr(broca, 'get_model_provider', lambda tier=None: fake)
    result = broca._speak({
        'persona': {'voice': 'big_sister', 'expertise': 'mind_emotions'},
        'context_pack': {'first_name': 'Sam'},
        'latest_message': 'Rough day.',
    })
    assert 'loving big sister' in fake.system and 'therapy-informed' in fake.system
    assert 'You are an AI' in fake.system
    assert '{' not in fake.system.split('WHO THEY ARE')[0]  # every placeholder filled
    assert result['persona'] == {'voice': 'big_sister', 'expertise': 'mind_emotions'}
    assert "I've been there" in ' '.join(result['example_replies'])


def test_profile_narrative_is_not_a_chat_reply(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeProvider()
    monkeypatch.setattr(broca, 'get_model_provider', lambda tier=None: fake)
    broca._profile_narrative({'full_name': 'Sam Lee', 'domain': 'fitness', 'domain_memories': ['Has two kids']})
    assert 'No advice, no questions' in fake.system and "Sam's own profile" in fake.system


def test_family_voices_never_claim_to_be_family() -> None:
    for voice_id in ('mother_like', 'father_like', 'grandparent_like'):
        assert 'never pretend' in persona.voice(voice_id)['identity']


def test_regulated_experts_point_to_professionals() -> None:
    for expertise_id in ('financial_analyst', 'nutritionist', 'sleep_guide', 'fitness_coach', 'parenting_guide'):
        exp = persona.expertise(expertise_id)
        assert exp.get('cannot') and exp.get('always'), expertise_id
