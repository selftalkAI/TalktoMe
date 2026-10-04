from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from ..config import settings

# Brain 1's Here & Now core (Building_Brain1.md §7.1 C13, §8.1 live section):
# what their world is like right now — local time, part of day, season, and
# the weather in their home city. Computed per turn, never stored. Privacy
# (approved default): only the city name from onboarding leaves the system;
# precise location would need opt-in. Weather comes from Open-Meteo (no key,
# no account); any failure simply leaves the weather out.

_GEOCODE_URL = 'https://geocoding-api.open-meteo.com/v1/search'
_FORECAST_URL = 'https://api.open-meteo.com/v1/forecast'
_CACHE_SECONDS = 30 * 60
_cache: dict[str, tuple[float, dict[str, Any] | None]] = {}

# WMO weather codes → plain words.
_WEATHER_WORDS = (
    ((0,), 'clear skies'),
    ((1, 2), 'partly cloudy'),
    ((3,), 'overcast'),
    ((45, 48), 'fog'),
    ((51, 53, 55, 56, 57), 'drizzle'),
    ((61, 63, 66, 80, 81), 'rain'),
    ((65, 67, 82), 'heavy rain'),
    ((71, 73, 77, 85), 'snow'),
    ((75, 86), 'heavy snow'),
    ((95, 96, 99), 'thunderstorms'),
)


def compute(location: str | None, now_utc: datetime | None = None) -> dict[str, Any]:
    """The live Here & Now: `local_time`, `weekday`, `date`, `part_of_day`,
    `season`, `city`, and `weather` (or None). Uses the city's own time zone
    when the weather lookup succeeds, else the server's local time."""
    now_utc = now_utc or datetime.now(timezone.utc)
    place = _lookup(location) if location and settings.here_now_weather_enabled else None

    if place and place.get('utc_offset_seconds') is not None:
        local = now_utc + timedelta(seconds=place['utc_offset_seconds'])
    else:
        local = now_utc.astimezone()
    southern = bool(place and place.get('latitude', 0) < 0)

    return {
        'city': (location or '').split(',')[0].strip() or None,
        'local_time': local.strftime('%I:%M %p').lstrip('0'),
        'weekday': local.strftime('%A'),
        'date': f"{local.day} {local.strftime('%B %Y')}",
        'part_of_day': part_of_day(local.hour),
        'season': season(local.month, southern),
        'weather': place.get('weather') if place else None,
    }


def describe(now: dict[str, Any]) -> str:
    """One plain-language line for the Context Pack."""
    line = f"{now['weekday']} {now['date']}, {now['local_time']} ({now['part_of_day']}), {now['season']}"
    if now.get('city'):
        line += f" in {now['city']}"
    weather = now.get('weather')
    if weather:
        line += f". Weather: {weather['words']}, {weather['temperature_c']}°C"
        if weather.get('high_c') is not None:
            line += f" (high {weather['high_c']}°C)"
        if weather.get('sunset'):
            line += f", sunset {weather['sunset']}"
    return line + '.'


def part_of_day(hour: int) -> str:
    if 5 <= hour < 12:
        return 'morning'
    if 12 <= hour < 17:
        return 'afternoon'
    if 17 <= hour < 21:
        return 'evening'
    return 'night'


def season(month: int, southern: bool = False) -> str:
    north = {12: 'winter', 1: 'winter', 2: 'winter', 3: 'spring', 4: 'spring', 5: 'spring',
             6: 'summer', 7: 'summer', 8: 'summer', 9: 'autumn', 10: 'autumn', 11: 'autumn'}[month]
    if not southern:
        return north
    return {'winter': 'summer', 'summer': 'winter', 'spring': 'autumn', 'autumn': 'spring'}[north]


def weather_words(code: int | None) -> str:
    for codes, words in _WEATHER_WORDS:
        if code in codes:
            return words
    return 'unsettled weather'


def _lookup(location: str) -> dict[str, Any] | None:
    key = location.strip().lower()
    cached = _cache.get(key)
    if cached and time.monotonic() - cached[0] < _CACHE_SECONDS:
        return cached[1]
    try:
        place = _geocode(location)
        result = _forecast(place) if place else None
    except (httpx.HTTPError, KeyError, ValueError, TypeError):
        result = None
    _cache[key] = (time.monotonic(), result)
    return result


def _geocode(location: str) -> dict[str, Any] | None:
    parts = [p.strip() for p in location.split(',') if p.strip()]
    response = httpx.get(_GEOCODE_URL, params={'name': parts[0], 'count': 10}, timeout=settings.here_now_timeout_seconds)
    response.raise_for_status()
    results = response.json().get('results') or []
    hints = {p.lower() for p in parts[1:]}

    def score(r: dict[str, Any]) -> int:
        names = {str(r.get(k, '')).lower() for k in ('country', 'country_code', 'admin1')}
        return sum(1 for h in hints if any(h == n or h in n for n in names if n))

    return max(results, key=score) if results else None


def _forecast(place: dict[str, Any]) -> dict[str, Any]:
    response = httpx.get(
        _FORECAST_URL,
        params={
            'latitude': place['latitude'],
            'longitude': place['longitude'],
            'current': 'temperature_2m,weather_code',
            'daily': 'temperature_2m_max,sunset',
            'timezone': 'auto',
            'forecast_days': 1,
        },
        timeout=settings.here_now_timeout_seconds,
    )
    response.raise_for_status()
    data = response.json()
    current, daily = data['current'], data.get('daily') or {}
    sunset = (daily.get('sunset') or [None])[0]
    return {
        'latitude': place['latitude'],
        'utc_offset_seconds': data.get('utc_offset_seconds'),
        'weather': {
            'words': weather_words(current.get('weather_code')),
            'temperature_c': round(current['temperature_2m']),
            'high_c': round(daily['temperature_2m_max'][0]) if daily.get('temperature_2m_max') else None,
            'sunset': datetime.fromisoformat(sunset).strftime('%I:%M %p').lstrip('0') if sunset else None,
        },
    }
