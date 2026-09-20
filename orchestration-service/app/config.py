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


settings = Settings()
