from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncIterator

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import brain1, memory_manager, memory_repo, moments_repo, profiles_repo, rag_manager, rag_store
from .brain2 import intentions_repo as brain2_intentions_repo
from .brain2 import orchestrator as brain2
from .brain2 import profile_store as brain2_profile_store
from .brain2 import scheduler as brain2_scheduler
from .spinal_cord import AgenticServiceClient, AgenticServiceError
from .config import settings

logger = logging.getLogger(__name__)

# Brain 2's Scheduler (ADD §8.2 step 1) as a single in-process background
# job — appropriate for the MVP modular-monolith shape (ADD §5.1). Running
# more than one worker process would run this cycle redundantly per worker;
# that's a scale-out trigger (ADD §5.2), not a correctness problem, since
# every recheck is idempotent (it only ever drafts a proposal when one isn't
# already pending — see scheduler._has_pending_proposal).
_brain2_background_scheduler = BackgroundScheduler(daemon=True)


@asynccontextmanager
async def _lifespan(_: FastAPI) -> AsyncIterator[None]:
    if settings.brain2_scheduler_enabled:
        _brain2_background_scheduler.add_job(
            brain2_scheduler.run_recheck_cycle,
            'interval',
            hours=settings.brain2_recheck_interval_hours,
            id='brain2_recheck',
            next_run_time=datetime.now(timezone.utc),  # also run one pass immediately on startup
        )
        _brain2_background_scheduler.start()
        logger.info(
            'Brain 2 Scheduler started: rechecking every %s hour(s)', settings.brain2_recheck_interval_hours
        )
    yield
    if _brain2_background_scheduler.running:
        _brain2_background_scheduler.shutdown(wait=False)


