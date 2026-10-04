from __future__ import annotations

from pathlib import Path

import pytest

from app import memory_repo
from app.brain1 import knowledge, learning, persona_selector, reflector, runs
from app.brain2 import plan_rules

EMAIL = 'sam@x'


def _reply(cards: list[str] | None = None, voice: str = 'friend', stance: str = 'listen', safety: str = 'ok') -> str:
    """Records one Brain 2 reply trace, as coach._finish does."""
    trace = {'cards': cards or [], 'persona': {'voice': voice, 'expertise': 'general'}, 'plan': {'stance': stance}}
    return runs.record(EMAIL, 'message', safety, trace, 10)


@pytest.mark.parametrize(
    ('reading', 'outcome'),
    [
        ({'change_talk': 'discord'}, 'discord'),
        ({'intent': 'pushback', 'change_talk': 'none'}, 'discord'),
        ({'did_it_today': True}, 'took_action'),
        ({'change_talk': 'taking_steps'}, 'took_action'),
        ({'change_talk': 'commitment'}, 'change_talk'),
        ({'change_talk': 'sustain'}, 'sustain'),
        ({'change_talk': 'none', 'intent': 'sharing'}, None),
    ],
)
def test_outcomes_from_their_next_message(reading: dict, outcome: str | None) -> None:
    assert learning.outcome_from_reading(reading) == outcome


def test_their_next_message_scores_the_previous_reply_once(temp_db: Path) -> None:
    _reply(cards=['AH-two-minute-rule'])
    assert learning.score_previous_turn(EMAIL, reading={'did_it_today': True}) == 'took_action'
    assert learning.score_previous_turn(EMAIL, reading={'did_it_today': True}) is None  # already scored
    assert learning.weights(EMAIL)['cards']['AH-two-minute-rule']['counts'] == {'took_action': 1}


def test_crisis_replies_are_never_scored(temp_db: Path) -> None:
    _reply(voice='care', safety='crisis')
    assert learning.score_previous_turn(EMAIL, outcome='silence') is None


def test_one_bad_reply_never_locks_an_approach_out(temp_db: Path) -> None:
    _reply(stance='challenge')
    learning.score_previous_turn(EMAIL, outcome='discord')
    assert 'challenge' not in learning.avoided(EMAIL)['stances']
    _reply(stance='challenge')
    learning.score_previous_turn(EMAIL, outcome='discord')
    assert 'challenge' in learning.avoided(EMAIL)['stances']


def test_preferred_needs_three_good_outcomes(temp_db: Path) -> None:
    for i in range(3):
        _reply(cards=['AH-two-minute-rule'])
        learning.score_previous_turn(EMAIL, outcome='took_action' if i < 2 else 'change_talk')
        assert ('AH-two-minute-rule' in learning.preferred(EMAIL)['cards']) is (i == 2)
    assert 'Works for them: "Scale a habit down' in learning.works_text(EMAIL)


def test_avoided_cards_voices_and_stances_change_what_brain2_does(temp_db: Path) -> None:
    for _ in range(2):
        _reply(cards=['AH-never-miss-twice'], voice='coach', stance='challenge')
        learning.score_previous_turn(EMAIL, outcome='discord')
    avoid = learning.avoided(EMAIL)

    reading = {'intent': 'setback', 'did_it_today': False}
    assert 'AH-never-miss-twice' in [c['id'] for c in knowledge.select(reading, 'missed it', 'fitness')]
    assert 'AH-never-miss-twice' not in [c['id'] for c in knowledge.select(reading, 'missed it', 'fitness', avoid_ids=avoid['cards'])]

    assert persona_selector.select(EMAIL, 'fitness', 'how do I start?', {'intent': 'asking'}, avoid['voices'])['voice'] != 'coach'
    persona_selector.set_preferred_voice(EMAIL, 'coach')  # her explicit choice still wins
    assert persona_selector.select(EMAIL, 'fitness', 'hi', {}, avoid['voices'])['voice'] == 'coach'

    plan = plan_rules.apply({'stance': 'challenge', 'moves': ['reflect']}, {}, avoid_stances=avoid['stances'])
    assert plan['stance'] == 'listen'
    assert 'Avoid: a challenge approach' in learning.works_text(EMAIL)


def test_accepting_a_proposal_credits_the_latest_reply(temp_db: Path) -> None:
    _reply(cards=['MI-affirm'])
    learning.score_previous_turn(EMAIL, outcome='change_talk')
    assert learning.record_for_latest_run(EMAIL, 'accepted')
    assert learning.weights(EMAIL)['cards']['MI-affirm']['n'] == 2


def test_reflection_writes_supersedes_and_retires_strategies(temp_db: Path) -> None:
    for _ in range(3):
        _reply(cards=['AH-two-minute-rule'])
        learning.score_previous_turn(EMAIL, outcome='took_action')

    first = reflector.run_for_profile(EMAIL)
    strategies = memory_repo.list_memories(EMAIL, memory_type='learned_strategy')
    assert len(first['strategies']) == len(strategies) == 3  # the card, the friend voice, the listen stance
    assert all(m['explicitness'] == 'inferred' and m['status'] == 'active' for m in strategies)
    assert reflector.run_for_profile(EMAIL)['strategies'] == []  # nothing changed, nothing rewritten

    _reply(cards=['AH-two-minute-rule'])
    learning.score_previous_turn(EMAIL, outcome='took_action')
    assert len(reflector.run_for_profile(EMAIL)['strategies']) == 3  # counts changed → new versions
    assert len(memory_repo.list_memories(EMAIL, status='suppressed', memory_type='learned_strategy')) == 3

    # Six pushbacks on the same card and voice, with a 'plan' stance: card and voice
    # fall to a mixed record (4 helped, 6 didn't) → retired; 'plan' becomes something to avoid;
    # 'listen' keeps its 4-of-4 record → untouched.
    for _ in range(6):
        _reply(cards=['AH-two-minute-rule'], stance='plan')
        learning.score_previous_turn(EMAIL, outcome='discord')
    third = reflector.run_for_profile(EMAIL)
    assert third['strategies'] == ["A plan approach tends not to land with them (0 of 6 times it helped, 6 times it didn't land)."]
    assert len(third['retired']) == 2 and all('tends to help them' in r for r in third['retired'])
    active = [m['content'] for m in memory_repo.list_memories(EMAIL, memory_type='learned_strategy')]
    assert len(active) == 2 and any(a.startswith('A listen approach tends to help') for a in active)
