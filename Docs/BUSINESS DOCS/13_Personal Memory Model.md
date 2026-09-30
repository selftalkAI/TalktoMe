# Personal Memory Model

*Version 0.3 | Company Document 13*

Define the durable memory representation.

## Memory Object

`memory_id`, `user_id`, `source_id`, original timestamp, captured text/transcript, summary, topics, people, places, event time, tags, embedding, provenance, confidence, sensitivity, permissions.

## Memory Types

Experience, observation, story, fact, preference, belief, goal, decision, lesson, question, relationship event.

## Provenance

Every derived memory remains linked to the original source so the user can inspect what was actually said.

## Temporal Model

Store both capture time and event time because users often describe older events later.

## Profile Layer

A memory only becomes part of a Profile once the user's own reflection is layered onto it — a raw fact or an unreflected-on article is memory, but not yet Profile-worthy. The Profile sits above Memory: a synthesized, versioned entry per domain of the complete human persona (skill, emotion, relationships, career, learning, habits — extensible, never a fixed list), built from active memories and beliefs in that domain. Like a memory, a Profile entry is never overwritten — an accepted refinement supersedes the prior version, which remains in history — and it additionally carries a reference to the outside-knowledge source it was compared against.

## Working Status

This is a working document. It should evolve through founder usage, user research, product experiments, technical validation, and legal/security review.

## Basis

Grounded in the selfie.Me Strategic Framework and Business Model Canvas, the founder's clarified direction, and the Two Brains / Profile implementation plan formalized in the Architecture, Functional and Technical Design Documents (V02).
