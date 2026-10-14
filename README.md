# selfie.Me

A starter project for a privacy-first personal memory AI product.

This repository contains a basic MVP scaffold aligned with the strategic documents in `Docs/`:
- capture personal memories and reflections
- preserve provenance and user control
- structure evidence, beliefs, and decisions
- provide grounded retrieval and reflection experiences

## Structure

Three independently runnable services, matching `Docs/selfieMe_Architecture_Design_Document.md`:

- **`observability-portal/`** — Next.js client. The user-facing surface: conversation UI, memory/belief review, decision workspace, agent approvals, and the transparency/audit views that give the portal its name. Talks only to the Orchestration Service.
- **`orchestration-service/`** — FastAPI API layer + data layer. Owns conversations, memories, beliefs, decisions, and policy/consent. Never calls a model provider directly — it delegates all model/agent work to the Agentic Service over HTTP.
- **`agentic-service/`** — The Agentic Layer. Wraps the model gateway (local Ollama or AWS Bedrock, switchable via `.env`) behind a small HTTP API (`/v1/complete`, `/v1/embed`). This is the only service that ever calls a model provider, and the only one expected to grow AWS Bedrock Agents / Action Groups later.
- **`docker-compose.yml`** — local data-layer infrastructure: Postgres (with pgvector) and Redis, shared by the Orchestration Service.

## Quick start

Start the data layer:

```bash
docker-compose up -d
```

Agentic Service (start first — Orchestration calls it):

```bash
cd agentic-service
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # defaults to MODEL_PROVIDER=ollama
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

To actually get a response from `/v1/complete`, install and run Ollama locally:

```bash
brew install ollama
ollama serve
ollama pull llama3.1
ollama pull nomic-embed-text
```

Orchestration Service:

```bash
cd orchestration-service
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # defaults to AGENTIC_SERVICE_URL=http://localhost:8001
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Observability Portal:

```bash
cd observability-portal
npm install
npm run dev
```

To use AWS Bedrock instead of Ollama once you're ready, edit `agentic-service/.env`:
`MODEL_PROVIDER=bedrock`, then run `aws configure` (or set AWS env vars) and enable the
chosen model in the Bedrock console. Nothing in Orchestration or the Portal changes.

## Brain 1 / Brain 2 agents (Claude Code)

`brain-pipeline/` runs Brain 1 (capture your journals, notes and app entries) and
Brain 2 (extract → review → propose Profile entries) as Claude Code agents on your
Claude plan — no Ollama needed. In Claude Code: `/brain init <you> --email <email>`,
then `/brain <you>`. Proposals show up in the app for you to accept. See
`brain-pipeline/ARCHITECTURE.md`.

## Brain 2 actions on Claude

Each Brain 2 action (Thalamus, Sensory Cortex, Hippocampus, Prefrontal Cortex,
Amygdala, Broca, World Knowledge) also exists as a Claude agent in
`.claude/agents/brain2-*.md`, with the same input and output JSON as its Python
agent. Set `AGENT_ENGINE=claude` in `agentic-service/.env` and the service runs
each action on Claude via the Claude Code CLI (your signed-in Claude plan, no API
key). Nothing else changes: same endpoints, same workflow, same results.
Embeddings still come from `MODEL_PROVIDER`.

## Product intent

The current version is intentionally simple and focused on the founder pilot:
- daily voice/text capture
- searchable memory archive
- belief and decision timeline
- evidence-backed reflection queries
- safe privacy controls

## Notes

This is a scaffold only. It is designed to be extended with real storage, auth, AI pipelines, and user feedback loops. See `Docs/` for the full architecture, functional spec, and technical design (V01).
