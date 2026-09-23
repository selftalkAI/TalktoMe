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
