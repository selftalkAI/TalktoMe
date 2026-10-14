# Brain Pipeline — Architecture

## What it does

The pipeline turns what **Brain 1** (you) writes and records — journals, notes,
PDFs, spreadsheet exports, and everything already entered in the selfie.Me app —
into **Brain 2**'s understanding of you: small, evidence-grounded *insights*
and one *Profile entry* per life area (skill, emotion, learning, reading, plus
any custom area). Results land in the app as **proposals**. Nothing becomes
part of your Profile until you accept it — the same rule the app already
enforces in `orchestration-service/app/brain2/`.

It runs as **Claude Code agents** on your Claude plan. No Ollama, no Llama, no
API key. The deterministic parts (file conversion, caching, checkpoints,
validation, the DB write) are small Python scripts in `scripts/`; the agents
only do the reading and writing that needs judgement.

## Pipeline Overview

```
User / /brain skill invocation
        │
        ▼
┌────────────────────┐
│  /brain (skill)    │  Orchestrator — config, dependency check, run mode, sequencing
└────────────────────┘
        │
        ├───────────────┬───────────────┬────────────────┬────────────────┐
        ▼               ▼               ▼                ▼                ▼
  Stage 1a         Stage 1b        Stage 2          Stage 3          Stage 4
  BRAIN 1          BRAIN 1         BRAIN 2          BRAIN 2          BRAIN 2
  capture-fs       capture-app     extract          review           propose
  agent            agent           agent            agent            agent
        │               │               │                │                │
        ▼               ▼               ▼                ▼                ▼
  tmp/brain1/<user>/              tmp/brain2/      tmp/brain2/       SQLite DB
                                  <user>/draft/    <user>/ins-*.md   memories (candidate)
                                                   profile/*.md      profile_entries (proposed)
```

