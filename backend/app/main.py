from __future__ import annotations

from datetime import datetime, timedelta, timezone
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
    mood_emoji: str = Field(default='', description='Optional emoji representing the mood at capture time')
    mood_label: str = Field(default='', description='Optional short mood label, e.g. Good, Frustrated')


class CaptureOut(BaseModel):
    id: str
    created_at: datetime
    source: str
    content: str
    tags: list[str]
    mood_emoji: str = ''
    mood_label: str = ''
    reflection: str | None = None


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


def _seed_time(hours_ago: float) -> datetime:
    return datetime.now(timezone.utc) - timedelta(hours=hours_ago)


CAPTURES: list[CaptureOut] = [
    CaptureOut(
        id='cap_seed_frustrated',
        created_at=_seed_time(1.2),
        source='text',
        content='I got frustrated at work today because my proposal got rejected again.',
        tags=['work'],
        mood_emoji='\U0001F624',
        mood_label='Frustrated',
        reflection=None,
    ),
    CaptureOut(
        id='cap_seed_good',
        created_at=_seed_time(1.0),
        source='text',
        content='Testing the new mobile UI shell.',
        tags=['product'],
        mood_emoji='\U0001F60A',
        mood_label='Good',
        reflection=(
            "This moment seems to be about a sense of satisfaction and progress, as you're "
            "testing the new mobile UI shell. You're in a good mood, which is a departure from "
            "the frustration you felt just a few years ago when your proposal got rejected at "
            "work. This moment feels quite different from the one in 2026, where you were "
            "feeling frustrated and rejected. It's almost as if you've turned a corner, and this "
            "new mobile UI shell is a source of excitement and optimism for you. The tone of "
            "this moment is light and positive, which is a stark contrast to the one in 2026. "
            "One thing that stands out to me is that you're now in a place where you can focus "
            "on creating and testing new ideas, rather than dealing with rejection. How do you "
            "think this shift in focus has impacted your overall approach to problem-solving "
            "and creativity?"
        ),
    ),
]


def _generate_reflection(mood_label: str, content: str) -> str:
    previous = CAPTURES[-1] if CAPTURES else None
    if previous is None:
        return (
            f"This is your first entry. You're noting a {mood_label.lower() or 'notable'} moment: "
            f"“{content.strip()}”. Future reflections will start drawing connections to entries like this one."
        )

    if previous.mood_label and mood_label and previous.mood_label.lower() != mood_label.lower():
        return (
            f"This feels like a shift from your last entry, where you were feeling "
            f"{previous.mood_label.lower()}. Now you're noting a {mood_label.lower()} moment: "
            f"“{content.strip()}”. Worth noticing how quickly the tone of your day can change."
        )

    return (
        f"This continues a {mood_label.lower() or 'similar'} thread from your last entry. "
        f"You're noting: “{content.strip()}”."
    )


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


@app.get('/api/v1/entries')
def list_entries() -> list[dict[str, Any]]:
    """Journal-style entries for the Today feed, newest first."""
    ordered = sorted(CAPTURES, key=lambda capture: capture.created_at, reverse=True)
    return [
        {
            'id': capture.id,
            'mood_emoji': capture.mood_emoji,
            'mood_label': capture.mood_label,
            'content': capture.content,
            'created_at': capture.created_at.isoformat(),
            'reflection': capture.reflection,
        }
        for capture in ordered
    ]


@app.post('/api/v1/captures', response_model=CaptureOut)
def create_capture(payload: CaptureIn) -> CaptureOut:
    reflection = _generate_reflection(payload.mood_label, payload.content) if payload.mood_label else None
    capture = CaptureOut(
        id=f'cap_{len(CAPTURES) + 1:03d}',
        created_at=datetime.now(timezone.utc),
        source=payload.source,
        content=payload.content,
        tags=payload.tags,
        mood_emoji=payload.mood_emoji,
        mood_label=payload.mood_label,
        reflection=reflection,
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
