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
    password_hash TEXT,
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
--
-- `domain` is the shared join key to Brain 2's Profile Store (`profile_entries.
-- domain`, ADD §6.1): an open string (skill/emotion/learning/reading/goal/...),
-- independent of `type`, since the two are different taxonomies — `type` is
-- what kind of statement this is, `domain` is which life area it belongs to.
-- NULL means "not yet associated with a Profile domain," a valid state for
-- ordinary facts/preferences that never feed a Profile refinement.
CREATE TABLE IF NOT EXISTS memories (
    memory_id TEXT PRIMARY KEY,
    profile_email TEXT NOT NULL,
    type TEXT NOT NULL CHECK (type IN (
        'fact', 'preference', 'goal', 'relationship', 'event',
        'routine', 'constraint', 'project_context', 'user_instruction', 'learned_strategy'
    )),
    domain TEXT,
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
-- idx_memories_profile_domain_status is created in init_db(), after the
-- `domain` migration below — creating it here would fail on a pre-existing
-- DB where this CREATE TABLE is a no-op and `domain` doesn't exist yet.

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
-- `memories`.
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
-- a deterministic write.
CREATE TABLE IF NOT EXISTS brain2_checkins (
    intention_id TEXT NOT NULL,
    profile_email TEXT NOT NULL,
    checkin_date TEXT NOT NULL,
    actual_minutes INTEGER NOT NULL,
    note TEXT,
    created_at TEXT NOT NULL,
    PRIMARY KEY (intention_id, checkin_date)
);

-- Brain 1 (Building_Brain1.md §11, TDD §21 V03).
-- One row per version of the compiled 12-section profile — the history of
-- how Brain 1 came to know this person.
CREATE TABLE IF NOT EXISTS brain1_profile_versions (
    version_id TEXT PRIMARY KEY,
    profile_email TEXT NOT NULL,
    version INTEGER NOT NULL,
    profile_json TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    reason TEXT,
    created_at TEXT NOT NULL,
    UNIQUE (profile_email, version)
);
-- How the person responded to each reply — the raw signal Brain 1 learns from.
CREATE TABLE IF NOT EXISTS brain1_outcomes (
    outcome_id TEXT PRIMARY KEY,
    profile_email TEXT NOT NULL,
    run_id TEXT,
    card_ids TEXT NOT NULL DEFAULT '[]',
    voice TEXT,
    expertise TEXT,
    stance TEXT,
    outcome TEXT NOT NULL CHECK (outcome IN
        ('change_talk', 'took_action', 'accepted', 'sustain', 'discord', 'silence')),
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_brain1_outcomes_profile ON brain1_outcomes(profile_email, created_at);
-- What Brain 1 still wants to learn, for Brain 2 to ask at the right moment.
CREATE TABLE IF NOT EXISTS brain1_open_questions (
    question_id TEXT PRIMARY KEY,
    profile_email TEXT NOT NULL,
    core TEXT NOT NULL,
    sub_agent TEXT,
    question TEXT NOT NULL,
    priority INTEGER NOT NULL DEFAULT 50,
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'asked', 'answered', 'dropped')),
    created_at TEXT NOT NULL,
    UNIQUE (profile_email, core, question)
);
-- Trace of one turn: safety, cores, Context Pack sections, persona, plan,
-- checks — so anyone can see why Brain 2 said what it said.
CREATE TABLE IF NOT EXISTS brain1_runs (
    run_id TEXT PRIMARY KEY,
    profile_email TEXT NOT NULL,
    trigger TEXT NOT NULL CHECK (trigger IN ('message', 'silence', 'schedule', 'event')),
    safety_level TEXT NOT NULL CHECK (safety_level IN ('ok', 'concern', 'crisis')),
    trace_json TEXT NOT NULL,
    latency_ms INTEGER,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_brain1_runs_profile ON brain1_runs(profile_email, created_at);
-- What each core agent currently understands about its area of the person's life
-- (Building_Brain1.md §7): the latest one per core feeds the Context Pack.
CREATE TABLE IF NOT EXISTS brain1_area_summaries (
    summary_id TEXT PRIMARY KEY,
    profile_email TEXT NOT NULL,
    core TEXT NOT NULL,
    summary TEXT NOT NULL,
    confidence REAL NOT NULL DEFAULT 0.5,
    steps_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_brain1_area_summaries ON brain1_area_summaries(profile_email, core, created_at);
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
        for column in ('narrative_focus', 'mood_summary', 'context_notes', 'password_hash'):
            if column not in profile_cols:
                conn.execute(f'ALTER TABLE profiles ADD COLUMN {column} TEXT')

        memory_cols = {row['name'] for row in conn.execute('PRAGMA table_info(memories)').fetchall()}
        if 'domain' not in memory_cols:
            conn.execute('ALTER TABLE memories ADD COLUMN domain TEXT')
        conn.execute(
            'CREATE INDEX IF NOT EXISTS idx_memories_profile_domain_status ON memories(profile_email, domain, status)'
        )
        _migrate_memory_types(conn)


def _migrate_memory_types(conn: sqlite3.Connection) -> None:
    """Adds 'learned_strategy' to memories.type (V03). SQLite can't alter a
    CHECK constraint, so the table is rebuilt in one transaction with every
    row and index carried over; it is a no-op once done."""
    table_sql = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='memories'").fetchone()['sql']
    if 'learned_strategy' in table_sql:
        return
    columns = [row['name'] for row in conn.execute('PRAGMA table_info(memories)').fetchall()]
    column_list = ', '.join(columns)
    new_sql = table_sql.replace("'user_instruction'", "'user_instruction', 'learned_strategy'", 1).replace(
        'CREATE TABLE memories', 'CREATE TABLE memories_v03', 1
    )
    conn.execute('BEGIN')
    conn.execute(new_sql)
    conn.execute(f'INSERT INTO memories_v03 ({column_list}) SELECT {column_list} FROM memories')
    conn.execute('DROP TABLE memories')
    conn.execute('ALTER TABLE memories_v03 RENAME TO memories')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_memories_profile_status ON memories(profile_email, status)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_memories_profile_domain_status ON memories(profile_email, domain, status)')
    conn.execute('COMMIT')


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    conn = _connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
