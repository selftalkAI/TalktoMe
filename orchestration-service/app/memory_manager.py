from __future__ import annotations

import json
from typing import Any

from . import memory_repo, rag_store
from .clients import AgenticServiceClient, AgenticServiceError

# Deterministic write-gate thresholds (TDD §5 step 5 / ADD §13's write gate).
# The model (SmartAgent's extract_memories) only proposes candidates; these
# thresholds decide what actually becomes durable, kept outside the model
# per ADR-007.
MIN_CONFIDENCE_TO_STORE = 0.4
MIN_CONFIDENCE_TO_AUTO_ACTIVATE = 0.6


def remember_from_text(
    profile_email: str,
    source_text: str,
    source_type: str,
    source_id: str,
    full_name: str | None = None,
) -> list[dict[str, Any]]:
    """Extracts candidate memories from a piece of text and applies the write gate.

    Best-effort: failure here must never break the caller's main flow (saving a
    moment, responding in a conversation) — same rule as rag_store's indexing.
    Runs through the same agent-run pipeline (plan -> policy -> execute -> audit)
    as every other agent action, via SmartAgent's 'extract_memories' mode.
    """
    source_text = (source_text or '').strip()
    if not source_text:
        return []

    existing = [m['content'] for m in memory_repo.list_memories(profile_email, status=memory_repo.ACTIVE)]

    try:
        agentic = AgenticServiceClient()
        goal = json.dumps(
            {
                'mode': 'extract_memories',
                'source_text': source_text,
                'existing_active_memories': existing,
                'full_name': full_name or '',
            }
        )
        run = agentic.create_agent_run('smart', user_id=profile_email, goal=goal)
    except AgenticServiceError:
        return []

    if run.get('status') != 'completed':
        return []
    steps = run.get('steps') or []
    result = steps[0].get('result') if steps else None
    candidates = (result or {}).get('candidates') or []
    if not isinstance(candidates, list):
        return []

    stored: list[dict[str, Any]] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        memory = _apply_write_gate(profile_email, candidate, source_type, source_id)
        if memory is not None:
            stored.append(memory)
    return stored


def _apply_write_gate(
    profile_email: str, candidate: dict[str, Any], source_type: str, source_id: str
) -> dict[str, Any] | None:
    """The deterministic STORE / REQUIRE_CONFIRMATION / TRANSIENT_ONLY decision

    (TDD §5 step 5). Nothing here trusts the model's own judgment about whether
    something should be stored — only its proposal of type/content/confidence.
    """
    memory_type = candidate.get('type')
    content = (candidate.get('content') or '').strip()
    if memory_type not in memory_repo.VALID_TYPES or not content:
        return None

    confidence = _clamp_confidence(candidate.get('confidence'))
    if confidence < MIN_CONFIDENCE_TO_STORE:
        return None  # TRANSIENT_ONLY: not durable enough to keep at all

    if memory_repo.find_duplicate(profile_email, memory_type, content) is not None:
        return None  # already remembered, in these exact words

    explicitness = candidate.get('explicitness')
    if explicitness not in ('explicit', 'inferred'):
        explicitness = 'inferred'

    sensitivity_tier = candidate.get('sensitivity_tier')
    if sensitivity_tier not in memory_repo.VALID_SENSITIVITY_TIERS:
        sensitivity_tier = 'T2'

    if sensitivity_tier == 'T3':
        status = memory_repo.REQUIRES_CONFIRMATION  # FR-MEM-011: never auto-store T3
    elif explicitness == 'explicit' and confidence >= MIN_CONFIDENCE_TO_AUTO_ACTIVATE:
        status = memory_repo.ACTIVE
    else:
        status = memory_repo.REQUIRES_CONFIRMATION

    rationale_code = candidate.get('rationale_code')
    if not isinstance(rationale_code, str):
        rationale_code = None

    memory = memory_repo.create_memory(
        profile_email=profile_email,
        memory_type=memory_type,
        content=content,
        explicitness=explicitness,
        confidence=confidence,
        sensitivity_tier=sensitivity_tier,
        status=status,
        rationale_code=rationale_code,
        source_type=source_type,
        source_id=source_id,
    )
    if status == memory_repo.ACTIVE:
        rag_store.index_memory(memory['memory_id'], memory['content'], profile_email, memory_type)
    return memory


def _clamp_confidence(value: Any) -> float:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return 0.5
    return max(0.0, min(1.0, value))


def recall(profile_email: str, query_text: str, top_k: int = 5) -> list[dict[str, Any]]:
    """Retrieves this profile's own active memories most relevant to query_text.

    Basic similarity-only lookup for now, matching rag_store's current
    simplicity — a real hybrid ranker (TDD §6) lands with the RAG work later.
    """
    if not query_text or not query_text.strip():
        return []
    ids = rag_store.query_similar_memories(query_text, profile_email, n_results=top_k)
    memories = []
    for memory_id in ids:
        memory = memory_repo.get_memory(memory_id, profile_email)
        if memory is not None and memory['status'] == memory_repo.ACTIVE:
            memories.append(memory)
    return memories


def confirm(memory_id: str, profile_email: str) -> dict[str, Any]:
    memory = memory_repo.confirm_memory(memory_id, profile_email)
    if memory is None:
        raise KeyError(f'Unknown memory {memory_id}')
    rag_store.index_memory(memory['memory_id'], memory['content'], profile_email, memory['type'])
    return memory


def suppress(memory_id: str, profile_email: str) -> dict[str, Any]:
    memory = memory_repo.suppress_memory(memory_id, profile_email)
    if memory is None:
        raise KeyError(f'Unknown memory {memory_id}')
    rag_store.delete_memory_embedding(memory_id)
    return memory


def forget(memory_id: str, profile_email: str) -> dict[str, Any]:
    memory = memory_repo.delete_memory(memory_id, profile_email)
    if memory is None:
        raise KeyError(f'Unknown memory {memory_id}')
    rag_store.delete_memory_embedding(memory_id)
    return memory


def correct(memory_id: str, profile_email: str, new_content: str) -> dict[str, Any]:
    new_memory = memory_repo.correct_memory(memory_id, profile_email, new_content)
    rag_store.delete_memory_embedding(memory_id)
    rag_store.index_memory(new_memory['memory_id'], new_memory['content'], profile_email, new_memory['type'])
    return new_memory
