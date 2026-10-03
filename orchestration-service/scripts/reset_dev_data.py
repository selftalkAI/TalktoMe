"""Clears local dev activity history — never accounts, never the knowledge base.

Deletes: moments, memories, profile_entries, brain2_intentions,
brain2_checkins (SQL) and their matching Chroma collections (moments,
profile_understanding, memories).

Never touches: the `profiles` table (accounts are not "history" — a prior
run of an ad-hoc version of this cleanup accidentally deleted the `profiles`
rows too, which is exactly the mistake this script exists to stop repeating),
and never `rag_documents`/`rag_chunks`/`document_chunks` (the ingested book
knowledge base — unrelated to any profile's activity).

Usage (from orchestration-service/, with its venv active):
    python3 scripts/reset_dev_data.py
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.paths import RAG_STORAGE_DIR, SQL_STORAGE_DIR  # noqa: E402

HISTORY_TABLES = ['moments', 'memories', 'profile_entries', 'brain2_intentions', 'brain2_checkins']
CHROMA_COLLECTIONS = ('moments', 'profile_understanding', 'memories')


def main() -> None:
    conn = sqlite3.connect(SQL_STORAGE_DIR / 'selfie_me.db')
    for table in HISTORY_TABLES:
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
