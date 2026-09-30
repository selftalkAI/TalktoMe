from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Iterator

from .paths import SQL_STORAGE_DIR

# Local, file-based SQL storage (SQLite) — the "local host SQL database"
# under Storage/sql_storage/. No server process to run; this is a single
# file on disk, which is the durable copy of Moments (ADD §11 durability
# note) for local/dev use ahead of the Postgres migration in the ADD/TDD.
DB_PATH = SQL_STORAGE_DIR / 'selfie_me.db'

_SCHEMA = """
CREATE TABLE IF NOT EXISTS moments (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    source TEXT NOT NULL,
    content TEXT NOT NULL,
    mood TEXT,
    photo_data_url TEXT,
    reflection TEXT,
    profile_email TEXT
);

CREATE TABLE IF NOT EXISTS profiles (
    email TEXT PRIMARY KEY,
    full_name TEXT NOT NULL,
    dob TEXT,
    location TEXT,
    interests TEXT,
    other_interests TEXT,
    photo_data_url TEXT,
    quote TEXT,
    narrative_focus TEXT,
    mood_summary TEXT,
    context_notes TEXT,
    created_at TEXT NOT NULL
);

-- Durable, governed personal memory (ADD §6's "Memory" layer) — distinct from
-- `moments` (raw evidence) and the `profiles` snapshot fields (latest-only,
-- no history). A row here is typed, carries provenance, and is corrected by
-- superseding (supersedes_id) rather than overwritten in place, so history is
-- never destroyed (TDD §5.3).
CREATE TABLE IF NOT EXISTS memories (
    memory_id TEXT PRIMARY KEY,
    profile_email TEXT NOT NULL,
    type TEXT NOT NULL CHECK (type IN (
        'fact', 'preference', 'goal', 'relationship', 'event',
        'routine', 'constraint', 'project_context', 'user_instruction'
    )),
    content TEXT NOT NULL,
    explicitness TEXT NOT NULL CHECK (explicitness IN ('explicit', 'inferred')),
    confidence REAL NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    sensitivity_tier TEXT NOT NULL CHECK (sensitivity_tier IN ('T0', 'T1', 'T2', 'T3')),
    status TEXT NOT NULL CHECK (status IN (
        'candidate', 'active', 'requires_confirmation', 'suppressed', 'superseded', 'deleted'
    )),
    rationale_code TEXT,
    source_type TEXT,
    source_id TEXT,
    supersedes_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_memories_profile_status ON memories(profile_email, status);

-- General RAG knowledge sources (ADD "Files and ingestion" domain) — distinct
-- from `memories` (governed facts about the person) and `moments` (their own
-- captured entries). A document is chunked on ingest; chunks are derivative
-- (rebuildable from the document) and carry the owner scope forward.
CREATE TABLE IF NOT EXISTS rag_documents (
    document_id TEXT PRIMARY KEY,
    profile_email TEXT NOT NULL,
    title TEXT,
    source_type TEXT NOT NULL DEFAULT 'text',
    status TEXT NOT NULL DEFAULT 'ingested' CHECK (status IN ('ingested', 'deleted')),
    content_hash TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_rag_documents_profile_status ON rag_documents(profile_email, status);

CREATE TABLE IF NOT EXISTS rag_chunks (
    chunk_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    profile_email TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_rag_chunks_document ON rag_chunks(document_id);

-- Trackable goals (US-004) — distinct from a free-text `memories` row of
-- type='goal': this carries the progress-tracking fields (streak, nudge
-- state) a durable memory record has no place for. A correction supersedes
-- rather than mutates in place, same pattern as `memories.supersedes_id`.
CREATE TABLE IF NOT EXISTS goals (
    goal_id TEXT PRIMARY KEY,
    profile_email TEXT NOT NULL,
    title TEXT NOT NULL,
    target_minutes INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'superseded', 'deleted')),
    state TEXT NOT NULL DEFAULT 'on_track' CHECK (state IN ('on_track', 'renegotiation_offered', 'adjusted')),
    current_streak_under_target INTEGER NOT NULL DEFAULT 0,
    last_evaluated_date TEXT,
    last_nudged_date TEXT,
    pending_nudge_message TEXT,
    pending_nudge_suggested_target INTEGER,
    supersedes_goal_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_goals_profile_status ON goals(profile_email, status);

-- Ground-truth adherence log for a goal — the LLM's grounding data (US-004);
-- never inferred from conversation, always a deterministic write.
CREATE TABLE IF NOT EXISTS goal_logs (
    goal_id TEXT NOT NULL,
    profile_email TEXT NOT NULL,
    log_date TEXT NOT NULL,
    actual_minutes INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (goal_id, log_date)
);

-- Brain 2's Profile Store (ADD §6.1 / TDD §21): a versioned, per-domain
-- synthesis of who Brain 1 (the user) is in that domain — a skill, an
-- emotion, a relationship, a habit, any part of the complete human persona.
-- An entry is never overwritten; an accepted refinement supersedes the prior
-- accepted entry for that domain (ADR-014), which stays in history.
CREATE TABLE IF NOT EXISTS profile_entries (
    profile_entry_id TEXT PRIMARY KEY,
    profile_email TEXT NOT NULL,
    domain TEXT NOT NULL,
    version INTEGER NOT NULL,
    content TEXT NOT NULL,
    source_memory_ids TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('proposed', 'accepted', 'superseded', 'rejected')),
    proposed_at TEXT NOT NULL,
    accepted_at TEXT,
    superseded_by TEXT
);
CREATE INDEX IF NOT EXISTS idx_profile_entries_email_domain_status
    ON profile_entries(profile_email, domain, status);

-- Brain 1's explicit, self-stated intention in a domain (e.g. "gym, 60
-- min/day"). Explicit and self-authored, so it needs no reflection-check
-- before being trackable — the reflection gate applies to relayed content
-- (an article, a habit merely described), not to a person's own stated goal.
-- Adjusting the target supersedes rather than mutates, same pattern as
-- `goals`/`memories`.
CREATE TABLE IF NOT EXISTS brain2_intentions (
    intention_id TEXT PRIMARY KEY,
    profile_email TEXT NOT NULL,
    domain TEXT NOT NULL,
    title TEXT NOT NULL,
    target_minutes INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'superseded')),
    supersedes_intention_id TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_brain2_intentions_email_domain_status
    ON brain2_intentions(profile_email, domain, status);

-- Ground-truth daily check-ins against an intention — never inferred, always
-- a deterministic write, same spirit as `goal_logs`.
CREATE TABLE IF NOT EXISTS brain2_checkins (
    intention_id TEXT NOT NULL,
    profile_email TEXT NOT NULL,
    checkin_date TEXT NOT NULL,
    actual_minutes INTEGER NOT NULL,
    note TEXT,
    created_at TEXT NOT NULL,
    PRIMARY KEY (intention_id, checkin_date)
);
"""


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        # Migration for DBs created before moments were scoped per profile —
        # must run before the index below, which needs the column to exist.
        cols = {row['name'] for row in conn.execute('PRAGMA table_info(moments)').fetchall()}
        if 'profile_email' not in cols:
            conn.execute('ALTER TABLE moments ADD COLUMN profile_email TEXT')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_moments_profile_email ON moments(profile_email)')

        profile_cols = {row['name'] for row in conn.execute('PRAGMA table_info(profiles)').fetchall()}
        for column in ('narrative_focus', 'mood_summary', 'context_notes'):
            if column not in profile_cols:
                conn.execute(f'ALTER TABLE profiles ADD COLUMN {column} TEXT')


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    conn = _connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
