from __future__ import annotations

from dataclasses import asdict
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .agents import list_agents
from .config import settings
from .model_gateway import ModelProviderUnavailable, get_model_provider
from .workflow import WorkflowEngine

app = FastAPI(
    title='selfie.Me Agentic Service',
    version='0.1.0',
    description=(
        'The Agentic Layer: model gateway (Ollama locally / AWS Bedrock in the cloud) '
        'and, later, Bedrock Agent action-group targets. Only the Orchestration Service '
        'is expected to call this — it is never exposed to the Observability Portal directly.'
    ),
)

# Internal service-to-service traffic only. Restrict to the orchestration service's
# origin in production; this stays permissive for local development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=['http://localhost:8000'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


class CompletionIn(BaseModel):
    prompt: str = Field(..., min_length=1)
    system: str | None = None


class CompletionOut(BaseModel):
    provider: str
    response: str


class EmbeddingIn(BaseModel):
    text: str = Field(..., min_length=1)


class EmbeddingOut(BaseModel):
    provider: str
    vector: list[float]


class CreateAgentRunIn(BaseModel):
    agent: str = Field(..., description="Registered agent name, e.g. 'calendar' or 'email_digest'")
    user_id: str = Field(..., min_length=1)
    goal: str = Field(..., min_length=1)


class ApproveStepIn(BaseModel):
    step_id: str = Field(..., min_length=1)


workflow_engine = WorkflowEngine()


@app.get('/health')
def health() -> dict[str, str]:
    return {
        'status': 'ok',
        'service': 'selfie.Me Agentic Service',
        'model_provider': settings.model_provider,
    }


@app.post('/v1/complete', response_model=CompletionOut)
def complete(payload: CompletionIn) -> CompletionOut:
    provider = get_model_provider()
    try:
        response_text = provider.chat(
            [{'role': 'user', 'content': payload.prompt}], system=payload.system
        )
    except ModelProviderUnavailable as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return CompletionOut(provider=settings.model_provider, response=response_text)


@app.post('/v1/embed', response_model=EmbeddingOut)
def embed(payload: EmbeddingIn) -> EmbeddingOut:
    provider = get_model_provider()
    try:
        vector = provider.embed(payload.text)
    except ModelProviderUnavailable as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return EmbeddingOut(provider=settings.model_provider, vector=vector)


@app.get('/v1/agents')
def available_agents() -> dict[str, list[str]]:
    return {'agents': list_agents()}


@app.post('/v1/agents/runs')
def create_agent_run(payload: CreateAgentRunIn) -> dict[str, Any]:
    try:
        run = workflow_engine.create_run(payload.agent, payload.user_id, payload.goal)
        run = workflow_engine.start(run.run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return asdict(run)


@app.get('/v1/agents/runs/{run_id}')
def get_agent_run(run_id: str) -> dict[str, Any]:
    try:
        run = workflow_engine.get_run(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return asdict(run)


@app.post('/v1/agents/runs/{run_id}/approve')
def approve_agent_run_step(run_id: str, payload: ApproveStepIn) -> dict[str, Any]:
    try:
        run = workflow_engine.approve_step(run_id, payload.step_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return asdict(run)


@app.post('/v1/agents/runs/{run_id}/cancel')
def cancel_agent_run(run_id: str) -> dict[str, Any]:
    try:
        run = workflow_engine.cancel(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return asdict(run)
