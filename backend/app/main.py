from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI(
    title='selfie.Me API',
    version='0.1.0',
    description='Privacy-first personal memory AI MVP backend.',
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=['http://localhost:3000'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


class CaptureIn(BaseModel):
    source: str = Field(..., description='Source type: voice, text, photo, or journal entry')
    content: str = Field(..., min_length=1, description='Raw user input or transcription text')
    tags: list[str] = Field(default_factory=list)


class CaptureOut(BaseModel):
    id: str
    created_at: datetime
    source: str
    content: str
    tags: list[str]


SEED_MEMORIES: list[dict[str, Any]] = [
    {
        'id': 'mem_001',
        'title': 'Decision to build a privacy-first AI memory system',
        'type': 'decision',
        'summary': 'A decision was made to build a personal memory AI grounded in evidence, not stolen identity or generic advice.',
        'created_at': '2026-09-16T00:00:00Z',
    },
    {
        'id': 'mem_002',
        'title': 'Core product principles',
        'type': 'belief',
        'summary': 'User control, evidence provenance, and privacy-by-design are non-negotiable product principles.',
        'created_at': '2026-09-16T00:00:00Z',
    },
    {
        'id': 'mem_003',
        'title': 'Founder pilot objective',
        'type': 'goal',
        'summary': 'The first product should help a user revisit how their beliefs and decisions have changed over time.',
        'created_at': '2026-09-15T12:00:00Z',
    },
]

SEED_BELIEFS: list[dict[str, Any]] = [
    {
        'topic': 'privacy-first AI',
        'status': 'stable',
        'confidence': 0.92,
        'summary': 'The system must preserve identity and memory under explicit user control.',
    },
    {
        'topic': 'evolution tracking',
        'status': 'emerging',
        'confidence': 0.87,
        'summary': 'User beliefs should be versioned and compared over time with evidence.',
    },
    {
        'topic': 'grounded reflection',
        'status': 'active',
        'confidence': 0.84,
        'summary': 'Important insights should cite the user’s prior memories and decisions.',
    },
]

CAPTURES: list[CaptureOut] = []


@app.get('/health')
def health() -> dict[str, str]:
    return {'status': 'ok', 'service': 'selfie.Me API'}


@app.get('/api/v1/summary')
def summary() -> dict[str, Any]:
    memories = list_memories()
    return {
        'product': 'selfie.Me',
        'phase': 'founder pilot',
        'focus': ['capture', 'memory search', 'belief evolution', 'grounded reflection'],
        'memory_count': len(memories),
        'belief_count': len(SEED_BELIEFS),
    }


@app.get('/api/v1/memories')
def list_memories(q: str | None = Query(default=None)) -> list[dict[str, Any]]:
    all_memories = SEED_MEMORIES + [
        {
            'id': capture.id,
            'title': f'{capture.source.title()} capture',
            'type': 'observation',
            'summary': capture.content,
            'created_at': capture.created_at.isoformat(),
            'tags': capture.tags,
        }
        for capture in CAPTURES
    ]

    if not q:
        return all_memories

    needle = q.lower()
    return [memory for memory in all_memories if needle in str(memory.get('summary', '')).lower() or needle in str(memory.get('title', '')).lower()]


@app.post('/api/v1/captures', response_model=CaptureOut)
def create_capture(payload: CaptureIn) -> CaptureOut:
    capture = CaptureOut(
        id=f'cap_{len(CAPTURES) + 1:03d}',
        created_at=datetime.now(timezone.utc),
        source=payload.source,
        content=payload.content,
        tags=payload.tags,
    )
    CAPTURES.append(capture)
    return capture


@app.get('/api/v1/beliefs')
def list_beliefs() -> list[dict[str, Any]]:
    return SEED_BELIEFS


@app.get('/api/v1/reflections')
def reflections(topic: str | None = Query(default='privacy and identity')) -> dict[str, Any]:
    return {
        'topic': topic,
        'insight': 'The strongest pattern so far is that users want personal AI grounded in their own history, not generic advice. The product should emphasize evidence, transparency, and correction loops.',
        'evidence': [
            'User control over memory and future permissions is a core product principle.',
            'Belief evolution should be tracked as versioned state, not overwritten history.',
            'RAG-style grounding must cite the original capture and related memories.',
        ],
        'confidence': 0.9,
    }
