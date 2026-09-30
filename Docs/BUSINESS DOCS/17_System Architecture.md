# System Architecture

*Version 0.3 | Company Document 17*

Define major technical components and interactions.

## Architecture

Mobile/Web -> API Gateway/BFF -> Identity -> Capture Service -> Event/Workflow Orchestrator (Brain 2 — one orchestrating model, many jobs; see `12_Agentic AI Architecture`) -> Memory / Belief / Decision / Profile Stores -> World Knowledge Gateway -> Scheduler -> PostgreSQL/pgvector + Object Storage -> Retrieval/Reranking -> LLM/ML Services -> Reflection/Advisor UI.

## Pattern

Start as a modular monolith plus background workers. Separate services only where scale, security isolation or model workloads justify it. The "services" above are code and ownership boundaries, not separate AI agents — the reasoning itself is one orchestrator that holds no state of its own between turns; all durable state lives in the Stores.

## Event Flow

CaptureReceived -> SourceStored -> MemoryExtracted -> RelatedHistoryRetrieved -> EvolutionEvaluated -> PersonalGraphUpdated -> ReflectionCandidateCreated -> ProfileProposalCreated -> UserFeedbackRecorded -> FollowThroughScheduled (on acceptance only).

## Working Status

This is a working document. It should evolve through founder usage, user research, product experiments, technical validation, and legal/security review.

## Basis

Grounded in the selfie.Me Strategic Framework and Business Model Canvas, the founder's clarified direction, and the Two Brains / Profile implementation plan formalized in the Architecture, Functional and Technical Design Documents (V02).
