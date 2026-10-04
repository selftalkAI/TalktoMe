from __future__ import annotations

from pathlib import Path

import pytest

from app import db


@pytest.fixture
def temp_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A fresh SQLite database for one test — never the dev database."""
    path = tmp_path / 'test.db'
    monkeypatch.setattr(db, 'DB_PATH', path)
    db.init_db()
    return path