app = FastAPI(
    title='selfie.Me Orchestration Service',
    version='0.2.0',
    description=(
        'API layer + data layer for selfie.Me. Owns Moments (this person\'s own captured '
        'thoughts) and reflects them back using only that person\'s own history — never '
        'outside opinions, other people\'s data, or generic advice.'
    ),
    lifespan=_lifespan,
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
    profile_email: str = Field(..., min_length=3, description='Which profile this moment belongs to')
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


class ProfileIn(BaseModel):
    email: str = Field(..., min_length=3, description='Also the login identifier')
    full_name: str = Field(..., min_length=1)
    password: str = Field(..., min_length=6, description='Set once at profile creation; hashed before storage')
    dob: str | None = None
    location: str | None = None
    interests: list[str] = Field(default_factory=list)
    other_interests: str | None = None
    photo_data_url: str | None = Field(default=None, description='Optional small inline image (data URL)')
    quote: str | None = None


class LoginIn(BaseModel):
    password: str = Field(..., min_length=1)


# password / password_hash deliberately never appear on this model — nothing
# that returns a ProfileOut can leak it, even by accident (main.py never
# builds one from a raw profiles_repo row without going through this).
class ProfileOut(BaseModel):
    email: str
    full_name: str
    dob: str | None = None
    location: str | None = None
    interests: list[str] = Field(default_factory=list)
    other_interests: str | None = None
    photo_data_url: str | None = None
    quote: str | None = None
    narrative_focus: str | None = None
    mood_summary: str | None = None
    context_notes: str | None = None
    created_at: datetime


class MemoryOut(BaseModel):
    memory_id: str
    profile_email: str
    type: str
    domain: str | None = None
    content: str
    explicitness: str
    confidence: float
    sensitivity_tier: str
    status: str
    rationale_code: str | None = None
    source_type: str | None = None
    source_id: str | None = None
    supersedes_id: str | None = None
    created_at: datetime
    updated_at: datetime


class MemoryIn(BaseModel):
    profile_email: str = Field(..., min_length=3)
    type: str = Field(..., description='fact | preference | goal | relationship | event | routine | constraint | project_context | user_instruction')
    domain: str | None = Field(default=None, description='Open Profile domain (skill/emotion/learning/reading/...), ADD §6.1 — omit if this memory feeds no Profile domain')
    content: str = Field(..., min_length=1)
    sensitivity_tier: str = Field(default='T2', description='T0-T3, see ADD §7.1')


class MemoryCorrectionIn(BaseModel):
    content: str = Field(..., min_length=1)


class RagIngestIn(BaseModel):
    profile_email: str = Field(..., min_length=3)
    text: str = Field(..., min_length=1, description='Raw text to chunk and index (a book summary, framework notes, etc.)')
    title: str | None = None
    source_type: str = Field(default='text', description="'text' for now; 'file'/'url' once ingestion grows")


class RagDocumentOut(BaseModel):
    document_id: str
    profile_email: str
    title: str | None = None
    source_type: str
    status: str
    content_hash: str | None = None
    created_at: datetime


class RagIngestOut(BaseModel):
    document: RagDocumentOut
    chunk_count: int
    already_ingested: bool


class RagChunkOut(BaseModel):
    chunk_id: str
    document_id: str
    document_title: str | None = None
    chunk_index: int
    content: str
    score: float


class ConversationOpenOut(BaseModel):
    opening_message: str


class ConversationRespondIn(BaseModel):
    response_text: str = Field(..., min_length=1, description="What the person said about how they're doing")


class ConversationRespondOut(BaseModel):
    welcome_message: str
    suggested_first_action: str
    mood_summary: str
    context_notes: str
    narrative_focus: str


@app.get('/health')
def health() -> dict[str, str]:
    return {'status': 'ok', 'service': 'selfie.Me Orchestration Service'}


@app.post('/api/v1/profiles', response_model=ProfileOut)
def save_profile(payload: ProfileIn) -> ProfileOut:
    """Creates Brain 1's record — account creation only, not a general-purpose

    update. Rejects an email that already has a profile (409): with password
    auth in place, re-POSTing to an existing email must never be a way to
    silently overwrite it without knowing the current password — a returning
    person logs in via `POST /api/v1/profiles/{email}/login` instead. Goes
    through `brain1.create`, not `profiles_repo` directly, so that the first
    time this email is ever seen, Brain 2's side of the architecture (the
    Scheduler, ADD §1.1/§8.2) is already live for them, not merely eligible
    for its next cycle.
    """
    if payload.photo_data_url and len(payload.photo_data_url) > MAX_PHOTO_DATA_URL_LENGTH:
        raise HTTPException(status_code=413, detail='Photo is too large for this MVP (limit ~1.5MB).')
    if profiles_repo.get_profile(payload.email) is not None:
        raise HTTPException(status_code=409, detail='An account already exists for this email. Log in instead.')

    row = brain1.create(
        email=payload.email,
        full_name=payload.full_name,
        password=payload.password,
        dob=payload.dob,
        location=payload.location,
        interests=payload.interests,
        other_interests=payload.other_interests,
        photo_data_url=payload.photo_data_url,
        quote=payload.quote,
    )
    return ProfileOut(**row)


@app.get('/api/v1/profiles', response_model=list[ProfileOut])
def list_profiles() -> list[ProfileOut]:
    """Lists every saved profile — used by the login screen's quick-pick list for testing."""
    return [ProfileOut(**row) for row in profiles_repo.list_profiles()]


@app.get('/api/v1/profiles/{email}', response_model=ProfileOut)
def get_profile(email: str) -> ProfileOut:
    """Existence check only — the login flow's first step, to decide whether

    to prompt for a password or drop into onboarding. Never a way to log in
    by itself (it asks nothing and proves nothing about the caller); see
    `login_profile` below for the actual password check.
    """
    row = profiles_repo.get_profile(email)
    if row is None:
        raise HTTPException(status_code=404, detail=f'No profile for {email}')
    return ProfileOut(**row)


@app.post('/api/v1/profiles/{email}/login', response_model=ProfileOut)
def login_profile(email: str, payload: LoginIn) -> ProfileOut:
    """The login flow's actual authentication step — verifies the password

    against the stored bcrypt hash (`brain1.authenticate`) and returns the
    profile only on a match. A wrong password and an unknown email both come
    back as 401 with the same generic detail, deliberately not distinguished,
    so this endpoint can't be used to enumerate which emails have accounts.
    """
    row = brain1.authenticate(email, payload.password)
    if row is None:
        raise HTTPException(status_code=401, detail='Incorrect email or password.')
    return ProfileOut(**row)


@app.get('/api/v1/brain1/{email}/key-areas')
def brain1_key_areas(email: str) -> list[dict[str, Any]]:
    """Brain 1's key areas (ADD §6.1: skill/emotion/learning/reading, plus

    any custom domain this person has actually used) with Brain 2's current,
    honest status for each — an accepted entry if one exists, how many
    active memories feed it, and whether something is waiting for review.
    """
    if profiles_repo.get_profile(email) is None:
        raise HTTPException(status_code=404, detail=f'No profile for {email}')
    return brain1.key_areas_overview(email)


def _profile_facts(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'full_name': row['full_name'],
        'dob': row['dob'],
        'location': row['location'],
        'interests': row['interests'],
        'other_interests': row['other_interests'],
        'quote': row['quote'],
    }


@app.post('/api/v1/profiles/{email}/conversation/open', response_model=ConversationOpenOut)
def open_conversation(email: str) -> ConversationOpenOut:
    """Stage 1: Thalamus opens the conversation — grounded only in the

    profile, inviting them to say how they're doing. It decides nothing and performs
    no action; it's just the door opening. Called once at the start of the app, after
    login or right after profile creation.
    """
    row = profiles_repo.get_profile(email)
    if row is None:
        raise HTTPException(status_code=404, detail=f'No profile for {email}')

    result = _run_agent('thalamus', _profile_facts(row))
    return ConversationOpenOut(opening_message=result.get('opening_message', ''))


@app.post('/api/v1/profiles/{email}/conversation/respond', response_model=ConversationRespondOut)
def respond_to_conversation(email: str, payload: ConversationRespondIn) -> ConversationRespondOut:
    """Stage 2: the person answers, in their own words, how they're doing.

    Sensory Cortex turns that into structured understanding (mood, context,
    narrative focus) — still no advice, no suggestions. That understanding is then
    handed to Prefrontal Cortex, which is the one that actually decides what this
    person needs and produces the welcome + suggested first moment. Understanding is
    also persisted on the profile so it keeps shaping reflections and the evolution
    narrative afterward, not just this one screen.
    """
    row = profiles_repo.get_profile(email)
    if row is None:
        raise HTTPException(status_code=404, detail=f'No profile for {email}')

    understanding = _run_agent(
        'sensory_cortex',
        {'response_text': payload.response_text, **_profile_facts(row)},
    )
    mood_summary = understanding.get('mood_summary', '')
    context_notes = understanding.get('context_notes', '')
    narrative_focus = understanding.get('narrative_focus', '')
    profiles_repo.set_understanding(email, mood_summary, context_notes, narrative_focus)
    rag_store.index_understanding(email, payload.response_text, mood_summary, context_notes)
    memory_manager.remember_from_text(
        profile_email=email,
        source_text=payload.response_text,
        source_type='conversation',
        source_id='onboarding',
        full_name=row['full_name'],
    )

    recent_moments = [_moment_payload(MomentOut(**m)) for m in moments_repo.list_moments(email)[:10]]
    decision = _run_prefrontal_cortex(
        'suggest_next_step',
        full_name=row['full_name'],
        interests=row['interests'],
        mood_summary=mood_summary,
        context_notes=context_notes,
        recent_moments=list(reversed(recent_moments)),  # oldest to newest
    )

    return ConversationRespondOut(
        welcome_message=decision.get('welcome_message', ''),
        suggested_first_action=decision.get('suggested_first_action', ''),
        mood_summary=mood_summary,
        context_notes=context_notes,
        narrative_focus=narrative_focus,
    )


@app.post('/api/v1/moments', response_model=MomentOut)
def create_moment(payload: MomentIn) -> MomentOut:
    if payload.photo_data_url and len(payload.photo_data_url) > MAX_PHOTO_DATA_URL_LENGTH:
        raise HTTPException(status_code=413, detail='Photo is too large for this MVP (limit ~1.5MB).')

    row = moments_repo.create_moment(
        profile_email=payload.profile_email,
        source=payload.source,
        content=payload.content,
        mood=payload.mood,
        photo_data_url=payload.photo_data_url,
    )
    rag_store.index_moment(row['id'], row['content'], payload.profile_email)
    profile = profiles_repo.get_profile(payload.profile_email)

    memory_manager.remember_from_text(
        profile_email=payload.profile_email,
        source_text=row['content'],
        source_type='moment',
        source_id=row['id'],
        full_name=profile['full_name'] if profile else None,
    )

    return MomentOut(**row)


@app.get('/api/v1/moments', response_model=list[MomentOut])
def list_moments(profile_email: str = Query(..., min_length=3)) -> list[MomentOut]:
    return [MomentOut(**row) for row in moments_repo.list_moments(profile_email)]  # already most recent first


def _find_moment(moment_id: str, profile_email: str) -> MomentOut:
    row = moments_repo.get_moment(moment_id, profile_email)
    if row is None:
        raise HTTPException(status_code=404, detail=f'Unknown moment {moment_id}')
    return MomentOut(**row)


def _moment_payload(moment: MomentOut) -> dict[str, Any]:
    return {'content': moment.content, 'mood': moment.mood, 'created_at': moment.created_at.isoformat()}


@app.get('/api/v1/memories', response_model=list[MemoryOut])
def list_memories(
    profile_email: str = Query(..., min_length=3),
    status: str | None = Query(default='active'),
    domain: str | None = Query(default=None),
) -> list[MemoryOut]:
    """Lists this profile's memories. Defaults to active only; pass status=

    (empty) to see every status, or a specific one (requires_confirmation, etc.).
    Pass domain to see only memories tagged to one Profile domain (ADD §6.1)."""
    return [
        MemoryOut(**m)
        for m in memory_repo.list_memories(profile_email, status=status or None, domain=domain)
    ]


@app.post('/api/v1/memories', response_model=MemoryOut)
def create_memory(payload: MemoryIn) -> MemoryOut:
    """An explicit memory, created directly by the user (FR-MEM-004) — active

    immediately unless T3, which still requires confirmation even when the
    user typed it themselves (FR-MEM-011: per-category opt-in is separate from
    general write access)."""
    if payload.type not in memory_repo.VALID_TYPES:
        raise HTTPException(status_code=422, detail=f'Unknown memory type {payload.type!r}')
    if payload.sensitivity_tier not in memory_repo.VALID_SENSITIVITY_TIERS:
        raise HTTPException(status_code=422, detail=f'Unknown sensitivity tier {payload.sensitivity_tier!r}')

    status = memory_repo.REQUIRES_CONFIRMATION if payload.sensitivity_tier == 'T3' else memory_repo.ACTIVE
    memory = memory_repo.create_memory(
        profile_email=payload.profile_email,
        memory_type=payload.type,
        domain=payload.domain,
        content=payload.content,
        explicitness='explicit',
        confidence=1.0,
        sensitivity_tier=payload.sensitivity_tier,
        status=status,
        rationale_code='USER_EXPLICIT',
        source_type='user',
    )
    if status == memory_repo.ACTIVE:
        rag_store.index_memory(memory['memory_id'], memory['content'], payload.profile_email, payload.type)
    return MemoryOut(**memory)


@app.patch('/api/v1/memories/{memory_id}/confirm', response_model=MemoryOut)
def confirm_memory(memory_id: str, profile_email: str = Query(..., min_length=3)) -> MemoryOut:
    """Promotes a requires_confirmation candidate to active."""
    try:
        return MemoryOut(**memory_manager.confirm(memory_id, profile_email))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.patch('/api/v1/memories/{memory_id}/correct', response_model=MemoryOut)
def correct_memory(
    memory_id: str, payload: MemoryCorrectionIn, profile_email: str = Query(..., min_length=3)
) -> MemoryOut:
    """Corrects a memory by superseding it — returns the new, current record."""
    try:
        return MemoryOut(**memory_manager.correct(memory_id, profile_email, payload.content))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.patch('/api/v1/memories/{memory_id}/suppress', response_model=MemoryOut)
def suppress_memory(memory_id: str, profile_email: str = Query(..., min_length=3)) -> MemoryOut:
    """Hides a memory from retrieval without deleting it (reversible)."""
    try:
        return MemoryOut(**memory_manager.suppress(memory_id, profile_email))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.delete('/api/v1/memories/{memory_id}', response_model=MemoryOut)
def delete_memory(memory_id: str, profile_email: str = Query(..., min_length=3)) -> MemoryOut:
    try:
        return MemoryOut(**memory_manager.forget(memory_id, profile_email))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post('/api/v1/rag/documents', response_model=RagIngestOut)
def ingest_rag_document(payload: RagIngestIn) -> RagIngestOut:
    """Chunks and indexes a piece of text as a retrievable knowledge source for

    this profile — the intake point for real documents (e.g. book summaries,
    frameworks) once provided; identical text ingested twice is a no-op."""
    try:
        result = rag_manager.ingest_text(
            profile_email=payload.profile_email,
            text=payload.text,
            title=payload.title,
            source_type=payload.source_type,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return RagIngestOut(
        document=RagDocumentOut(**result['document']),
        chunk_count=result['chunk_count'],
        already_ingested=result['already_ingested'],
    )


@app.get('/api/v1/rag/documents', response_model=list[RagDocumentOut])
def list_rag_documents(profile_email: str = Query(..., min_length=3)) -> list[RagDocumentOut]:
    return [RagDocumentOut(**d) for d in rag_manager.list_documents(profile_email)]


@app.delete('/api/v1/rag/documents/{document_id}', response_model=RagDocumentOut)
def delete_rag_document(document_id: str, profile_email: str = Query(..., min_length=3)) -> RagDocumentOut:
    try:
        return RagDocumentOut(**rag_manager.delete_document(document_id, profile_email))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get('/api/v1/rag/retrieve', response_model=list[RagChunkOut])
def retrieve_rag_chunks(
    profile_email: str = Query(..., min_length=3),
    query: str = Query(..., min_length=1),
    top_k: int = Query(default=5, ge=1, le=20),
) -> list[RagChunkOut]:
    return [RagChunkOut(**c) for c in rag_manager.retrieve(profile_email, query, top_k=top_k)]


def _run_agent(agent_name: str, goal_payload: dict[str, Any]) -> dict[str, Any]:
    """Runs any registered agent through the real pipeline (plan -> policy -> execute -> audit),

    not a raw model call. Orchestration owns the data, the Agentic Layer owns the
    reasoning about it, and the run is planned/authorized/observed like any other agent —
    every cognitive agent (Thalamus, Sensory Cortex, Hippocampus, Prefrontal Cortex,
    Amygdala, Broca's Area, and whatever comes next) goes through this same door.
    """
    client = AgenticServiceClient()
    goal = json.dumps(goal_payload)
    try:
        run = client.create_agent_run(agent_name, user_id='local-user', goal=goal)
    except AgenticServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if run.get('status') != 'completed':
        steps = run.get('steps') or []
        error = steps[0].get('result', {}).get('error') if steps else None
        raise HTTPException(status_code=502, detail=error or f"{agent_name} agent run ended as '{run.get('status')}'.")

    steps = run.get('steps') or []
    result = steps[0].get('result') if steps else None
    if not result:
        raise HTTPException(status_code=502, detail=f'{agent_name} agent run produced no result.')
    return result


def _run_prefrontal_cortex(mode: str, **payload: Any) -> dict[str, Any]:
    """`reflect_moment`/`evolution_narrative`/`suggest_next_step` all live on

    Prefrontal Cortex now (ADD §8's body-region naming) — one agent, three
    routed operations, since all three are the same job (reasoning from past
    to present to decide what's next), not three unrelated capabilities.
    """
    return _run_agent('prefrontal_cortex', {'mode': mode, **payload})


def _all_moments(profile_email: str) -> list[MomentOut]:
    return [MomentOut(**row) for row in moments_repo.list_moments(profile_email)]  # most recent first


def _understanding_for(profile_email: str) -> dict[str, str]:
    """Sensory Cortex's read on this person, if a conversation has ever run for them —

    threaded into every Prefrontal Cortex call below so what they told us about
    themselves, and how they said they were feeling, actually shapes how their
    reflections and evolution narrative get written.
    """
    row = profiles_repo.get_profile(profile_email)
    if not row:
        return {'narrative_focus': '', 'mood_summary': '', 'context_notes': ''}
    return {
        'narrative_focus': row.get('narrative_focus') or '',
        'mood_summary': row.get('mood_summary') or '',
        'context_notes': row.get('context_notes') or '',
    }


@app.post('/api/v1/moments/{moment_id}/reflect', response_model=ReflectionOut)
def reflect_on_moment(moment_id: str, profile_email: str = Query(..., min_length=3)) -> ReflectionOut:
    """Reflects one moment back using ONLY this person's own prior moments as context —

    routed through Prefrontal Cortex's agent run, so it's planned, policy-checked
    (READ_ONLY, auto-approved), and recorded in an audit trail like any other agent action.
    """
    moment = _find_moment(moment_id, profile_email)
    recent_others = [m for m in _all_moments(profile_email) if m.id != moment_id][:30]
    past_moments = list(reversed(recent_others))  # oldest to newest, matching Prefrontal Cortex's prompt contract
    relevant_memories = memory_manager.recall(profile_email, moment.content, top_k=5)
    profile_row = profiles_repo.get_profile(profile_email)

    result = _run_prefrontal_cortex(
        'reflect_moment',
        moment=_moment_payload(moment),
        past_moments=[_moment_payload(m) for m in past_moments],
        relevant_memories=[{'type': m['type'], 'content': m['content']} for m in relevant_memories],
        **_understanding_for(profile_email),
        **(_profile_facts(profile_row) if profile_row else {}),
    )

    moments_repo.set_reflection(moment.id, profile_email, result['reflection'])
    return ReflectionOut(
        moment_id=moment.id,
        reflection=result['reflection'],
        referenced_past_count=result.get('referenced_past_count', 0),
    )


@app.get('/api/v1/evolution')
def evolution(profile_email: str = Query(..., min_length=3), days: int = Query(default=30, ge=1, le=3650)) -> dict[str, Any]:
    """Purely computed from this person's own stored moments — no model call, no outside data."""
    now = datetime.now(timezone.utc)
    window_cutoff = now - timedelta(days=days)
    today = now.date()

    all_moments = _all_moments(profile_email)
    in_window = [m for m in all_moments if m.created_at >= window_cutoff]
    today_moments = [m for m in all_moments if m.created_at.date() == today]
    earlier_than_window = [m for m in all_moments if m.created_at < window_cutoff]

    mood_counts: dict[str, int] = {}
    for m in in_window:
        key = m.mood or 'unspecified'
        mood_counts[key] = mood_counts.get(key, 0) + 1

    return {
        'range_days': days,
        'total_moments_all_time': len(all_moments),
        'moments_in_range': len(in_window),
        'moments_today': len(today_moments),
        'mood_counts_in_range': mood_counts,
        'has_history_before_range': len(earlier_than_window) > 0,
    }


@app.get('/api/v1/evolution/narrative')
def evolution_narrative(
    profile_email: str = Query(..., min_length=3), days: int = Query(default=30, ge=1, le=3650)
) -> dict[str, Any]:
    """An AI-written 'how you've changed' summary — routed through Prefrontal Cortex's agent run."""
    now = datetime.now(timezone.utc)
    window_cutoff = now - timedelta(days=days)
    in_window = [m for m in _all_moments(profile_email) if m.created_at >= window_cutoff]
    oldest_to_newest = list(reversed(in_window))

    result = _run_prefrontal_cortex(
        'evolution_narrative',
        moments=[_moment_payload(m) for m in oldest_to_newest],
        **_understanding_for(profile_email),
    )
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


# --- Brain 2: intention / check-in / Profile endpoints -------------------
# Brain 1 is the user (the `profile_email` on every call below). Brain 2 is
# everything these endpoints front — one orchestrator, propose-never-write,
# nothing durable changes to a Profile except through the accept endpoint.


class Brain2IntentionIn(BaseModel):
    profile_email: str = Field(..., min_length=3)
    domain: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    target_minutes: int = Field(..., ge=0)


class Brain2CheckinIn(BaseModel):
    profile_email: str = Field(..., min_length=3)
    minutes: int = Field(..., ge=0)
    checkin_date: str | None = None
    note: str | None = None


class Brain2SupportIn(BaseModel):
    profile_email: str = Field(..., min_length=3)


class Brain2RefineIn(BaseModel):
    profile_email: str = Field(..., min_length=3)
    support_message: str = Field(default='')
    user_reflection: str = Field(..., min_length=1)


class Brain2ReviseIn(BaseModel):
    profile_email: str = Field(..., min_length=3)
    additional_reflection: str = Field(..., min_length=1)
    support_message: str = Field(default='')


class Brain2ProposalActionIn(BaseModel):
    profile_email: str = Field(..., min_length=3)


class Brain2AdjustIntentionIn(BaseModel):
    profile_email: str = Field(..., min_length=3)
    new_target_minutes: int = Field(..., ge=0)


@app.post('/api/v1/brain2/intentions')
def brain2_set_intention(payload: Brain2IntentionIn) -> dict[str, Any]:
    """Brain 1 states an intention (e.g. 'Gym', 60 min/day) in a life domain."""
    return brain2.set_intention(payload.profile_email, payload.domain, payload.title, payload.target_minutes)


@app.post('/api/v1/brain2/intentions/{intention_id}/checkins')
def brain2_log_checkin(intention_id: str, payload: Brain2CheckinIn) -> dict[str, Any]:
    """Logs one day's ground truth against an intention and returns whether a

    real shortfall pattern now exists — three+ consecutive days under target,
    never a single bad day (`brain2/intentions_repo.SHORTFALL_STREAK_THRESHOLD`).
    """
    try:
        return brain2.log_checkin(payload.profile_email, intention_id, payload.minutes, payload.checkin_date, payload.note)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post('/api/v1/brain2/intentions/{intention_id}/support')
def brain2_offer_support(intention_id: str, payload: Brain2SupportIn) -> dict[str, Any]:
    """Brain 2 notices the pattern already detected by the check-in endpoint

    and drafts something to say — it never decides or acts, only offers.
    """
    intention = brain2_intentions_repo.get_intention(intention_id, payload.profile_email)
    if intention is None:
        raise HTTPException(status_code=404, detail=f'Unknown intention {intention_id}')
    checkins = brain2_intentions_repo.list_checkins(intention_id, payload.profile_email)
    streak = brain2_intentions_repo.shortfall_streak(checkins, intention['target_minutes'])
    support = brain2.offer_support(payload.profile_email, intention, streak, checkins)
    return {**support, 'streak': streak}


@app.post('/api/v1/brain2/intentions/{intention_id}/profile-proposal')
def brain2_propose_from_intention(intention_id: str, payload: Brain2RefineIn) -> dict[str, Any]:
    """Drafts a Profile refinement from this intention's current shortfall and

    what Brain 1 just said back — this writes nothing durable; the returned
    entry has status='proposed' until an explicit accept call.
    """
    intention = brain2_intentions_repo.get_intention(intention_id, payload.profile_email)
    if intention is None:
        raise HTTPException(status_code=404, detail=f'Unknown intention {intention_id}')
    checkins = brain2_intentions_repo.list_checkins(intention_id, payload.profile_email)
    streak = brain2_intentions_repo.shortfall_streak(checkins, intention['target_minutes'])
    return brain2.propose_refinement(
        profile_email=payload.profile_email,
        domain=intention['domain'],
        user_reflection=payload.user_reflection,
        intention=intention,
        streak=streak,
        support_message=payload.support_message,
    )


class Brain2DomainProposalIn(BaseModel):
    profile_email: str = Field(..., min_length=3)
    user_reflection: str = Field(..., min_length=1)


@app.post('/api/v1/brain2/profile/{domain}/proposal')
def brain2_propose_for_domain(domain: str, payload: Brain2DomainProposalIn) -> dict[str, Any]:
    """Generic entry point into the Profile refinement loop (ADD §6.1/§8.2) for

    any domain that isn't goal-adherence tracking — grounded in this domain's
    own active `memories` rather than an intention/checkin streak. This is
    how a skill/emotion/learning/reading Profile entry gets proposed.
    """
    return brain2.propose_refinement(
        profile_email=payload.profile_email,
        domain=domain,
        user_reflection=payload.user_reflection,
    )


@app.get('/api/v1/brain2/pending')
def brain2_list_pending(profile_email: str = Query(..., min_length=3)) -> list[dict[str, Any]]:
    """Everything Brain 2 has drafted and is waiting on Brain 1 to review —

    across every domain, including proposals the Scheduler drafted on its
    own with no new input while Brain 1 was away (ADD §8.2 step 1). This is
    how 'Brain 2 keeps working while you're offline' actually surfaces:
    nothing pings you — you see it here next time you open the app.
    """
    return brain2_profile_store.list_pending(profile_email)


@app.post('/api/v1/brain2/scheduler/run-now')
def brain2_run_scheduler_now() -> dict[str, Any]:
    """Manually triggers one Scheduler recheck cycle immediately, across every

    profile — for testing/demo without waiting for the next interval. The
    real cycle runs automatically on `settings.brain2_recheck_interval_hours`
    for as long as this process is up (see `_lifespan` above).
    """
    drafted = brain2_scheduler.run_recheck_cycle()
    return {'drafted_count': len(drafted), 'drafted': drafted}


@app.get('/api/v1/brain2/profile/{domain}')
def brain2_get_profile(domain: str, profile_email: str = Query(..., min_length=3)) -> dict[str, Any]:
    """Current accepted entry (if any) plus the full version history — nothing

    in the history list is ever deleted, only superseded or rejected in place.
    """
    return {
        'domain': domain,
        'accepted': brain2_profile_store.get_accepted(profile_email, domain),
        'history': brain2_profile_store.history(profile_email, domain),
    }


@app.post('/api/v1/brain2/profile/proposals/{proposal_id}/accept')
def brain2_accept_proposal(proposal_id: str, payload: Brain2ProposalActionIn) -> dict[str, Any]:
    """The only endpoint in this whole module that can make a Profile entry durable."""
    try:
        return brain2.accept_proposal(proposal_id, payload.profile_email)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post('/api/v1/brain2/profile/proposals/{proposal_id}/refine')
def brain2_refine_proposal(proposal_id: str, payload: Brain2ReviseIn) -> dict[str, Any]:
    """Brain 1 wants the draft reworked. Rejects this version (kept in history)

    and drafts a new one incorporating the additional reflection. Works for
    any domain: if this domain has an active intention (goal-adherence), its
    streak/target re-ground the redraft; otherwise the redraft is grounded in
    this domain's own `memories`, same as the generic proposal path.
    """
    entry = brain2_profile_store.get_entry(proposal_id, payload.profile_email)
    if entry is None:
        raise HTTPException(status_code=404, detail=f'Unknown proposal {proposal_id}')

    intention = brain2_intentions_repo.get_active_intention(payload.profile_email, entry['domain'])
    streak = None
    if intention is not None:
        checkins = brain2_intentions_repo.list_checkins(intention['intention_id'], payload.profile_email)
        streak = brain2_intentions_repo.shortfall_streak(checkins, intention['target_minutes'])

    return brain2.refine_proposal(
        proposal_id,
        payload.profile_email,
        payload.additional_reflection,
        intention=intention,
        streak=streak,
        support_message=payload.support_message,
    )


@app.post('/api/v1/brain2/profile/proposals/{proposal_id}/reject')
def brain2_reject_proposal(proposal_id: str, payload: Brain2ProposalActionIn) -> dict[str, Any]:
    try:
        return brain2.reject_proposal(proposal_id, payload.profile_email)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post('/api/v1/brain2/intentions/{intention_id}/adjust')
def brain2_adjust_intention(intention_id: str, payload: Brain2AdjustIntentionIn) -> dict[str, Any]:
    """Brain 1 accepted a smaller target — supersedes the old intention rather

    than mutating it, so the original target stays visible in history.
    """
    try:
        return brain2.adjust_intention(payload.profile_email, intention_id, payload.new_target_minutes)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
