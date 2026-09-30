# AI Safety and Grounding Principles

*Version 0.3 | Company Document 16*

Define trustworthy AI behavior.

## Information States

- **Observed:** directly stated by user.
- **Derived:** directly extracted from source.
- **Inferred:** AI interpretation.
- **Confirmed:** user accepted inference.
- **Rejected:** user rejected inference.

## Grounding Rules

- Cite source memories for important claims.
- Expose uncertainty.
- Do not fabricate motives.
- Do not convert repeated inference into fact.
- Respect deletion across derived artifacts.
- An outside-knowledge lookup used to compare a Profile entry discloses only the minimum content needed for that comparison — never the user's full memory or Profile context.

## Agent Safety

Autonomy is limited by permissions, reversibility, auditability and user control. A Profile refinement proposal is disclosed, never written, until the user accepts it — this holds whether the proposal was triggered by the user or by a recurring automatic check (the Scheduler).

## Working Status

This is a working document. It should evolve through founder usage, user research, product experiments, technical validation, and legal/security review.

## Basis

Grounded in the selfie.Me Strategic Framework and Business Model Canvas, the founder's clarified direction, and the Two Brains / Profile implementation plan formalized in the Architecture, Functional and Technical Design Documents (V02).
