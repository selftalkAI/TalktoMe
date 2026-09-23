from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any

from .db import get_connection, init_db

init_db()

INGESTED = 'ingested'
DELETED = 'deleted'


def _new_id(prefix: str) -> str:
    return f'{prefix}_{uuid.uuid4().hex[:12]}'


def content_hash(text: str) -> str:
    return hashlib.sha256(text.strip().encode('utf-8')).hexdigest()


def find_document_by_hash(profile_email: str, hash_value: str) -> dict[str, Any] | None:
    """Prevents re-ingesting the exact same source text as a second document."""
    with get_connection() as conn:
        row = conn.execute(
            'SELECT * FROM rag_documents WHERE profile_email = ? AND content_hash = ? AND status = ?',
            (profile_email, hash_value, INGESTED),
        ).fetchone()
    return dict(row) if row else None


def create_document(profile_email: str, title: str | None, source_type: str, hash_value: str) -> dict[str, Any]:
    document_id = _new_id('doc')
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            'INSERT INTO rag_documents (document_id, profile_email, title, source_type, status, '
            'content_hash, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)',
            (document_id, profile_email, title, source_type, INGESTED, hash_value, now),
        )
    document = get_document(document_id, profile_email)
    assert document is not None  # just inserted it
    return document


def get_document(document_id: str, profile_email: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            'SELECT * FROM rag_documents WHERE document_id = ? AND profile_email = ?',
            (document_id, profile_email),
        ).fetchone()
    return dict(row) if row else None


def list_documents(profile_email: str, status: str | None = INGESTED) -> list[dict[str, Any]]:
    query = 'SELECT * FROM rag_documents WHERE profile_email = ?'
    params: list[Any] = [profile_email]
    if status is not None:
        query += ' AND status = ?'
        params.append(status)
    query += ' ORDER BY created_at DESC'
    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def create_chunks(document_id: str, profile_email: str, chunks: list[str]) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc).isoformat()
    rows: list[dict[str, Any]] = []
    with get_connection() as conn:
        for index, content in enumerate(chunks):
            chunk_id = _new_id('chk')
            conn.execute(
                'INSERT INTO rag_chunks (chunk_id, document_id, profile_email, chunk_index, content, '
                'created_at) VALUES (?, ?, ?, ?, ?, ?)',
                (chunk_id, document_id, profile_email, index, content, now),
            )
            rows.append(
                {
                    'chunk_id': chunk_id,
                    'document_id': document_id,
                    'profile_email': profile_email,
                    'chunk_index': index,
                    'content': content,
                    'created_at': now,
                }
            )
    return rows


def get_chunk(chunk_id: str, profile_email: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            'SELECT * FROM rag_chunks WHERE chunk_id = ? AND profile_email = ?',
            (chunk_id, profile_email),
        ).fetchone()
    return dict(row) if row else None


def list_chunks(document_id: str, profile_email: str) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            'SELECT * FROM rag_chunks WHERE document_id = ? AND profile_email = ? ORDER BY chunk_index',
            (document_id, profile_email),
        ).fetchall()
    return [dict(row) for row in rows]


def mark_document_deleted(document_id: str, profile_email: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        conn.execute(
            'UPDATE rag_documents SET status = ? WHERE document_id = ? AND profile_email = ?',
            (DELETED, document_id, profile_email),
        )
    return get_document(document_id, profile_email)


def delete_chunks(document_id: str, profile_email: str) -> list[str]:
    """Hard-deletes chunk rows (they're derivative of the document) and returns

    the deleted chunk_ids so the caller can also remove their vector entries.
    """
    chunk_ids = [c['chunk_id'] for c in list_chunks(document_id, profile_email)]
    with get_connection() as conn:
        conn.execute(
            'DELETE FROM rag_chunks WHERE document_id = ? AND profile_email = ?',
            (document_id, profile_email),
        )
    return chunk_ids