| Template (Issue Profile Pipeline) | Brain pipeline |
|---|---|
| profile-master-agent | `/brain` skill (main thread — subagents can't launch subagents) |
| source-confluence-agent | `brain1-capture-app-agent` (the app DB is Brain 1's "Confluence") |
| source-fs-agent | `brain1-capture-fs-agent` |
| extract-agent → issue profiles | `brain2-extract-agent` → insights |
| review-agent | `brain2-review-agent` (+ one Profile entry per domain) |
| publish-agent → Postgres + ChromaDB | `brain2-propose-agent` → `memories` + `profile_entries` as *proposals* |

## Agents

### `/brain` — Orchestrator (`.claude/skills/brain/SKILL.md`)

- Loads and validates `tmp/config/<user>-brain.yml`
- Detects **full** vs **incremental** mode (existing `tmp/brain2/<user>/ins-*.md`)
- Checks dependencies (Python packages, DB file, tables, your profile row) before doing any work
- Clears `tmp/brain2/<user>/draft/` at the start of each run
- Sequences Stage 1 → 2 → 3 → 4, skipping stages by flag
- Writes `run-manifest.json`
- `init <user> --email …` scaffolds a config without running

Flags: `--capture-only`, `--extract-only`, `--review-only`, `--propose-only`, `--full`, `--replace-pending`

### Stage 1a — `brain1-capture-fs-agent`

- Reads `type: filesystem, enabled: true` entries from the config, or one ad-hoc path
- Converts PDF (pypdf), Excel (openpyxl), CSV, and copies `.md`/`.txt`
- Version cache by `mtime` in `.source-index.json` — unchanged files are skipped
- Output: `<sanitised_basename>__<category>__fs.txt` with a metadata header

### Stage 1b — `brain1-capture-app-agent`

- Opens `Storage/sql_storage/selfie_me.db` **read-only**
- Exports moments (one file per month), memories, and intentions + check-ins for your `profile_email`
- Keeps every record id (`[mom_0003]`, `[mem_…]`) so Brain 2 can cite it
- Version cache by content hash

Both Brain 1 agents share the output folder and `.source-index.json` and can run in parallel.

### Stage 2 — `brain2-extract-agent`

- **Full mode:** every source file. **Incremental:** only files new or changed since `.extraction-baseline.json`
- Reads everything as one blended corpus and cross-references sources
- Extracts the **maximum** number of distinct insights — one file each, no merging here
- Every insight carries verbatim evidence (file + record id/page/line + quote ≤ 40 words), explicit vs inferred, confidence, and a sensitivity tier (T0–T3)
- Output: `tmp/brain2/<user>/draft/ins-<user>-NNNN.md` + `draft/index.md`, checked by `validate.py draft`
- Updates `.extraction-baseline.json`

Drafts have empty `summary`, `tags`, `related` — Stage 3 fills them.

### Stage 3 — `brain2-review-agent`

1. **Duplicate detection** — shared evidence ref, near-identical title, or contained statement; merges true duplicates and keeps `merged_from`
2. **Cross-linking** — fills `related` via shared causes, the same habit across sources, and domain families
3. **Tag normalisation** — one controlled vocabulary, 3–8 lowercase-hyphenated tags each
4. **Summary fill** — 2–3 sentence, second-person, retrieval-friendly summaries
5. **Publish library** — final `ins-*.md` + `index.md`; `draft/` kept for audit
6. **Profile entries** — `profile/<domain>.md`, grounded only in listed insights
7. **Review report** — `review-report.md` with every merge, link, tag, and omission

**Incremental mode:** loads the published library as the base set and merges new drafts in without renumbering existing ids; new ids continue from the highest existing one.

### Stage 4 — `brain2-propose-agent`

| Target | Purpose | Behaviour |
|---|---|---|
| `memories` table | Candidate facts for you to confirm | `status='candidate'`, `source_type='brain_pipeline'`, `source_id=<insight id>`; changed content supersedes the old candidate; anything you already marked `active`/`suppressed` is left alone |
| `profile_entries` table | Proposed Profile text per domain | `status='proposed'`, next version after your accepted one; identical text is skipped; an existing pending proposal is never overwritten (unless it came from this pipeline and `--replace-pending` is set) |

Anything above `max_publish_tier` (default `T2`) stays on disk and is never written to the DB.
Always dry-runs first. You accept, refine, or reject in the app through the existing `brain2/orchestrator.py` endpoints.

## `tmp/` Folder Layout

```
brain-pipeline/tmp/
├── config/
│   └── <user>-brain.yml          Your config — sources, key areas, publish tier
│
├── brain1/                        BRAIN 1 — raw material, unchanged
│   └── <user>/
│       ├── .source-index.json     Version cache — mtime (files) or content hash (app)
│       ├── index.md               Human-readable listing of captured files
│       ├── .extraction-baseline.json   Stage 2 checkpoint — what Brain 2 has read
│       └── <name>__<category>__<fs|app>.txt   One file per captured document / month
│
└── brain2/                        BRAIN 2 — understanding, proposed
    └── <user>/
        ├── run-manifest.json      Run metadata — time, mode, counts
        ├── index.md               Final insight index (rebuilt each run)
        ├── review-report.md       Stage 3 audit — merges, links, tags, omissions
        ├── publish-log.md         Stage 4 — what was proposed, held, skipped
        ├── .publish-state.json    insight id → memory id, domain → entry id
        ├── ins-<user>-NNNN.md     Final insights (one per insight)
        ├── profile/
        │   └── <domain>.md        Proposed Profile entry per life area
        └── draft/
            ├── index.md           Draft index (kept for audit)
            └── ins-<user>-NNNN.md Raw drafts from Stage 2
```

### Why `tmp/` and git-ignored?

It's your private material. `brain-pipeline/tmp/` is in `.gitignore`, so
nothing personal is ever committed. `draft/` is cleared at the start of each
run; everything else persists so incremental runs only redo what changed.

## Grounding & privacy rules (all agents)

- No claim without verbatim evidence from Brain 1's own sources
- Inferred patterns need ≥ 2 pieces of evidence and confidence ≤ 0.7
- No diagnoses or clinical labels unless you used those words
- Sensitivity tiers are never lowered; T3 is held on disk by default
- Agents report counts, never your content, in chat

## Quick start

```bash
pip install -r brain-pipeline/requirements.txt
# in Claude Code, from the repo root:
/brain init sujitha --email you@example.com      # then edit tmp/config/sujitha-brain.yml
/brain sujitha                                     # full run
/brain sujitha                                     # later runs are incremental automatically
/brain capture sujitha ~/Desktop/notes.pdf notes  # ad-hoc file
```
