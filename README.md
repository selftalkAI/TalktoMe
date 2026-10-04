# selfie.Me

A privacy-first "second brain" that knows you and talks to you like someone who does.

- **Brain 1 = you + your Persona** — a living, structured model of you (who you are, your people, places, tastes, goals, story, what works for you), built by 13 core agents on top of a governed memory layer and a knowledge base distilled from expert books. It never talks to you and never writes anything durable without your yes.
- **Brain 2 = the Voice** — the only part that talks to you. It speaks through a persona Brain 1 picks for the moment (a voice like friend / big sister / mentor / coach, an expertise like fitness or money, and a stance like listen / plan / celebrate), and every reply passes a quality check before you see it.

## Documentation

| Document | What it covers |
| --- | --- |
| [`Docs/selfieMe_Simple_Guide.md`](Docs/selfieMe_Simple_Guide.md) | The idea in plain language — start here |
| [`Docs/FEATURES/Building_Brain1.md`](Docs/FEATURES/Building_Brain1.md) | Brain 1 spec: Persona, 13 cores / 68 sub-agents, structured profile, Context Pack, knowledge, behaviour, build plan |
| [`Docs/FEATURES/Building_Brain2.md`](Docs/FEATURES/Building_Brain2.md) | Brain 2 spec: personas, five-step reply pipeline, prompt architecture, behaviour, build plan |
| [`Docs/selfieMe_Functional_Specification_Document.md`](Docs/selfieMe_Functional_Specification_Document.md) | FSD — what the product does (requirements, journeys, rules) |
| [`Docs/selfieMe_Architecture_Design_Document.md`](Docs/selfieMe_Architecture_Design_Document.md) | ADD — boundaries, trust, ADRs |
| [`Docs/selfieMe_Technical_Design_Document.md`](Docs/selfieMe_Technical_Design_Document.md) | TDD — services, data model, pipelines, APIs; §34 states what the repo runs today |
| `Docs/BUSINESS DOCS/` | Strategy, product, and business documentation |
| `Docs/PLAN/User Stories/` | User stories |

## Structure

Three independently runnable services:

- **`observability-portal/`** — Next.js client (port 3000). The user-facing surface. Talks only to the Orchestration Service.
- **`orchestration-service/`** — FastAPI API + data layer (port 8000). Owns profiles, memories, Brain 1 (`app/brain1/`) and Brain 2 orchestration (`app/brain2/`). Never calls a model provider directly.
- **`agentic-service/`** — The agent layer (port 8001). LangGraph agents (`app/agents/`) and the model gateway (Ollama or AWS Bedrock, switchable in `.env`). The only service that calls a model provider.

**Storage today:** SQLite at `Storage/sql_storage/selfie_me.db` and Chroma at `Storage/rag_storage/` (both created at runtime, never committed). `docker-compose.yml` provisions the PostgreSQL/Redis target described in the TDD, but the code does not use it yet (see `TDD §34`).

## Quick start

Install and run Ollama:

```bash
brew install ollama
ollama serve
ollama pull llama3.1
ollama pull nomic-embed-text
```

Agentic Service (start first — Orchestration calls it):

```bash
cd agentic-service
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # MODEL_PROVIDER=ollama
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

Orchestration Service:

```bash
cd orchestration-service
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # AGENTIC_SERVICE_URL=http://localhost:8001
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Observability Portal:

```bash
cd observability-portal
npm install
npm run dev
```

Load the expert book library into the knowledge base (once):

```bash
brew install poppler   # provides pdftotext
cd orchestration-service && python3 scripts/ingest_pdfs.py "../Docs/ASSETS/BOOKS"
```

**Model quality:** Brain 2's voice depends heavily on the model. The MVP runs on local `llama3.1`; to use a stronger model, set `MODEL_PROVIDER=bedrock` in `agentic-service/.env`, configure AWS credentials (`aws configure`), and enable the model in the Bedrock console. Nothing else changes.

## Build status

The Brain 1 / Brain 2 redesign is being built in phases — see `Building_Brain1.md` §18 and `Building_Brain2.md` §15. `TDD §34` tracks what is implemented versus planned.
