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

## API Rules

- Authenticated user scope required.
- Idempotency for capture ingestion.
- Source/provenance identifiers returned with AI-derived outputs.
- Async jobs expose processing state.
- Deletion requests cascade to derived indexes.
- A Profile write only occurs through an explicit accept call — no other endpoint may supersede a Profile entry.

## Working Status

This is a working document. It should evolve through founder usage, user research, product experiments, technical validation, and legal/security review.

## Basis

Grounded in the selfie.Me Strategic Framework and Business Model Canvas, the founder's clarified direction, and the Two Brains / Profile implementation plan formalized in the Architecture, Functional and Technical Design Documents (V02).
