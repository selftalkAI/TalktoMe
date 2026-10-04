from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx
import pytest

from app.brain1 import here_now, safety


@pytest.mark.parametrize(
    ('message', 'level'),
    [
        ("I don't want to be alive anymore", 'crisis'),
        ('sometimes I think about ending my life', 'crisis'),
        ('I wanted to die last night', 'crisis'),
        ("I don't want to be here anymore", 'crisis'),
        ('life is not worth living', 'crisis'),
        ('I keep thinking about taking my own life', 'crisis'),
        ('I want to kill myself', 'crisis'),
        ("I've been hurting myself again", 'crisis'),
        ("Honestly I can't do this anymore. What's the point.", 'concern'),
        ('I feel so alone lately', 'concern'),
        ('Missed the gym, kids were sick', 'ok'),
        ('This workout is killing me haha', 'ok'),
    ],
)
def test_safety_levels(message: str, level: str) -> None:
    assert safety.assess(message)['level'] == level


@pytest.mark.parametrize(
    ('location', 'expected'),
    [('Langley, BC, Canada', '9-8-8'), ('Austin, TX', '988'), ('London, UK', '116 123'), ('Pune, India', 'local crisis line'), (None, 'local crisis line')],
)
def test_care_message_uses_the_right_crisis_line(location: str | None, expected: str) -> None:
    message = safety.care_message('Sam', location)
    assert expected in message and message.startswith('Sam,') and message.endswith('Are you safe right now?')


@pytest.mark.parametrize(('hour', 'part'), [(6, 'morning'), (13, 'afternoon'), (19, 'evening'), (23, 'night'), (3, 'night')])
def test_part_of_day(hour: int, part: str) -> None:
    assert here_now.part_of_day(hour) == part


def test_seasons_flip_in_the_southern_hemisphere() -> None:
    assert here_now.season(1) == 'winter' and here_now.season(1, southern=True) == 'summer'


def test_weather_codes() -> None:
    assert here_now.weather_words(61) == 'rain' and here_now.weather_words(73) == 'snow' and here_now.weather_words(999) == 'unsettled weather'


class FakeResponse:
    def __init__(self, data: dict[str, Any]) -> None:
        self.data = data

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict[str, Any]:
        return self.data


def test_compute_uses_the_city_time_zone_and_weather(monkeypatch: pytest.MonkeyPatch) -> None:
    here_now._cache.clear()
    monkeypatch.setattr(here_now.settings, 'here_now_weather_enabled', True)

    def fake_get(url: str, params: dict[str, Any], timeout: float) -> FakeResponse:
        if 'geocoding' in url:
            return FakeResponse({'results': [
                {'latitude': -33.8, 'longitude': 151.2, 'country': 'Australia', 'admin1': 'NSW'},
                {'latitude': 49.1, 'longitude': -122.6, 'country': 'Canada', 'admin1': 'British Columbia', 'country_code': 'CA'},
            ]})
        return FakeResponse({'utc_offset_seconds': -7 * 3600, 'current': {'temperature_2m': 9.4, 'weather_code': 61},
                             'daily': {'temperature_2m_max': [12.2], 'sunset': ['2026-10-05T18:40']}})

    monkeypatch.setattr(here_now.httpx, 'get', fake_get)
    now = here_now.compute('Langley, BC, Canada', datetime(2026, 10, 5, 13, 5, tzinfo=timezone.utc))
    assert now['weekday'] == 'Monday' and now['local_time'] == '6:05 AM' and now['part_of_day'] == 'morning'
    assert now['season'] == 'autumn'  # picked the Canadian Langley, not the southern one
    assert now['weather'] == {'words': 'rain', 'temperature_c': 9, 'high_c': 12, 'sunset': '6:40 PM'}
    assert 'Weather: rain, 9°C (high 12°C), sunset 6:40 PM' in here_now.describe(now)


def test_weather_failure_is_silent(monkeypatch: pytest.MonkeyPatch) -> None:
    here_now._cache.clear()
    monkeypatch.setattr(here_now.settings, 'here_now_weather_enabled', True)

    def down(*a: Any, **k: Any) -> None:
        raise httpx.ConnectError('offline')

    monkeypatch.setattr(here_now.httpx, 'get', down)
    now = here_now.compute('Langley, BC, Canada')
    assert now['weather'] is None and now['city'] == 'Langley'
