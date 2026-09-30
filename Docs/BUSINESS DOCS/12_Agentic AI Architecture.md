# Agentic AI Architecture

*Version 0.3 | Company Document 12*

Define how Brain 2's intelligence is structured, and its boundaries.

## Two Brains

Brain 1 is the user — sovereign, the only actor who ever decides or acts. Brain 2 is selfie.Me: everything described below belongs to Brain 2, and none of it has independent authority over Brain 1.

## One Orchestrator, Many Jobs

Brain 2 is not a set of separate AI agents. It is **one orchestrating model** that takes on different jobs depending on where it is in a conversation or workflow:

- **Capture** — ingests voice/text and preserves source provenance.
- **Memory formation** — creates durable memory objects and links entities.
- **Integration** — synthesizes memories and beliefs across the complete human persona into one coherent, standing Profile per domain, rather than leaving them as disconnected records.
- **Belief evolution** — maintains time-versioned opinions/beliefs and detects change.
- **Decision tracking** — records decision, rationale, alternatives, expectation and outcome.
- **Reflection** — periodically identifies meaningful changes and recurring patterns.
- **Advising** — uses relevant personal history when the user faces a new decision.
- **Integrity checking** — verifies evidence, confidence, permissions and fact-vs-inference boundaries.
- **Profile refinement (enhance)** — runs the propose/accept/refine/reject loop per domain — a skill, an emotion, a relationship, a habit, a learning area, or any other part of the persona — comparing the user's own reflection against outside knowledge, then following through with support once accepted.

The orchestrator itself holds no memory of its own between turns — everything durable lives in the tools below.

## Tools

- **Memory Store, Belief Store, Decision Store** — durable, versioned, user-scoped (PostgreSQL).
- **Profile Store** — versioned Profile entries per domain, synthesized from the Memory and Belief Stores.
- **World Knowledge Gateway** — provider-abstracted lookup of outside/expert domain knowledge, used only to draft a Profile proposal, never to write it.
- **Scheduler** — wakes the orchestrator on a recurring cadence to re-check an existing Profile entry, without needing new user input.

## Orchestration

Event-driven stateful workflow: new capture -> classify -> extract -> retrieve related state -> compare (against the user's own history, and, for Profile work, against outside knowledge) -> update graph -> evaluate significance -> optionally prepare a reflection or a Profile proposal -> await/record user confirmation -> on acceptance, follow through with ongoing support.

## Boundaries

- The orchestrator cannot silently rewrite historical records.
- The orchestrator cannot treat inference as user fact.
- The orchestrator cannot share personal information without authorization.
- High-impact external actions are outside V1.
- The orchestrator may never supersede an existing Profile entry without the user's recorded acceptance — whether the run was triggered by the user or by the Scheduler.

## Working Status

This is a working document. It should evolve through founder usage, user research, product experiments, technical validation, and legal/security review.

## Basis

Grounded in the selfie.Me Strategic Framework and Business Model Canvas, the founder's clarified direction, and the Two Brains / Profile implementation plan formalized in the Architecture, Functional and Technical Design Documents (V02), specifically ADR-013 (Brain 2 is one stateless orchestrator, not independent agents).
