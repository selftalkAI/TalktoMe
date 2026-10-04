# Belief and Evolution Model

*Version 0.3 | Company Document 14*

Define how opinions and thinking change over time.

## Belief Entity

Topic, position, rationale, confidence, source, timestamp, status.

## Evolution States

New, stable, strengthened, weakened, refined, uncertain, changed, reversed, abandoned.

## Change Record

Previous belief version, new version, detected differences, supporting evidence, possible causes, confidence, user confirmation.

## Critical Rule

Never overwrite a prior belief. Preserve each version and build an evolution timeline. The Profile layer (`13_Personal Memory Model`) reuses this exact rule for domain-level entries — Profile is simply a new consumer of it, not a different mechanism.

## Example

Topic: building selfie.Me full-time. Earlier position: leave job and focus. Later position: keep job while validating. System interpretation: goal stable; risk strategy changed. Interpretation remains an inference until confirmed.

## Working Status

This is a working document. It should evolve through founder usage, user research, product experiments, technical validation, and legal/security review.

## Basis

Grounded in the selfie.Me Strategic Framework and Business Model Canvas, the founder's clarified direction, and the Brain 1 / Brain 2 design in `Docs/FEATURES/Building_Brain1.md` and `Building_Brain2.md`, formalized in the Architecture, Functional and Technical Design Documents (V03).
