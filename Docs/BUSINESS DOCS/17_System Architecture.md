# System Architecture

*Version 0.4 | Company Document 17*

Define major technical components and interactions.

## Architecture

Web/Mobile → Orchestration Service (API, data layer, Brain 1 orchestration, Brain 2 turn pipeline) → Agentic Service (Brain 1 core agents and sub-agents, Brain 2 steps, model gateway) → Memory / Profile / Knowledge stores → LLM providers.

## Pattern

A modular monolith plus background workers (Reflector, proactive check-ins). Logical components are code and ownership boundaries, not separate deployments.

## Turn Flow

MessageReceived → SafetyChecked → CoresRouted → AreasInvestigated → ContextPackCompiled → PersonaSelected → Understood → Planned → Spoken → Checked → ReplySent → TurnRemembered → OutcomeScored.

## Storage

Target: PostgreSQL/pgvector + object storage. Today: SQLite + Chroma (see `TDD §34`).

## Working Status

This is a working document. It should evolve through founder usage, user research, product experiments, technical validation, and legal/security review.

## Basis

Grounded in the selfie.Me Strategic Framework and Business Model Canvas, the founder's clarified direction, and the Brain 1 / Brain 2 design in `Docs/FEATURES/Building_Brain1.md` and `Docs/FEATURES/Building_Brain2.md`, formalized in the Architecture, Functional and Technical Design Documents (V03).
