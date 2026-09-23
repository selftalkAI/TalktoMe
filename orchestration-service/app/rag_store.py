from __future__ import annotations

import uuid
from datetime import datetime, timezone

import chromadb

from .clients import AgenticServiceClient, AgenticServiceError
from .paths import RAG_STORAGE_DIR

# Local vector storage for RAG — under Storage/rag_storage/. Embeddings come
# from the Agentic Service's model gateway (Orchestration never calls a model
# provider directly, same boundary as everywhere else in this service); this
# module only owns the vector index itself. Collections are scoped per
# profile via metadata rather than one collection per user, so each stays a
# single, simple local index.
_client = chromadb.PersistentClient(path=str(RAG_STORAGE_DIR))
_collection = _client.get_or_create_collection('moments')

# The ProfileAgent's understanding, one document per conversation turn — unlike
# the `profiles` SQL row (which only ever holds the latest snapshot), this
# builds a searchable history of how someone has said they're feeling over
# time, so a future agent can ask "how has their mood been trending" instead
# of only ever seeing the most recent check-in.
_understanding_collection = _client.get_or_create_collection('profile_understanding')

# Governed memory records (memory_repo.py owns the canonical SQL rows; this is
# only the derivative, rebuildable retrieval index — ADD ADR-005). Only ever
# indexed while a memory is ACTIVE; suppressed/deleted/superseded memories are
# removed from here so they can never resurface in retrieval (ADD §13's
# retrieval gate). Basic similarity-only lookup for now — chunking and a real
# ranking/retrieval mechanism land later.
_memory_collection = _client.get_or_create_collection('memories')

# General RAG knowledge chunks (rag_documents_repo.py owns the canonical SQL
# rows; this is only the derivative, rebuildable index). Explicit cosine space
# per TDD §6.1 — the other collections above default to Chroma's L2 metric,
# left as-is to avoid touching their existing behavior.
_document_chunk_collection = _client.get_or_create_collection(
    'document_chunks', metadata={'hnsw:space': 'cosine'}
)


def index_moment(moment_id: str, content: str, profile_email: str) -> None:
    """Embeds a moment's content and upserts it into the local vector store.

    Best-effort: a missing/unreachable Agentic Service must never block
    saving a moment (the SQL write already happened), so failures here are
    swallowed rather than raised.
    """
    try:
        agentic = AgenticServiceClient()
        vector = agentic.embed(content)['vector']
        _collection.upsert(
            ids=[moment_id],
            embeddings=[vector],
            documents=[content],
            metadatas=[{'profile_email': profile_email}],
        )
    except (AgenticServiceError, KeyError):
        pass


def query_similar_moments(query_text: str, profile_email: str, n_results: int = 5) -> list[str]:
    """Returns this profile's own moment IDs whose content is semantically closest to query_text."""
    try:
        agentic = AgenticServiceClient()
        vector = agentic.embed(query_text)['vector']
    except (AgenticServiceError, KeyError):
        return []

    result = _collection.query(
        query_embeddings=[vector],
        n_results=n_results,
        where={'profile_email': profile_email},
    )
    ids = result.get('ids') or [[]]
    return ids[0]


def index_understanding(profile_email: str, response_text: str, mood_summary: str, context_notes: str) -> None:
    """Embeds one conversation check-in (what they said + what was understood from it)

    and appends it to this profile's understanding history. Best-effort, same as
    index_moment — never blocks the conversation flow if the Agentic Service is down.
    """
    document = f'{response_text}\n\nUnderstood: {mood_summary}. {context_notes}'.strip()
    try:
        agentic = AgenticServiceClient()
        vector = agentic.embed(document)['vector']
        _understanding_collection.upsert(
            ids=[uuid.uuid4().hex],
            embeddings=[vector],
            documents=[document],
            metadatas=[
                {
                    'profile_email': profile_email,
                    'mood_summary': mood_summary,
                    'context_notes': context_notes,
                    'created_at': datetime.now(timezone.utc).isoformat(),
                }
            ],
        )
    except (AgenticServiceError, KeyError):
        pass


