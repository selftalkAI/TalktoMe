from __future__ import annotations

from app.brain2 import plan_rules


def test_their_question_is_answered_first_and_not_answered_with_a_question() -> None:
    plan = plan_rules.apply(
        {'stance': 'listen', 'moves': ['open_question', 'reflect']},
        {'asked_question': 'How do I do that at home?'},
    )
    assert plan['moves'][0] == 'answer_question'
    assert 'open_question' not in plan['moves']
    assert plan['stance'] == 'teach'


def test_pushback_is_met_with_listening_not_defending() -> None:
    plan = plan_rules.apply(
        {'stance': 'challenge', 'moves': ['offer_idea'], 'idea': 'Try 20 minutes instead'},
        {'change_talk': 'discord'},
    )
    assert plan['stance'] == 'listen' and plan['moves'] == ['reflect', 'open_question'] and plan['idea'] is None


def test_a_missed_day_is_never_celebrated() -> None:
    plan = plan_rules.apply({'stance': 'celebrate', 'moves': ['celebrate', 'affirm']}, {'did_it_today': False})
    assert plan['stance'] == 'listen' and 'celebrate' not in plan['moves']
    assert 'did NOT do it today' in plan['words']


def test_progress_defaults_to_celebrating_with_the_real_number() -> None:
    plan = plan_rules.apply({}, {'intent': 'progress', 'did_it_today': True, 'minutes_today': 45})
    assert plan['stance'] == 'celebrate' and 'today they did 45 minutes' in plan['words']


def test_invalid_model_choices_fall_back_to_safe_defaults() -> None:
    plan = plan_rules.apply({'stance': 'lecture', 'moves': ['dance']}, {})
    assert plan['stance'] == 'listen' and plan['moves'] == ['reflect', 'open_question']


def test_an_idea_without_an_offer_move_is_dropped() -> None:
    plan = plan_rules.apply({'stance': 'listen', 'moves': ['reflect'], 'idea': 'HIIT'}, {})
    assert plan['idea'] is None and 'HIIT' not in plan['words']


def test_their_reason_is_acknowledged() -> None:
    plan = plan_rules.apply({}, {'intent': 'setback', 'did_it_today': False, 'reason_given': 'kids were sick'})
    assert 'kids were sick' in plan['words']


def test_proactive_plans_stay_gentle_and_escalate_lighter() -> None:
    first = plan_rules.apply({'stance': 'challenge'}, {}, trigger='silence')
    later = plan_rules.apply({}, {}, trigger='silence', escalation_level=2)
    assert first['stance'] == 'listen' and 'not the goal' in first['words']
    assert 'even lighter' in later['words']


def test_asked_if_human_the_plan_says_it_is_an_ai() -> None:
    plan = plan_rules.apply({}, {'asked_question': 'Are you a real person?'})
    assert plan['moves'][0] == 'answer_question' and 'you are an AI' in plan['words']
    assert 'Brain 2' not in plan['words']  # the Check rejects internal names, so the plan must not use them
