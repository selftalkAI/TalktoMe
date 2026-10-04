# API Specification — Initial

*Version 0.3 | Company Document 21*

Define initial service contracts.

## Core Endpoints

- `POST /captures`
- `GET /captures/{id}`
- `GET /memories/search`
- `GET /topics/{id}/evolution`
- `POST /inferences/{id}/feedback`
- `POST /advisor/query`
- `GET /reflections`
- `POST /export`
- `DELETE /memories/{id}`
- `GET /profile/{domain}`
- `POST /profile/{domain}/refine`
- `POST /profile/proposals/{id}/accept`
- `POST /profile/proposals/{id}/reject`
- `POST /brain/turn` (V03) — one conversational turn through Brain 1 and Brain 2
- `GET /brain1/profile` (V03) — the user's Brain 1 Profile with evidence (mirror view)
- `PATCH /brain1/profile/facets/{id}` (V03) — correct, confirm or forget a fact
- `PUT /brain1/preferences/voice` (V03) — set Brain 2's voice

## API Rules

- Authenticated user scope required.
- Idempotency for capture ingestion.
- Source/provenance identifiers returned with AI-derived outputs.
- Async jobs expose processing state.
- Deletion requests cascade to derived indexes.
- A Profile write only occurs through an explicit accept call — no other endpoint may supersede a Profile entry.
- A reply is returned only after it passes Brain 2's Check (V03).

## Working Status

This is a working document. It should evolve through founder usage, user research, product experiments, technical validation, and legal/security review.

## Basis

Grounded in the selfie.Me Strategic Framework and Business Model Canvas, the founder's clarified direction, and the Brain 1 / Brain 2 design in `Docs/FEATURES/Building_Brain1.md` and `Building_Brain2.md`, formalized in the Architecture, Functional and Technical Design Documents (V03).
