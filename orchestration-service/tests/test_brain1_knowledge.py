from __future__ import annotations

import pytest

from app.brain1 import knowledge

CARDS = knowledge.cards()
INTENTS = {'sharing', 'asking', 'progress', 'setback', 'venting', 'pushback', 'smalltalk'}
CHANGE_TALK = {'desire', 'ability', 'reason', 'need', 'commitment', 'activation', 'taking_steps', 'sustain', 'discord', 'none'}


def test_cards_load_with_unique_ids() -> None:
    ids = [c['id'] for c in CARDS]
    assert len(CARDS) >= 25 and len(ids) == len(set(ids))


@pytest.mark.parametrize('card', CARDS, ids=lambda c: c['id'])
def test_every_card_is_complete_and_cites_its_source(card: dict) -> None:
    assert card['core'] and card['principle'] and card['offer']
    assert card['source']['book'] and card['source']['chapter']
    assert card['review'] in ('draft', 'approved')
    when = card['use_when']
    assert set(when) <= {'intents', 'change_talk', 'did_it_today', 'feelings', 'words', 'domains'}
    assert set(when.get('intents') or []) <= INTENTS
    assert set(when.get('change_talk') or []) <= CHANGE_TALK
    assert set(card.get('avoid_when') or {}) <= {'safety', 'reason_words', 'feelings'}


def _ids(reading: dict, message: str, domain: str = 'fitness', level: str = 'ok') -> list[str]:
    return [c['id'] for c in knowledge.select(reading, message, domain, level)]


def test_a_missed_day_gets_never_miss_twice() -> None:
    assert 'AH-never-miss-twice' in _ids({'intent': 'setback', 'did_it_today': False}, "Didn't make it to the gym today.")


def test_never_miss_twice_is_not_offered_when_they_are_sick() -> None:
    reading = {'intent': 'setback', 'did_it_today': False, 'reason_given': 'I was sick with the flu'}
    assert 'AH-never-miss-twice' not in _ids(reading, "Couldn't go, I was sick")


def test_progress_gets_effort_focused_cards() -> None:
    ids = _ids({'intent': 'progress', 'did_it_today': True, 'change_talk': 'taking_steps'}, 'Did 45 minutes!')
    assert ids and all(i in {'AH-identity-votes', 'MI-affirm', 'DW-praise-process', 'AH-make-it-satisfying'} for i in ids)


def test_all_or_nothing_language_is_noticed_but_not_in_concern() -> None:
    assert 'FG-all-or-nothing' in _ids({'intent': 'setback'}, 'I always fail at this', domain='general')
    assert 'FG-all-or-nothing' not in _ids({'intent': 'setback'}, 'I always fail at this', domain='general', level='concern')


def test_words_match_whole_words_only() -> None:
    assert 'FG-should-statements' not in _ids({}, 'I shoulder everything', domain='general')
    assert 'FG-should-statements' in _ids({}, 'I should be better at this', domain='general')


def test_at_most_two_cards() -> None:
    assert len(_ids({'intent': 'setback', 'did_it_today': False, 'change_talk': 'sustain'}, 'I always fail, I should try harder, no motivation')) <= 2


def test_card_text_cites_the_book_without_ids() -> None:
    text = knowledge.as_text([c for c in CARDS if c['id'] == 'AH-two-minute-rule'])
    assert '(Atomic Habits)' in text and 'AH-two-minute-rule' not in text


@pytest.mark.parametrize('card', CARDS, ids=lambda c: c['id'])
def test_every_condition_is_text(card: dict) -> None:
    """YAML turns bare off/no/yes into booleans — that crashed a live turn once."""
    for conditions in (card['use_when'], card.get('avoid_when') or {}):
        for key, value in conditions.items():
            if isinstance(value, list):
                assert all(isinstance(v, str) for v in value), (card['id'], key, value)


def test_selection_survives_every_feeling_and_word() -> None:
    reading = {'intent': 'venting', 'feeling': 'feeling off and stressed', 'change_talk': 'none', 'did_it_today': False}
    knowledge.select(reading, 'no yes on off always should kids', 'general')  # must not raise
