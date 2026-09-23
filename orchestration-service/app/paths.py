from __future__ import annotations

from pathlib import Path

# orchestration-service/app/paths.py -> repo root is two levels up.
REPO_ROOT = Path(__file__).resolve().parents[2]
STORAGE_ROOT = REPO_ROOT / 'Storage'
SQL_STORAGE_DIR = STORAGE_ROOT / 'sql_storage'
RAG_STORAGE_DIR = STORAGE_ROOT / 'rag_storage'

SQL_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
RAG_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
