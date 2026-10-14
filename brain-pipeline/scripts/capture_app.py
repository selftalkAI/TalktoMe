"""Stage 1b helper — what Brain 1 already told the selfie.Me app -> tmp/brain1/<user>/*.txt

Opens the orchestration-service SQLite DB READ-ONLY and exports, for one
profile_email:
  - moments, grouped by month      -> moments-YYYY-MM__moments__app.txt
  - memories (active/candidate)    -> memories__memories__app.txt
  - intentions + daily check-ins   -> intention-<title>__checkins__app.txt
Every record keeps its DB id ([mom_0003], [mem_ab12...]) so Brain 2 can cite it.
A file is rewritten only when its content hash changes (`.source-index.json`).

Usage:  python capture_app.py <user>
"""

from __future__ import annotations

import argparse
import sqlite3
from collections import defaultdict

from _common import db_path, die, load_config, load_json, now_iso, sanitise, save_json, sha256_text, sources_dir
from capture_fs import write_index_md


def _rows(conn: sqlite3.Connection, sql: str, params: tuple) -> list[sqlite3.Row]:
    try:
        return conn.execute(sql, params).fetchall()
    except sqlite3.OperationalError:
        return []  # table not created yet on this DB


def export(user: str, cfg: dict, include: set[str]) -> dict[str, str]:
    email = cfg['profile_email']
    path = db_path(cfg)
    if not path.exists():
        die(f'DB not found: {path}')
    conn = sqlite3.connect(f'file:{path}?mode=ro', uri=True)
    conn.row_factory = sqlite3.Row
    files: dict[str, str] = {}

    if 'moments' in include:
        by_month: dict[str, list[str]] = defaultdict(list)
        for m in _rows(conn, 'SELECT * FROM moments WHERE profile_email = ? ORDER BY created_at', (email,)):
            lines = [f"[{m['id']}] {m['created_at']} via {m['source']}" + (f" mood={m['mood']}" if m['mood'] else '')]
            lines.append(m['content'].strip())
            if m['reflection']:
                lines.append(f"(reflection) {m['reflection'].strip()}")
            by_month[m['created_at'][:7]].append('\n'.join(lines))
        for month, blocks in by_month.items():
            files[f'moments-{month}__moments__app.txt'] = '\n\n'.join(blocks)

    if 'memories' in include:
        mems = _rows(
            conn,
            "SELECT * FROM memories WHERE profile_email = ? AND status IN ('active', 'candidate', 'requires_confirmation') "
            'ORDER BY created_at',
            (email,),
        )
        if mems:
            files['memories__memories__app.txt'] = '\n'.join(
                f"[{m['memory_id']}] status={m['status']} type={m['type']} domain={m['domain'] or '-'} "
                f"tier={m['sensitivity_tier']}: {m['content'].strip()}"
                for m in mems
            )

    if 'checkins' in include:
        for it in _rows(conn, "SELECT * FROM brain2_intentions WHERE profile_email = ? AND status = 'active'", (email,)):
            checks = _rows(
                conn,
                'SELECT * FROM brain2_checkins WHERE intention_id = ? ORDER BY checkin_date',
                (it['intention_id'],),
            )
            body = [f"[{it['intention_id']}] intention \"{it['title']}\" domain={it['domain']} target={it['target_minutes']} min/day"]
            body += [
                f"  {c['checkin_date']}: {c['actual_minutes']} min" + (f" — {c['note']}" if c['note'] else '')
                for c in checks
            ]
            files[f"intention-{sanitise(it['title'], 40)}__checkins__app.txt"] = '\n'.join(body)

    conn.close()
    return files


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('user')
    args = parser.parse_args()
    cfg = load_config(args.user)
    entries = [s for s in cfg['sources'] if s.get('type') == 'selfie_app' and s.get('enabled')]
    if not entries:
        print('app: no enabled selfie_app source, nothing to do')
        return
    include = set(entries[0].get('include', ['moments', 'memories', 'checkins']))

    out_dir = sources_dir(args.user)
    out_dir.mkdir(parents=True, exist_ok=True)
    index_path = out_dir / '.source-index.json'
    index = load_json(index_path, {})
    written = unchanged = 0

    for name, body in export(args.user, cfg, include).items():
        key = f'app:{name}'
        version = sha256_text(body)
        if index.get(key, {}).get('version') == version and (out_dir / name).exists():
            unchanged += 1
            continue
        header = f"source: selfie_app\nprofile_email: {cfg['profile_email']}\ncaptured_at: {now_iso()}\n---\n"
        (out_dir / name).write_text(header + body + '\n', encoding='utf-8')
        index[key] = {'file': name, 'version': version, 'source': 'selfie_app', 'category': name.split('__')[1]}
        written += 1

    save_json(index_path, index)
    write_index_md(args.user)
    print(f'app: {written} written, {unchanged} unchanged')


if __name__ == '__main__':
    main()
