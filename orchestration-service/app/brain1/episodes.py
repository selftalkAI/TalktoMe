from __future__ import annotations

import json
import logging
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from .. import conversations_repo, memory_repo
from ..db import get_connection
from ..spinal_cord import AgenticServiceClient, AgenticServiceError

logger = logging.getLogger(__name__)

# Episodic memory (Building_Brain1.md §8.3): when a conversation session ends
# (a gap longer than conversations_repo.SESSION_GAP_MINUTES, or the nightly
# reflection), Hippocampus summarises it — what happened, their own words,
# what they committed to, what is left open — into one `event` memory. Brain
# 1's Story section and the Context Pack read those, so Brain 2 can say
# "last week you said…" without re-reading every transcript.

EPISODE_SOURCE = 'episode'
MIN_TURNS = 2


def consolidate(profile_email: str, domain: str, *, include_current: bool = False) -> dict[str, Any] | None:
    """Summarises this area's unsummarised turns into one episodic memory.
    Unless `include_current`, the ongoing session is left alone."""
    turns = conversations_repo.unsummarised(profile_email, domain)
    if not include_current:
        ongoing = {t['turn_id'] for t in conversations_repo.current_session(profile_email, domain)}
        last = turns[-1] if turns else None
        if last and conversations_repo.minutes_since(last['created_at']) <= conversations_repo.SESSION_GAP_MINUTES:
            turns = [t for t in turns if t['turn_id'] not in ongoing]
    if len(turns) < MIN_TURNS:
        return None

    summary = _summarise(profile_email, turns)
    if not summary or not summary.get('summary'):
        return None
    content = summary['summary']
    if summary.get('quotes'):
        content += ' In their words: ' + '; '.join(f'"{q}"' for q in summary['quotes']) + '.'
    if summary.get('commitments'):
        content += ' They said they would: ' + '; '.join(summary['commitments']) + '.'
    if summary.get('open_thread'):
        content += f" Open thread: {summary['open_thread']}"

    memory = memory_repo.create_memory(
        profile_email=profile_email, memory_type='event', domain=domain, content=f"{turns[0]['created_at'][:10]}: {content}",
        explicitness='inferred', confidence=0.8, sensitivity_tier='T2', status=memory_repo.ACTIVE,
        rationale_code='EPISODE_SUMMARY', source_type=EPISODE_SOURCE, source_id=turns[-1]['turn_id'],
    )
    conversations_repo.mark_summarised([t['turn_id'] for t in turns], memory['memory_id'])
    if summary.get('open_thread'):
        _queue_follow_up(profile_email, summary['open_thread'])
    return memory


def consolidate_finished(profile_email: str) -> list[dict[str, Any]]:
    """Every area's finished sessions (used by the nightly reflection)."""
    episodes = []
    for domain in conversations_repo.domains_with_unsummarised(profile_email):
        episode = consolidate(profile_email, domain)
        if episode:
            episodes.append(episode)
    return episodes


def consolidate_in_background(profile_email: str, domain: str) -> None:
    threading.Thread(target=_safe, args=(profile_email, domain), daemon=True).start()


def _summarise(profile_email: str, turns: list[dict[str, Any]]) -> dict[str, Any] | None:
    payload = {'operation': 'summarize_episode', 'turns': conversations_repo.as_messages(turns)}
    try:
        run = AgenticServiceClient().create_agent_run('hippocampus', user_id=profile_email, goal=json.dumps(payload))
    except AgenticServiceError:
        return None
    steps = run.get('steps') or []
    result = steps[0].get('result') if run.get('status') == 'completed' and steps else None
    return result if isinstance(result, dict) else None


def _queue_follow_up(profile_email: str, thread: str) -> None:
    with get_connection() as conn:
        conn.execute(
            'INSERT OR IGNORE INTO brain1_open_questions (question_id, profile_email, core, sub_agent, question, priority, '
            "status, created_at) VALUES (?, ?, 'life_story', 'follow_up', ?, 75, 'open', ?)",
            (str(uuid.uuid4()), profile_email, f'Follow up: {thread.strip()[:180]}', datetime.now(timezone.utc).isoformat()),
        )


def _safe(profile_email: str, domain: str) -> None:
    try:
        consolidate(profile_email, domain)
    except Exception:  # noqa: BLE001
        logger.exception('Episode consolidation failed for %s/%s', profile_email, domain)
