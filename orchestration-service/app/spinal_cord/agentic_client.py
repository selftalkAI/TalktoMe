from __future__ import annotations

import httpx

from ..config import settings


class AgenticServiceError(RuntimeError):
    """Raised when the Agentic Service cannot fulfill a request."""


class AgenticServiceClient:
    """The Orchestration Service's only path to a model/agent capability.

    No other module in this service is allowed to call Ollama, Bedrock, or the
    agent workflow engine directly — that boundary is what keeps the Agentic
    Layer swappable (local Ollama today, AWS Bedrock Agents later) without
    touching Orchestration's business logic, and keeps the Observability
    Portal from ever reaching the Agentic Service on its own.
    """

    def __init__(self, base_url: str | None = None, timeout: float | None = None) -> None:
        self.base_url = (base_url or settings.agentic_service_url).rstrip('/')
        self.timeout = timeout or settings.agentic_request_timeout_seconds

    def complete(self, prompt: str, system: str | None = None) -> dict:
        return self._post('/v1/complete', {'prompt': prompt, 'system': system})

    def embed(self, text: str) -> dict:
        return self._post('/v1/embed', {'text': text})

    def list_agents(self) -> dict:
        return self._get('/v1/agents')

    def create_agent_run(self, agent: str, user_id: str, goal: str) -> dict:
        return self._post('/v1/agents/runs', {'agent': agent, 'user_id': user_id, 'goal': goal})

    def get_agent_run(self, run_id: str) -> dict:
        return self._get(f'/v1/agents/runs/{run_id}')

    def approve_agent_run_step(self, run_id: str, step_id: str) -> dict:
        return self._post(f'/v1/agents/runs/{run_id}/approve', {'step_id': step_id})

    def cancel_agent_run(self, run_id: str) -> dict:
        return self._post(f'/v1/agents/runs/{run_id}/cancel', {})

    def _get(self, path: str) -> dict:
        try:
            response = httpx.get(f'{self.base_url}{path}', timeout=self.timeout)
            response.raise_for_status()
        except httpx.ConnectError as exc:
            raise AgenticServiceError(self._unreachable_message()) from exc
        except httpx.HTTPStatusError as exc:
            raise AgenticServiceError(self._error_detail(exc)) from exc
        return response.json()

    def _post(self, path: str, payload: dict) -> dict:
        try:
            response = httpx.post(f'{self.base_url}{path}', json=payload, timeout=self.timeout)
            response.raise_for_status()
        except httpx.ConnectError as exc:
            raise AgenticServiceError(self._unreachable_message()) from exc
        except httpx.HTTPStatusError as exc:
            raise AgenticServiceError(self._error_detail(exc)) from exc
        return response.json()

    def _unreachable_message(self) -> str:
        return (
            f'Could not reach the Agentic Service at {self.base_url}. '
            'Is it running (uvicorn app.main:app --port 8001)?'
        )

    @staticmethod
    def _error_detail(exc: httpx.HTTPStatusError) -> str:
        try:
            return exc.response.json().get('detail', exc.response.text)
        except ValueError:
            return exc.response.text
