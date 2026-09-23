from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any

from . import rag_documents_repo, rag_store
from .chunking import chunk_text

DEFAULT_CHUNK_SIZE = 800
DEFAULT_CHUNK_OVERLAP = 150
# Embedding calls are I/O-bound HTTP requests to the Agentic Service, so a
# thread pool (not a process pool) gives real concurrency here despite the
# GIL. 12 was picked from measuring the local embedding endpoint directly:
# throughput kept scaling cleanly up to 16 concurrent requests.
DEFAULT_INDEXING_WORKERS = 12

# `profile_email` is the ownership/scoping key for every RAG document and
# memory in this codebase (per-user data). A shared knowledge base (e.g. the
# emotional agent's reference library, US-003) isn't owned by any one user,
# but reuses the same column as a reserved scope key rather than adding a
# separate nullable "global" path through the schema and every query. Any
# code retrieving for a specific user's conversation should additionally
# query this scope and merge results — that wiring is a separate step from
# ingestion itself.
KNOWLEDGE_BASE_SCOPE = 'knowledge_base'

# Blend weights for ranking retrieved chunks — semantic relevance dominates,
# recency is a light tie-breaker. Chunks don't carry confidence/explicitness
# the way a memory does, so this is a smaller version of TDD §6.1's scoring
# idea, not the full memory-ranking formula.
SEMANTIC_WEIGHT = 0.75
RECENCY_WEIGHT = 0.25
RECENCY_HALF_LIFE_DAYS = 30.0


def ingest_text(
    profile_email: str,
    text: str,
    title: str | None = None,
    source_type: str = 'text',
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
    max_workers: int = DEFAULT_INDEXING_WORKERS,
) -> dict[str, Any]:
    """Chunks and indexes a piece of text as a retrievable knowledge source for

    this profile — the intake point for whatever real documents (books,
    frameworks, notes) get provided later. A file-upload path can call this
    same function once parsing exists (TDD §23); the pipeline stages don't
    change, only how `text` gets extracted.
    """
    text = (text or '').strip()
    if not text:
        raise ValueError('Cannot ingest empty text.')

    hash_value = rag_documents_repo.content_hash(text)
    existing = rag_documents_repo.find_document_by_hash(profile_email, hash_value)
    if existing is not None:
        chunk_count = len(rag_documents_repo.list_chunks(existing['document_id'], profile_email))
        return {'document': existing, 'chunk_count': chunk_count, 'already_ingested': True}

    document = rag_documents_repo.create_document(profile_email, title, source_type, hash_value)
    chunks = chunk_text(text, chunk_size=chunk_size, overlap=overlap)
    chunk_rows = rag_documents_repo.create_chunks(document['document_id'], profile_email, chunks)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(
                rag_store.index_chunk,
                chunk['chunk_id'],
                chunk['content'],
                profile_email,
                document['document_id'],
                chunk['chunk_index'],
            )
            for chunk in chunk_rows
        ]
        for future in futures:
            future.result()  # index_chunk is best-effort internally; this only waits for completion

    return {'document': document, 'chunk_count': len(chunk_rows), 'already_ingested': False}


def retrieve(profile_email: str, query: str, top_k: int = 5) -> list[dict[str, Any]]:
    """Retrieves the most relevant chunks for query_text, ranked by a blend of

    semantic similarity and recency. Over-fetches candidates from the vector
    store, then drops any chunk whose document was deleted after indexing —
    the retrieval gate applies here the same as it does for memories.
    """
    query = (query or '').strip()
    if not query:
        return []

    matches = rag_store.query_similar_chunks(query, profile_email, n_results=max(top_k * 3, top_k))
    if not matches:
        return []

    now = datetime.now(timezone.utc)
    scored: list[dict[str, Any]] = []
    for match in matches:
        chunk = rag_documents_repo.get_chunk(match['chunk_id'], profile_email)
        if chunk is None:
            continue  # stale vector entry for a chunk that no longer exists
        document = rag_documents_repo.get_document(chunk['document_id'], profile_email)
        if document is None or document['status'] != rag_documents_repo.INGESTED:
            continue  # document deleted after this chunk was indexed

        # cosine distance is in [0, 2]; convert to a [0, 1] similarity score.
        semantic_score = 1.0 - (min(max(match['distance'], 0.0), 2.0) / 2.0)
        age_days = max((now - datetime.fromisoformat(chunk['created_at'])).total_seconds() / 86400, 0.0)
        recency_score = 1.0 / (1.0 + age_days / RECENCY_HALF_LIFE_DAYS)
        score = SEMANTIC_WEIGHT * semantic_score + RECENCY_WEIGHT * recency_score

        scored.append(
            {
                'chunk_id': chunk['chunk_id'],
                'document_id': chunk['document_id'],
                'document_title': document.get('title'),
                'chunk_index': chunk['chunk_index'],
                'content': chunk['content'],
                'score': round(score, 4),
            }
        )

    scored.sort(key=lambda c: c['score'], reverse=True)
    return scored[:top_k]


def list_documents(profile_email: str) -> list[dict[str, Any]]:
    return rag_documents_repo.list_documents(profile_email)


def delete_document(document_id: str, profile_email: str) -> dict[str, Any]:
    document = rag_documents_repo.get_document(document_id, profile_email)
    if document is None:
        raise KeyError(f'Unknown document {document_id}')
    chunk_ids = rag_documents_repo.delete_chunks(document_id, profile_email)
    rag_store.delete_chunk_embeddings(chunk_ids)
    marked = rag_documents_repo.mark_document_deleted(document_id, profile_email)
    assert marked is not None
    return marked
