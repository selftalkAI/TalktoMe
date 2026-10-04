from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.brain2.checks import check_reply

FIXTURE = json.loads((Path(__file__).parent / 'fixtures' / 'brain2_real_outputs_2026_10.json').read_text())

# Context a real turn would have supplied — numbers in it are legitimate.
GYM_CONTEXT = 'Goal: gym 60 min/day. Recent check-ins: 35 min, 35 min, 20 min, 45 min, 15 min.'


@pytest.mark.parametrize('reply', FIXTURE['must_reject'])
def test_every_real_bad_output_is_rejected(reply: str) -> None:
    """Building_Brain2.md §15 Phase B: every real bad output must fail Check —
    even when the numbers it uses were legitimately in context."""
    assert not check_reply(reply, allowed_text=GYM_CONTEXT).passed


# The ✅ column of the voice guide (Building_Brain2.md §9.5) — the checks must
# not be so strict that good replies fail.
GOOD_REPLIES = [
    "Two sick kids in one week — that's a full house, not a willpower problem. "
    'Two minutes tonight to keep the streak, or is it a rest night?',
    "You said this is about feeling like you again. What would that look like this week?",
    "45 minutes in a week like this one. That's you choosing to show up — "
    "exactly the 'feeling like me' you were missing.",
    'Rain on the window and a black coffee — your kind of morning. '
    'Fifteen minutes by the window before the house wakes up?',
    'Just checking in — how are the kids doing? No gym talk.',
    "Okay, no judgement — I've done it too. It keeps happening after the hard weeks, right?",
]


@pytest.mark.parametrize('reply', GOOD_REPLIES)
def test_good_replies_pass(reply: str) -> None:
    result = check_reply(reply, allowed_text=GYM_CONTEXT)
    assert result.passed, result.failures


@pytest.mark.parametrize(
    ('reply', 'expected'),
    [
        ('- Find a buddy\n- Make a playlist.', 'list'),
        ('**Celebrate progress** — well done.', 'list'),
        ('Based on the information, the user is doing well.', 'talks about her'),
        ('One specific reason why this might genuinely matter is energy.', 'copies instruction'),
        ('I want to acknowledge that this is a huge accomplishment.', 'hollow'),
        ('How was it? What got in the way?', 'questions'),
        ("Now, what I'd like to know is,", 'ends mid-sentence'),
        ('You did 90 minutes yesterday, nice.', 'numbers'),
        (' '.join(['word'] * 70) + '.', 'too long'),
        ('', 'empty'),
    ],
)
def test_each_rule_names_its_failure(reply: str, expected: str) -> None:
    result = check_reply(reply, allowed_text=GYM_CONTEXT)
    assert not result.passed
    assert any(expected in failure for failure in result.failures), result.failures


def test_repetition_of_an_earlier_reply_fails() -> None:
    earlier = 'Reaching an hour would give you more energy for weekend cycling with the kids.'
    again = 'Reaching an hour would give you more energy for weekend cycling with your kids.'
    result = check_reply(again, previous_replies=[earlier])
    assert any('repeats' in f for f in result.failures)


def test_blocked_privacy_term_fails() -> None:
    result = check_reply('How is your back doing after the pregnancy?', blocked_terms=['pregnancy'])
    assert any('private' in f for f in result.failures)


def test_feedback_lists_every_failure() -> None:
    result = check_reply('I want to acknowledge your huge accomplishment. What now? Why?')
    assert 'hollow' in result.feedback() and 'questions' in result.feedback()


def test_a_day_not_in_context_fails() -> None:
    result = check_reply('Sunday can be tough, right?', allowed_text='Today: Saturday, 3 October 2026')
    assert any('day not in the context' in f for f in result.failures)
    assert check_reply('Saturday mornings are yours.', allowed_text='Today: Saturday').passed
