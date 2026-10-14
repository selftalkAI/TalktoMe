"""Orchestrator helpers: scaffold a config, check dependencies, detect run mode,
prepare the draft folder, and write the run manifest.

Usage:
  python brain_init.py init <user> --email you@example.com
  python brain_init.py check <user>
  python brain_init.py mode <user>                # prints "full" or "incremental"
  python brain_init.py prepare <user>             # clears brain2/<user>/draft/
  python brain_init.py manifest <user> --mode full --stages capture,extract,review,propose [--note "..."]
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys

from _common import (
    TMP, brain2_dir, config_path, db_path, die, load_config, now_iso, save_json, sources_dir, load_json,
)

TEMPLATE = """# Brain pipeline config for {user}
user: {user}
profile_email: {email}          # must match the email you sign in to selfie.Me with

# SQLite DB written by orchestration-service (relative to repo root).
db_path: Storage/sql_storage/selfie_me.db

# Life areas Brain 2 organises the Profile around. Add your own freely.
key_areas: [skill, emotion, learning, reading]

# Highest sensitivity tier Stage 4 may publish (T0 public .. T3 most private).
# Anything above this stays in tmp/ for you to look at, never in the DB.
max_publish_tier: T2

sources:
  # Stage 1a - Brain 1 files on disk (journals, notes, PDFs, CSV/Excel exports)
  - name: journal
    type: filesystem
    enabled: false
    path: ~/Documents/journal         # folder or single file
    category: journal                 # free label, ends up in the filename
    recursive: true
    extensions: [.md, .txt, .pdf, .csv, .xlsx]

  # Stage 1b - what Brain 1 already told the app (moments, memories, check-ins)
  - name: app
    type: selfie_app
    enabled: true
    include: [moments, memories, checkins]
"""


def cmd_init(args: argparse.Namespace) -> None:
    path = config_path(args.user)
    if path.exists() and not args.force:
        die(f'{path} already exists (use --force to overwrite)')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(TEMPLATE.format(user=args.user, email=args.email), encoding='utf-8')
    print(f'Created {path}')


def cmd_check(args: argparse.Namespace) -> None:
    problems: list[str] = []
    for module, pip_name in (('yaml', 'pyyaml'), ('pypdf', 'pypdf'), ('openpyxl', 'openpyxl')):
        try:
            __import__(module)
        except ImportError:
            problems.append(f'python package missing: {pip_name} (pip install -r brain-pipeline/requirements.txt)')

    cfg = load_config(args.user)
    uses_app = any(s.get('type') == 'selfie_app' and s.get('enabled') for s in cfg['sources'])
    path = db_path(cfg)
    if uses_app:
        if not path.exists():
            problems.append(f'DB not found at {path} (start orchestration-service once to create it)')
        else:
            with sqlite3.connect(path) as conn:
                tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            for table in ('moments', 'memories', 'profile_entries', 'profiles'):
                if table not in tables:
                    problems.append(f'DB table missing: {table}')
            if not problems:
                with sqlite3.connect(path) as conn:
                    found = conn.execute('SELECT 1 FROM profiles WHERE email = ?', (cfg['profile_email'],)).fetchone()
                if not found:
                    problems.append(f"profile_email {cfg['profile_email']} has no profile in the DB yet")

    if problems:
        for p in problems:
            print(f'FAIL  {p}')
        sys.exit(1)
    print('OK    all dependencies present')


def cmd_mode(args: argparse.Namespace) -> None:
    published = list(brain2_dir(args.user).glob('ins-*.md'))
    print('incremental' if published else 'full')


def cmd_prepare(args: argparse.Namespace) -> None:
    draft = brain2_dir(args.user) / 'draft'
    if draft.exists():
        shutil.rmtree(draft)
    draft.mkdir(parents=True)
    sources_dir(args.user).mkdir(parents=True, exist_ok=True)
    print(f'Cleared {draft}')


def cmd_manifest(args: argparse.Namespace) -> None:
    out = brain2_dir(args.user)
    src = sources_dir(args.user)
    manifest = {
        'user': args.user,
        'finished_at': now_iso(),
        'run_mode': args.mode,
        'stages_run': [s for s in args.stages.split(',') if s],
        'source_files': len([p for p in src.glob('*') if p.is_file() and not p.name.startswith('.') and p.name != 'index.md']),
        'draft_insights': len(list((out / 'draft').glob('ins-*.md'))),
        'published_insights': len(list(out.glob('ins-*.md'))),
        'profile_entries': sorted(p.stem for p in (out / 'profile').glob('*.md')),
        'publish_log': load_json(out / '.publish-state.json', {}).get('last_run'),
        'note': args.note,
    }
    save_json(out / 'run-manifest.json', manifest)
    print(f'Wrote {out / "run-manifest.json"}')


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('init'); p.add_argument('user'); p.add_argument('--email', required=True); p.add_argument('--force', action='store_true')
    for name in ('check', 'mode', 'prepare'):
        sub.add_parser(name).add_argument('user')
    p = sub.add_parser('manifest'); p.add_argument('user'); p.add_argument('--mode', required=True)
    p.add_argument('--stages', required=True); p.add_argument('--note', default='')
    args = parser.parse_args()
    TMP.mkdir(exist_ok=True)
    {'init': cmd_init, 'check': cmd_check, 'mode': cmd_mode, 'prepare': cmd_prepare, 'manifest': cmd_manifest}[args.cmd](args)


if __name__ == '__main__':
    main()
