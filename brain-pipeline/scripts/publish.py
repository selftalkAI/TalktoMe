"""Stage 4 helper — hands Brain 2's finished work to Brain 1 inside the app.

Writes to the orchestration-service SQLite DB, following the app's one rule:
Brain 2 may PROPOSE, never accept.
  - each final insight      -> `memories` row, status='candidate'
                               (source_type='brain_pipeline', source_id=<insight id>)
  - each profile/<domain>.md -> `profile_entries` row, status='proposed'
Nothing becomes 'active'/'accepted' until Brain 1 accepts it in the app.

Idempotent: an insight already published with identical content is reused;
changed content creates a new candidate that supersedes the old one. A domain
whose identical text is already proposed/accepted is skipped. If a different
proposal is already waiting for that domain, it is left alone unless that
proposal came from this pipeline AND --replace-pending is given.
Anything above `max_publish_tier` stays on disk only.

Usage:  python publish.py <user> [--dry-run] [--replace-pending]
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import uuid

from _common import SENSITIVITY_TIERS, brain2_dir, db_path, die, load_config, load_json, now_iso, parse_front_matter, save_json


def tier_ok(tier: str, max_tier: str) -> bool:
    return SENSITIVITY_TIERS.index(tier) <= SENSITIVITY_TIERS.index(max_tier)


def insight_content(fm: dict, body: str) -> str:
    summary = str(fm.get('summary') or '').strip()
    return f"{fm['title'].strip()}. {summary}".strip() if summary else fm['title'].strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('user')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--replace-pending', action='store_true')
    args = parser.parse_args()

    cfg = load_config(args.user)
    email = cfg['profile_email']
    max_tier = cfg.get('max_publish_tier', 'T2')
    out = brain2_dir(args.user)
    state_path = out / '.publish-state.json'
    state = load_json(state_path, {'insights': {}, 'profile_entries': {}})
    path = db_path(cfg)
    if not path.exists():
        die(f'DB not found: {path}')

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    now = now_iso()
    log: list[str] = []
    memory_ids: dict[str, str] = {}

    # ---- insights -> memories (candidate) -------------------------------------------
    for p in sorted(out.glob('ins-*.md')):
        fm, body = parse_front_matter(p.read_text(encoding='utf-8'))
        iid = fm['id']
        if not tier_ok(fm['sensitivity_tier'], max_tier):
            log.append(f'HELD   {iid} (tier {fm["sensitivity_tier"]} > {max_tier}, stays on disk)')
            continue
        content = insight_content(fm, body)
        existing = conn.execute(
            "SELECT * FROM memories WHERE profile_email = ? AND source_type = 'brain_pipeline' AND source_id = ? "
            "AND status NOT IN ('superseded', 'deleted') ORDER BY created_at DESC LIMIT 1",
            (email, iid),
        ).fetchone()
        if existing and existing['content'] == content:
            memory_ids[iid] = existing['memory_id']
            continue
        if existing and existing['status'] in ('active', 'suppressed'):
            # Brain 1 already decided on this one; keep their decision, don't re-propose.
            memory_ids[iid] = existing['memory_id']
            log.append(f'KEPT   {iid} (Brain 1 already marked it {existing["status"]})')
            continue
        new_id = f'mem_{uuid.uuid4().hex[:12]}'
        memory_ids[iid] = new_id
        log.append(f"{'UPDATE' if existing else 'NEW   '} memory {new_id} <- {iid}")
        if args.dry_run:
            continue
        if existing:
            conn.execute("UPDATE memories SET status = 'superseded', updated_at = ? WHERE memory_id = ?", (now, existing['memory_id']))
        conn.execute(
            'INSERT INTO memories (memory_id, profile_email, type, domain, content, explicitness, confidence, '
            'sensitivity_tier, status, rationale_code, source_type, source_id, supersedes_id, created_at, updated_at) '
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'candidate', 'brain2_pipeline', 'brain_pipeline', ?, ?, ?, ?)",
            (new_id, email, fm['type'], fm['domain'], content, fm['explicitness'], float(fm['confidence']),
             fm['sensitivity_tier'], iid, existing['memory_id'] if existing else None, now, now),
        )
        state['insights'][iid] = new_id

    # ---- profile/<domain>.md -> profile_entries (proposed) --------------------------
    for p in sorted((out / 'profile').glob('*.md')):
        fm, body = parse_front_matter(p.read_text(encoding='utf-8'))
        domain, content = fm['domain'], body.strip()
        if not tier_ok(fm['sensitivity_tier'], max_tier):
            log.append(f'HELD   profile/{domain} (tier {fm["sensitivity_tier"]} > {max_tier})')
            continue
        rows = conn.execute(
            'SELECT * FROM profile_entries WHERE profile_email = ? AND domain = ? ORDER BY version DESC, proposed_at DESC',
            (email, domain),
        ).fetchall()
        accepted = next((r for r in rows if r['status'] == 'accepted'), None)
        pending = next((r for r in rows if r['status'] == 'proposed'), None)
        if (accepted and accepted['content'] == content) or (pending and pending['content'] == content):
            log.append(f'SAME   profile/{domain} (identical text already {"proposed" if pending else "accepted"})')
            continue
        if pending:
            ours = pending['profile_entry_id'] in state['profile_entries'].values()
            if not (ours and args.replace_pending):
                log.append(f'WAIT   profile/{domain} (a proposal is already waiting for Brain 1 — '
                           f'{"rerun with --replace-pending" if ours else "made by the app, left alone"})')
                continue
            log.append(f'REJECT {pending["profile_entry_id"]} (older pipeline proposal, replaced)')
            if not args.dry_run:
                conn.execute("UPDATE profile_entries SET status = 'rejected' WHERE profile_entry_id = ?", (pending['profile_entry_id'],))
        entry_id = f'profile_entry_{uuid.uuid4().hex[:12]}'
        version = (accepted['version'] + 1) if accepted else 1
        sources = [memory_ids[i] for i in fm.get('insight_ids') or [] if i in memory_ids]
        log.append(f'PROPOSE profile/{domain} v{version} -> {entry_id} ({len(sources)} source memories)')
        if args.dry_run:
            continue
        conn.execute(
            'INSERT INTO profile_entries (profile_entry_id, profile_email, domain, version, content, source_memory_ids, '
            "status, proposed_at, accepted_at, superseded_by) VALUES (?, ?, ?, ?, ?, ?, 'proposed', ?, NULL, NULL)",
            (entry_id, email, domain, version, content, json.dumps(sources), now),
        )
        state['profile_entries'][domain] = entry_id

    if args.dry_run:
        conn.rollback()
    else:
        conn.commit()
        state['last_run'] = {'at': now, 'actions': len(log)}
        save_json(state_path, state)
        (out / 'publish-log.md').write_text(f'# Publish log — {now}\n\n' + '\n'.join(f'- {l}' for l in log) + '\n', encoding='utf-8')
    conn.close()
    print(('DRY RUN — nothing written\n' if args.dry_run else '') + ('\n'.join(log) or 'nothing to publish'))


if __name__ == '__main__':
    main()
