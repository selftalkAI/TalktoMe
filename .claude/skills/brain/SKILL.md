---
name: brain
description: Run the selfie.Me Brain pipeline — Brain 1 captures the user's journals/notes/app entries, Brain 2 extracts, reviews and proposes Profile entries for the user to accept in the app. Use for "/brain", "run the brain", "update my profile from my journal", or "/brain init <user>".
---

# /brain — Brain 1 → Brain 2 pipeline (orchestrator)

You are the orchestrator (the "brain-master"). You run in the main conversation
because only the main thread can launch the stage subagents. You sequence the
stages, check dependencies, and summarise — you do not extract or write
Profile text yourself.

Full design: `brain-pipeline/ARCHITECTURE.md`. All commands run from the repo root.

## Arguments
`/brain <user> [--capture-only | --extract-only | --review-only | --propose-only] [--full] [--replace-pending]`
`/brain init <user> --email <email>` — scaffold a config, don't run anything.
`/brain capture <user> <path> [category]` — ad-hoc Stage 1a for one file/folder.

If `<user>` is missing, look for `brain-pipeline/tmp/config/*-brain.yml`; if
exactly one exists use it, otherwise ask.

## init
`python brain-pipeline/scripts/brain_init.py init <user> --email <email>` then
tell the user to open `brain-pipeline/tmp/config/<user>-brain.yml`, point the
`journal` source at their folder and set `enabled: true`. Stop.

## Run
1. **Dependencies** — `python brain-pipeline/scripts/brain_init.py check <user>`.
   On FAIL: show the lines and stop. (Missing packages:
   `pip install -r brain-pipeline/requirements.txt`.)
2. **Mode** — `python brain-pipeline/scripts/brain_init.py mode <user>` →
   `full` or `incremental`. `--full` forces full.
3. **Prepare** — unless `--review-only`/`--propose-only`:
   `python brain-pipeline/scripts/brain_init.py prepare <user>` (clears
   `tmp/brain2/<user>/draft/` only).
4. **Stage 1 — Brain 1 capture** (skip with `--extract-only`, `--review-only`,
   `--propose-only`). Launch in parallel, only for source types that are
   enabled in the config:
   - `brain1-capture-fs-agent` — prompt: `user: <user>`
   - `brain1-capture-app-agent` — prompt: `user: <user>`
5. **Stage 2 — Brain 2 extract** (skip with `--capture-only`, `--review-only`,
   `--propose-only`): `brain2-extract-agent` — prompt: `user: <user>, mode: <mode>`.
   If it reports 0 new files in incremental mode, skip Stage 3 and 4.
6. **Stage 3 — Brain 2 review** (skip with `--capture-only`, `--extract-only`,
   `--propose-only`): `brain2-review-agent` — prompt: `user: <user>, mode: <mode>`.
7. **Stage 4 — Brain 2 propose** (only on a full run or `--propose-only`):
   `brain2-propose-agent` — prompt: `user: <user>, replace_pending: <true|false>`.
8. **Manifest** — `python brain-pipeline/scripts/brain_init.py manifest <user>
   --mode <mode> --stages <comma list actually run>`.

Each stage starts only after the previous one reports success. If a stage
fails, stop, run the manifest step with `--note "<stage> failed: <reason>"`,
and report.

## Final reply (short)
- mode, and what each stage did (one line each, from the agents' reports)
- where to look: `brain-pipeline/tmp/brain2/<user>/review-report.md` and `profile/`
- "Open selfie.Me to accept or refine N proposals" — never imply anything was accepted.

Never paste the user's journal content or insight text into the reply; they
can open the files.
