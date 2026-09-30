# AI Product Specification

*Version 0.3 | Company Document 11*

Define what intelligence Brain 2 is responsible for.

## AI Responsibilities

- Understand new captures.
- Extract structured personal information.
- Retrieve related history.
- Detect change over time.
- Generate hypotheses about causes.
- Ask for confirmation when uncertain — including asking a clarifying question when new input doesn't yet carry the user's own reflection, before treating it as Profile-worthy.
- Compare Profile-relevant input against an outside-knowledge source before proposing a refinement.
- Synthesize memories and beliefs across domains into one coherent Profile per domain, rather than leaving them as disconnected records.
- Prepare reflections, decision context, and Profile refinement proposals.
- Follow through after an accepted refinement — a nudge, reminder, or check-in — so the change actually takes hold, not just a data update.

## Output Contract

Every important AI conclusion should expose: conclusion, evidence, source dates, confidence, and whether it is observed/derived/inferred/confirmed. A Profile refinement proposal must additionally expose what it was compared against — the outside-knowledge source and reference.

## Failure Behavior

When evidence is weak or contradictory, the AI should say it is uncertain rather than manufacture a coherent story.

## Learning Loop

User corrections and Profile accept/refine/reject decisions become labeled feedback for retrieval, classification, ranking and future proprietary models.

## Working Status

This is a working document. It should evolve through founder usage, user research, product experiments, technical validation, and legal/security review.

## Basis

Grounded in the selfie.Me Strategic Framework and Business Model Canvas, the founder's clarified direction, and the Two Brains / Profile implementation plan formalized in the Architecture, Functional and Technical Design Documents (V02).
