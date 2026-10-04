"""Clears local dev activity history — never accounts, never consents, never
the knowledge base.

Deletes: memories, profile drafts, goals and check-ins, the stored conversation,
and Brain 1's history (profile versions, outcomes, open questions, turn traces,
area summaries) plus their Chroma collections.

Never touches: the `profiles` table (accounts are not "history" — a prior run of
an ad-hoc cleanup accidentally deleted accounts, which this script exists to
prevent), `brain1_consents` (her choices), and the ingested book knowledge base
(`rag_documents` / `rag_chunks` / `document_chunks`).

Usage (from orchestration-service/, with its venv active):
    python3 scripts/reset_dev_data.py
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.paths import RAG_STORAGE_DIR, SQL_STORAGE_DIR  # noqa: E402

HISTORY_TABLES = [
    'memories', 'profile_entries', 'brain2_intentions', 'brain2_checkins', 'conversation_turns',
    'brain1_profile_versions', 'brain1_outcomes', 'brain1_open_questions', 'brain1_runs', 'brain1_area_summaries',
]
# Never cleared: profiles (accounts) and brain1_consents (her choices, not history).
CHROMA_COLLECTIONS = ('moments', 'profile_understanding', 'memories')  # 'moments' is legacy, cleared if present


def main() -> None:
    conn = sqlite3.connect(SQL_STORAGE_DIR / 'selfie_me.db')
    existing = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    for table in [t for t in HISTORY_TABLES + ['moments'] if t in existing]:  # `moments` only on pre-V03 databases
        deleted = conn.execute(f'DELETE FROM {table}').rowcount
        print(f'{table}: deleted {deleted} rows')
    conn.commit()
    conn.close()

    import chromadb

    client = chromadb.PersistentClient(path=str(RAG_STORAGE_DIR))
    for name in CHROMA_COLLECTIONS:
        collection = client.get_or_create_collection(name)
        before = collection.count()
        ids = collection.get().get('ids') or []
        if ids:
            collection.delete(ids=ids)
        print(f'chroma[{name}]: {before} -> {collection.count()}')

    print('\nprofiles table untouched — accounts are preserved.')


if __name__ == '__main__':
    main()
