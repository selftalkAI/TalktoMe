"""Shared paths and helpers for the Brain 1 / Brain 2 pipeline scripts.

Every script here is plain, deterministic Python — no model calls. The
Claude Code agents in `.claude/agents/` do the reading/thinking; these
scripts do the parts that must be exact and repeatable (file conversion,
version caching, checkpoints, validation, the DB write).
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PIPELINE_ROOT = Path(__file__).resolve().parents[1]          # brain-pipeline/
REPO_ROOT = PIPELINE_ROOT.parent                               # TalktoMe/
TMP = PIPELINE_ROOT / 'tmp'
DEFAULT_DB = REPO_ROOT / 'Storage' / 'sql_storage' / 'selfie_me.db'

KEY_AREAS = ('skill', 'emotion', 'learning', 'reading')        # mirrors app/brain1/key_areas.py
MEMORY_TYPES = {
    'fact', 'preference', 'goal', 'relationship', 'event',
    'routine', 'constraint', 'project_context', 'user_instruction',
}
SENSITIVITY_TIERS = ('T0', 'T1', 'T2', 'T3')


def config_path(user: str) -> Path:
    return TMP / 'config' / f'{user}-brain.yml'


def sources_dir(user: str) -> Path:
    return TMP / 'brain1' / user


def brain2_dir(user: str) -> Path:
    return TMP / 'brain2' / user


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def sanitise(name: str, max_len: int = 60) -> str:
    slug = re.sub(r'[^A-Za-z0-9]+', '-', name).strip('-').lower()
    return (slug or 'untitled')[:max_len]


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding='utf-8'))


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def load_config(user: str) -> dict[str, Any]:
    import yaml  # pyyaml

    path = config_path(user)
    if not path.exists():
        die(f'No config at {path}. Run: python brain-pipeline/scripts/brain_init.py init {user}')
    cfg = yaml.safe_load(path.read_text(encoding='utf-8')) or {}
    for key in ('user', 'profile_email', 'sources'):
        if key not in cfg:
            die(f'{path}: missing required key "{key}"')
    return cfg


def db_path(cfg: dict[str, Any]) -> Path:
    raw = cfg.get('db_path')
    return (REPO_ROOT / raw).resolve() if raw else DEFAULT_DB


def parse_front_matter(text: str) -> tuple[dict[str, Any], str]:
    """Splits a `---` YAML front-matter block from a Markdown body."""
    import yaml

    if not text.startswith('---'):
        return {}, text
    parts = text.split('---', 2)
    if len(parts) < 3:
        return {}, text
    return (yaml.safe_load(parts[1]) or {}), parts[2].lstrip('\n')


def die(message: str, code: int = 1) -> None:
    print(f'ERROR: {message}', file=sys.stderr)
    sys.exit(code)
