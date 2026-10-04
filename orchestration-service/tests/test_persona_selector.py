from __future__ import annotations

import itertools
from typing import Any

import pytest

from app.brain1 import persona_selector as ps


class FakeMemories:
    """In-memory stand-in for memory_repo — selector tests never touch the dev DB."""

    ACTIVE = 'active'

    def __init__(self, contents: list[str] | None = None) -> None:
        self._ids = itertools.count()
        self.rows: list[dict[str, Any]] = [
            {'memory_id': f'm{next(self._ids)}', 'type': 'fact', 'domain': 'family', 'content': c, 'status': 'active'}
            for c in contents or []
        ]

    def list_memories(self, profile_email: str, status: str | None = 'active', memory_type: str | None = None, domain: str | None = None) -> list[dict[str, Any]]:
        rows = [r for r in self.rows if (status is None or r['status'] == status)]
        rows = [r for r in rows if memory_type is None or r['type'] == memory_type]
        rows = [r for r in rows if domain is None or r['domain'] == domain]
        return list(reversed(rows))  # newest first, like the real repo

    def create_memory(self, **kwargs: Any) -> dict[str, Any]:
        row = {'memory_id': f'm{next(self._ids)}', 'type': kwargs['memory_type'], 'domain': kwargs['domain'],
               'content': kwargs['content'], 'status': kwargs['status']}
        self.rows.append(row)
        return row

    def suppress_memory(self, memory_id: str, profile_email: str) -> None:
        for r in self.rows:
            if r['memory_id'] == memory_id:
                r['status'] = 'suppressed'


@pytest.fixture
def mem(monkeypatch: pytest.MonkeyPatch) -> FakeMemories:
    fake = FakeMemories()
    monkeypatch.setattr(ps, 'memory_repo', fake)
    return fake


@pytest.mark.parametrize(
    ('message', 'voice'),
    [
        ('Can you just talk to me like my sister would?', 'big_sister'),
        ('be like a big brother to me', 'big_brother'),
        ('Talk to me like a friend, less coach-y', 'friend'),
        ('Please less coach-y.', 'friend'),
        ('speak to me like my mum', 'mother_like'),
        ('talk normally again', 'clear'),
        ('I went to the gym with my sister', None),
        ('I like my coach', None),
    ],
)
def test_voice_requests_are_detected(message: str, voice: str | None) -> None:
    assert ps.detect_request(message) == voice


def test_her_choice_wins_and_persists(mem: FakeMemories) -> None:
    first = ps.select('sam@x', 'fitness', 'Talk to me like my sister would.', {'intent': 'asking'})
    later = ps.select('sam@x', 'fitness', 'How do I do squats?', {'intent': 'asking'})
    assert first['voice'] == later['voice'] == 'big_sister' and later['source'] == 'her_choice'


def test_a_new_choice_supersedes_the_old_one(mem: FakeMemories) -> None:
    ps.set_preferred_voice('sam@x', 'big_sister')
    ps.set_preferred_voice('sam@x', 'coach')
    assert ps.preferred_voice('sam@x') == 'coach'
    assert [r['status'] for r in mem.rows] == ['suppressed', 'active']


def test_clearing_returns_to_brain1_choosing(mem: FakeMemories) -> None:
    ps.select('sam@x', 'general', 'talk to me like my sister', {})
    result = ps.select('sam@x', 'general', 'talk normally please', {})
    assert result['source'] == 'selected'


def test_unknown_voice_is_refused(mem: FakeMemories) -> None:
    with pytest.raises(ValueError):
        ps.set_preferred_voice('sam@x', 'pirate')


def test_a_voice_that_could_hurt_is_blocked_even_if_chosen(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeMemories(['My mum passed away last spring.'])
    monkeypatch.setattr(ps, 'memory_repo', fake)
    result = ps.select('sam@x', 'general', 'talk to me like my mum would', {'feeling': 'exhausted'})
    assert result['voice'] != 'mother_like'


@pytest.mark.parametrize(
    ('domain', 'reading', 'voice', 'expertise'),
    [
        ('fitness', {'feeling': 'exhausted'}, 'mother_like', 'mind_emotions'),
        ('fitness', {'intent': 'asking'}, 'coach', 'fitness_coach'),
        ('fitness', {'intent': 'progress'}, 'coach', 'fitness_coach'),
        ('cooking', {'intent': 'sharing'}, 'friend', 'general'),
        ('emotion', {'intent': 'sharing'}, 'friend', 'mind_emotions'),
    ],
)
def test_brain1_picks_by_state_and_topic(mem: FakeMemories, domain: str, reading: dict[str, Any], voice: str, expertise: str) -> None:
    result = ps.select('sam@x', domain, 'hi', reading)
    assert (result['voice'], result['expertise'], result['source']) == (voice, expertise, 'selected')