def query_similar_understanding(query_text: str, profile_email: str, n_results: int = 5) -> list[dict]:
    """Returns this profile's own past check-ins whose content is semantically closest

    to query_text — each as {document, mood_summary, context_notes, created_at}.
    """
    try:
        agentic = AgenticServiceClient()
        vector = agentic.embed(query_text)['vector']
    except (AgenticServiceError, KeyError):
        return []

    result = _understanding_collection.query(
        query_embeddings=[vector],
        n_results=n_results,
        where={'profile_email': profile_email},
    )
    documents = (result.get('documents') or [[]])[0]
    metadatas = (result.get('metadatas') or [[]])[0]
    return [
        {
            'document': doc,
            'mood_summary': meta.get('mood_summary', ''),
            'context_notes': meta.get('context_notes', ''),
            'created_at': meta.get('created_at', ''),
        }
        for doc, meta in zip(documents, metadatas)
    ]


def index_memory(memory_id: str, content: str, profile_email: str, memory_type: str) -> None:
    """Embeds an active memory and upserts it — call this only when a memory's

    status is ACTIVE. Best-effort, same as index_moment: a missing/unreachable
    Agentic Service must never block a memory write.
    """
    try:
        agentic = AgenticServiceClient()
        vector = agentic.embed(content)['vector']
        _memory_collection.upsert(
            ids=[memory_id],
            embeddings=[vector],
            documents=[content],
            metadatas=[{'profile_email': profile_email, 'type': memory_type}],
        )
    except (AgenticServiceError, KeyError):
        pass


def delete_memory_embedding(memory_id: str) -> None:
    """Removes a memory from the retrieval index — call on suppress/delete/correct

    so a no-longer-active memory can never resurface in similarity search.
    """
    try:
        _memory_collection.delete(ids=[memory_id])
    except Exception:
        pass


def query_similar_memories(query_text: str, profile_email: str, n_results: int = 5) -> list[str]:
    """Returns this profile's own memory IDs whose content is closest to query_text.

    Only ACTIVE memories are ever indexed (see index_memory), so ownership and
    status are already filtered before this similarity ranking runs (TDD §6
    step 2's "filter before rank" rule) — no separate status check needed here.
    """
    try:
        agentic = AgenticServiceClient()
        vector = agentic.embed(query_text)['vector']
    except (AgenticServiceError, KeyError):
        return []

    result = _memory_collection.query(
        query_embeddings=[vector],
        n_results=n_results,
        where={'profile_email': profile_email},
    )
    ids = result.get('ids') or [[]]
    return ids[0]


def index_chunk(chunk_id: str, content: str, profile_email: str, document_id: str, chunk_index: int) -> None:
    """Embeds one document chunk and upserts it. Best-effort, same as the other

    index_* functions — a missing/unreachable Agentic Service must never block
    ingestion (the SQL chunk rows already exist).
    """
    try:
        agentic = AgenticServiceClient()
        vector = agentic.embed(content)['vector']
        _document_chunk_collection.upsert(
            ids=[chunk_id],
            embeddings=[vector],
            documents=[content],
            metadatas=[{'profile_email': profile_email, 'document_id': document_id, 'chunk_index': chunk_index}],
        )
    except (AgenticServiceError, KeyError):
        pass


def delete_chunk_embeddings(chunk_ids: list[str]) -> None:
    """Removes chunk vectors — call when their document is deleted."""
    if not chunk_ids:
        return
    try:
        _document_chunk_collection.delete(ids=chunk_ids)
    except Exception:
        pass


def query_similar_chunks(query_text: str, profile_email: str, n_results: int = 5) -> list[dict]:
    """Returns this profile's own chunk IDs (with cosine distance) closest to

    query_text. Ownership is pre-filtered inside the query itself; the caller
    still re-checks each chunk's document status before use, since a document
    can be deleted after its chunks were indexed.
    """
    try:
        agentic = AgenticServiceClient()
        vector = agentic.embed(query_text)['vector']
    except (AgenticServiceError, KeyError):
        return []

    result = _document_chunk_collection.query(
        query_embeddings=[vector],
        n_results=n_results,
        where={'profile_email': profile_email},
        include=['distances'],
    )
    ids = (result.get('ids') or [[]])[0]
    distances = (result.get('distances') or [[]])[0]
    return [{'chunk_id': chunk_id, 'distance': distance} for chunk_id, distance in zip(ids, distances)]
