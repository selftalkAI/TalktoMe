# Product Requirements Document — V1

*Version 0.3 | Company Document 08*

Specify the first usable product.

## Objective

Build a private daily-use product for User #1 that captures thoughts, detects how opinions, goals and decisions evolve, and refines at least one Profile domain end to end.

## Must Have

- Voice and text capture.
- Original-source preservation with timestamp.
- Automatic memory extraction.
- Topic/entity linking.
- Belief/opinion version history.
- Semantic search.
- Evolution detection.
- Evidence-backed reflection.
- User confirmation/correction.
- Export and deletion.
- Agent activity log.
- Profile for at least one domain across the user's complete human persona (e.g. a skill, an emotion, a relationship, a habit, a learning area), with propose/accept/refine/reject controls and periodic re-evaluation against updated outside knowledge.

## Key User Stories

- As a user, I can ask what I thought about a topic six months ago.
- I can see a timeline of how an opinion changed.
- I can see what evidence caused the system to infer a change.
- I can correct a wrong inference.
- Before a decision, I can ask for similar past decisions and outcomes.
- As a user, I can share input about a skill or habit and see a proposed improvement — sourced from my own reflection and an outside benchmark — which I can accept, refine, or reject.

## V1 Exclusions

- Public social network.
- Autonomous impersonation.
- Posthumous access, or any access to a user's Profile by a person other than the account owner, at any time — not a temporary omission, but a dependency on a consent/legal framework that does not exist yet (`27_Consent and AI Identity Policy`).
- Training a foundation model from scratch.
- Unbounded autonomous actions.

## Success Criteria

- Daily capture is frictionless.
- Evolution insights are evidence-backed.
- Users can distinguish fact from inference.
- Corrections improve future behavior.
- At least one Profile refinement is proposed, understood, and either accepted or rejected by the user with no ambiguity about what changed.
- At least one accepted refinement is followed by real, noticed follow-through (a nudge, reminder, or check-in) — not just a silent update to stored data.

## Working Status

This is a working document. It should evolve through founder usage, user research, product experiments, technical validation, and legal/security review.

## Basis

Grounded in the selfie.Me Strategic Framework and Business Model Canvas, the founder's clarified direction, and the Two Brains / Profile implementation plan formalized in the Architecture, Functional and Technical Design Documents (V02).
