"""Stage 2 checkpoint — which Brain 1 source files Brain 2 has already extracted.

Usage:
  python extraction_baseline.py delta <user> [--full]   # prints files to extract, one per line
  python extraction_baseline.py mark <user>             # record every current source file as extracted

A file counts as "new" if it was never extracted OR its captured version
changed since (an edited journal, a month with new moments).
"""

from __future__ import annotations

import argparse

from _common import load_json, now_iso, save_json, sources_dir


def current_files(user: str) -> dict[str, str]:
    index = load_json(sources_dir(user) / '.source-index.json', {})
    return {item['file']: item['version'] for item in index.values() if (sources_dir(user) / item['file']).exists()}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('cmd', choices=['delta', 'mark'])
    parser.add_argument('user')
    parser.add_argument('--full', action='store_true', help='ignore the baseline and list every file')
    args = parser.parse_args()

    path = sources_dir(args.user) / '.extraction-baseline.json'
    baseline = load_json(path, {'files': {}})
    files = current_files(args.user)

    if args.cmd == 'delta':
        for name, version in sorted(files.items()):
            if args.full or baseline['files'].get(name) != version:
                print(name)
    else:
        baseline['files'].update(files)
        baseline['updated_at'] = now_iso()
        save_json(path, baseline)
        print(f'baseline: {len(baseline["files"])} files recorded')


if __name__ == '__main__':
    main()
