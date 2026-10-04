from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Runtime configuration for the Orchestration Service (API layer + data layer).

    The Orchestration Service never talks to a model provider directly — it calls
    the Agentic Service over HTTP, which is the only thing that knows about
    Ollama/Bedrock. See ADD §4 (planes) and §8 (agentic architecture).
    """

    def __init__(self) -> None:
        self.agentic_service_url: str = os.getenv('AGENTIC_SERVICE_URL', 'http://localhost:8001')
        self.agentic_request_timeout_seconds: float = float(
            os.getenv('AGENTIC_REQUEST_TIMEOUT_SECONDS', '60')
        )
        self.cors_allow_origins: list[str] = [
            origin.strip()
            for origin in os.getenv('CORS_ALLOW_ORIGINS', 'http://localhost:3000').split(',')
            if origin.strip()
        ]
        # Brain 2's Scheduler (ADD §8.2 step 1) — how often it rechecks every
        # profile/domain for something worth drafting, with no new input.
        # Runs in-process for as long as this service is up (see brain2/scheduler.py);
        # it does not make the process itself run while the machine is asleep.
        self.brain2_scheduler_enabled: bool = os.getenv('BRAIN2_SCHEDULER_ENABLED', 'true').lower() == 'true'
        self.brain2_recheck_interval_hours: float = float(os.getenv('BRAIN2_RECHECK_INTERVAL_HOURS', '24'))
        # Brain 2 Speak candidates per reply (Building_Brain2.md §9.4.4). More = better odds of a
        # good reply, but each one is a model call — 2 is the default trade-off.
        self.brain2_speak_candidates: int = max(1, int(os.getenv('BRAIN2_SPEAK_CANDIDATES', '2')))
        # Brain 1 Here & Now (Building_Brain1.md §7.1 C13): weather for the person's onboarding city
        # via Open-Meteo. Only the city name leaves the system; turn off to keep everything local.
        self.here_now_weather_enabled: bool = os.getenv('HERE_NOW_WEATHER_ENABLED', 'true').lower() == 'true'
        self.here_now_timeout_seconds: float = float(os.getenv('HERE_NOW_TIMEOUT_SECONDS', '3'))


settings = Settings()
