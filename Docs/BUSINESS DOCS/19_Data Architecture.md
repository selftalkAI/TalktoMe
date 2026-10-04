# Data Architecture

*Version 0.3 | Company Document 19*

Define where data lives and how it moves.

## Data Zones

- Raw source: original audio/text/photo.
- Canonical personal model: memories, beliefs, goals, decisions, relationships, and Profile entries (versioned, per domain) — each Profile entry references the memories/beliefs it was synthesized from and the outside-knowledge source it was compared against.
- Retrieval: chunks, embeddings, indexes.
- Analytics/ML: de-identified or permissioned feature/training datasets.
- Audit: security and agent-action events.

## Design Rules

- Separate raw evidence from AI interpretation.
- Version derived records.
- Propagate deletion.
- Encrypt sensitive content.
- Use user-scoped authorization in every retrieval path.
- An outside-knowledge lookup discloses only the minimum content necessary for that domain comparison.

## Working Status

This is a working document. It should evolve through founder usage, user research, product experiments, technical validation, and legal/security review.

## Basis

Grounded in the selfie.Me Strategic Framework and Business Model Canvas, the founder's clarified direction, and the Brain 1 / Brain 2 design in `Docs/FEATURES/Building_Brain1.md` and `Building_Brain2.md`, formalized in the Architecture, Functional and Technical Design Documents (V03).
