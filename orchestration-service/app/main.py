from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .clients import AgenticServiceClient, AgenticServiceError
from .config import settings

app = FastAPI(
    title='selfie.Me Orchestration Service',
    version='0.2.0',
    description=(
        'API layer + data layer for selfie.Me. Owns Moments (this person\'s own captured '
        'thoughts) and reflects them back using only that person\'s own history — never '
        'outside opinions, other people\'s data, or generic advice.'
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

# A moment's photo attachment is stored inline for MVP (no object storage wired yet).
# Kept intentionally small so a single process's memory can't be exhausted by uploads.
MAX_PHOTO_DATA_URL_LENGTH = 2_000_000  # ~1.5MB image, base64-encoded


class MomentIn(BaseModel):
    source: str = Field(..., description="'text', 'voice', or 'photo'")
    content: str = Field(..., min_length=1, description='What you said, typed, or transcribed')
    mood: str | None = Field(default=None, description='How you were feeling, in your own word')
    photo_data_url: str | None = Field(default=None, description='Optional small inline image (data URL)')


class MomentOut(BaseModel):
    id: str
    created_at: datetime
    source: str
    content: str
    mood: str | None = None
    photo_data_url: str | None = None
    reflection: str | None = None


class ReflectionOut(BaseModel):
    moment_id: str
    reflection: str
    referenced_past_count: int


class ChatCompletionIn(BaseModel):
    prompt: str = Field(..., min_length=1)
    system: str | None = None


class ChatCompletionOut(BaseModel):
    provider: str
    response: str


class CreateAgentRunIn(BaseModel):
    agent: str = Field(..., description="Registered agent name, e.g. 'calendar' or 'email_digest'")
    user_id: str = Field(..., min_length=1)
    goal: str = Field(..., min_length=1)


class ApproveStepIn(BaseModel):
    step_id: str = Field(..., min_length=1)


MOMENTS: list[MomentOut] = []


@app.get('/health')
def health() -> dict[str, str]:
    return {'status': 'ok', 'service': 'selfie.Me Orchestration Service'}


@app.post('/api/v1/moments', response_model=MomentOut)
def create_moment(payload: MomentIn) -> MomentOut:
    if payload.photo_data_url and len(payload.photo_data_url) > MAX_PHOTO_DATA_URL_LENGTH:
        raise HTTPException(status_code=413, detail='Photo is too large for this MVP (limit ~1.5MB).')

    moment = MomentOut(
        id=f'mom_{len(MOMENTS) + 1:04d}',
        created_at=datetime.now(timezone.utc),
        source=payload.source,
        content=payload.content,
        mood=payload.mood,
        photo_data_url=payload.photo_data_url,
    )
    MOMENTS.append(moment)
    return moment


@app.get('/api/v1/moments', response_model=list[MomentOut])
def list_moments() -> list[MomentOut]:
    return list(reversed(MOMENTS))  # most recent first


def _find_moment(moment_id: str) -> MomentOut:
    for moment in MOMENTS:
        if moment.id == moment_id:
            return moment
    raise HTTPException(status_code=404, detail=f'Unknown moment {moment_id}')


def _moment_payload(moment: MomentOut) -> dict[str, Any]:
    return {'content': moment.content, 'mood': moment.mood, 'created_at': moment.created_at.isoformat()}


def _run_smart_agent(mode: str, **payload: Any) -> dict[str, Any]:
    """Runs the 'smart' agent through the real agent pipeline (plan -> policy -> execute -> audit),

    not a raw model call. This is the pattern every future domain agent (finance, fun,
    time-management, ...) will follow — Orchestration owns the data, the Agentic Layer owns
    the reasoning about it, and the run is planned/authorized/observed like any other agent.
    """
    client = AgenticServiceClient()
    goal = json.dumps({'mode': mode, **payload})
    try:
        run = client.create_agent_run('smart', user_id='local-user', goal=goal)
    except AgenticServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if run.get('status') != 'completed':
        steps = run.get('steps') or []
        error = steps[0].get('result', {}).get('error') if steps else None
        raise HTTPException(status_code=502, detail=error or f"Smart agent run ended as '{run.get('status')}'.")

    steps = run.get('steps') or []
    result = steps[0].get('result') if steps else None
    if not result:
        raise HTTPException(status_code=502, detail='Smart agent run produced no result.')
    return result


@app.post('/api/v1/moments/{moment_id}/reflect', response_model=ReflectionOut)
def reflect_on_moment(moment_id: str) -> ReflectionOut:
    """Reflects one moment back using ONLY this person's own prior moments as context —

    routed through the 'smart' agent run, so it's planned, policy-checked (READ_ONLY,
    auto-approved), and recorded in an audit trail like any other agent action.
    """
    moment = _find_moment(moment_id)
    past_moments = [m for m in MOMENTS if m.id != moment_id][-30:]

    result = _run_smart_agent(
        'reflect_moment',
        moment=_moment_payload(moment),
        past_moments=[_moment_payload(m) for m in past_moments],
    )

    moment.reflection = result['reflection']
    return ReflectionOut(
        moment_id=moment.id,
        reflection=result['reflection'],
        referenced_past_count=result.get('referenced_past_count', 0),
    )


@app.get('/api/v1/evolution')
def evolution(days: int = Query(default=30, ge=1, le=3650)) -> dict[str, Any]:
    """Purely computed from this person's own stored moments — no model call, no outside data."""
    now = datetime.now(timezone.utc)
    window_cutoff = now - timedelta(days=days)
    today = now.date()

    in_window = [m for m in MOMENTS if m.created_at >= window_cutoff]
    today_moments = [m for m in MOMENTS if m.created_at.date() == today]
    earlier_than_window = [m for m in MOMENTS if m.created_at < window_cutoff]

    mood_counts: dict[str, int] = {}
    for m in in_window:
        key = m.mood or 'unspecified'
        mood_counts[key] = mood_counts.get(key, 0) + 1

    return {
        'range_days': days,
        'total_moments_all_time': len(MOMENTS),
        'moments_in_range': len(in_window),
        'moments_today': len(today_moments),
        'mood_counts_in_range': mood_counts,
        'has_history_before_range': len(earlier_than_window) > 0,
    }


@app.get('/api/v1/evolution/narrative')
def evolution_narrative(days: int = Query(default=30, ge=1, le=3650)) -> dict[str, Any]:
    """An AI-written 'how you've changed' summary — routed through the 'smart' agent run."""
    now = datetime.now(timezone.utc)
    window_cutoff = now - timedelta(days=days)
    in_window = [m for m in MOMENTS if m.created_at >= window_cutoff]

    result = _run_smart_agent('evolution_narrative', moments=[_moment_payload(m) for m in in_window])
    return {'range_days': days, 'narrative': result.get('narrative', '')}


@app.post('/api/v1/model/complete', response_model=ChatCompletionOut)
def model_complete(payload: ChatCompletionIn) -> ChatCompletionOut:
    """Proxies to the Agentic Service — Orchestration never calls a model provider directly."""
    client = AgenticServiceClient()
    try:
        result = client.complete(payload.prompt, payload.system)
    except AgenticServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return ChatCompletionOut(provider=result['provider'], response=result['response'])


@app.get('/api/v1/agents')
def list_agents() -> dict[str, list[str]]:
    """Proxies to the Agentic Service — same boundary rule as /api/v1/model/complete."""
    client = AgenticServiceClient()
    try:
        return client.list_agents()
    except AgenticServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post('/api/v1/agents/runs')
def create_agent_run(payload: CreateAgentRunIn) -> dict[str, Any]:
    client = AgenticServiceClient()
    try:
        return client.create_agent_run(payload.agent, payload.user_id, payload.goal)
    except AgenticServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get('/api/v1/agents/runs/{run_id}')
def get_agent_run(run_id: str) -> dict[str, Any]:
    client = AgenticServiceClient()
    try:
        return client.get_agent_run(run_id)
    except AgenticServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post('/api/v1/agents/runs/{run_id}/approve')
def approve_agent_run_step(run_id: str, payload: ApproveStepIn) -> dict[str, Any]:
    client = AgenticServiceClient()
    try:
        return client.approve_agent_run_step(run_id, payload.step_id)
    except AgenticServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post('/api/v1/agents/runs/{run_id}/cancel')
def cancel_agent_run(run_id: str) -> dict[str, Any]:
    client = AgenticServiceClient()
    try:
        return client.cancel_agent_run(run_id)
    except AgenticServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
