# Testing Strategy

*Version 0.3 | Company Document 31*

Define how product and AI behavior are verified.

## Software Tests

Unit, integration, API contract, end-to-end, migration, security and mobile regression tests.

## AI Tests

- Extraction accuracy.
- Retrieval relevance.
- Belief-change precision/recall.
- Evidence attribution.
- Fact-vs-inference labeling.
- Contradiction handling.
- Deletion propagation.
- Zero Profile writes without a recorded explicit acceptance event, tested adversarially — release-blocking, same severity as a cross-user leak.

## Founder Test Set

Create a private set of known historical statements and expected evolution relationships to regression-test every release, including at least one full Profile refinement case (a real skill, emotion, or other persona domain) run end to end — a rejected proposal, a refined-then-accepted proposal, and confirmation that an accepted proposal actually triggers follow-through support.

## Working Status

This is a working document. It should evolve through founder usage, user research, product experiments, technical validation, and legal/security review.

## Basis

Grounded in the selfie.Me Strategic Framework and Business Model Canvas, the founder's clarified direction, and the Two Brains / Profile implementation plan formalized in the Architecture, Functional and Technical Design Documents (V02).
