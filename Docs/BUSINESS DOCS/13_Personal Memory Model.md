# Personal Memory Model

*Version 0.4 | Company Document 13*

Define the durable memory representation, and the structured profile built on top of it.

## Memory Object

`memory_id`, `user_id`, `source_id`, original timestamp, captured text/transcript, summary, topics, people, places, event time, tags, embedding, provenance, confidence, sensitivity, permissions.

## Memory Types

Fact, preference, goal, relationship, event, routine, constraint, project context, user instruction — plus **learned strategy** (what has worked for this person).

## Provenance

Every derived memory remains linked to the original source so the user can inspect what was actually said.

## Temporal Model

Store both capture time and event time because users often describe older events later.

## Conversation memory — three levels

- **Working:** the last ~10 turns, verbatim.
- **Episodic:** one summary per conversation — what happened, how they felt, their own quotes, commitments, open threads.
- **Semantic:** the Brain 1 Profile.

## The Brain 1 Profile

A structured, evidence-backed model of the whole person, maintained by Brain 1's core agents: Identity · People · Inner world · Body & health · Life map & places · Tastes & rituals · Goals & journeys · Story & memory · What works · Communication · Boundaries & consent · Open questions — plus a live Here & Now section (weather, time, schedule) that is never stored long-term.

Every field records its value, source, evidence, confidence, status (hypothesis / confirmed / superseded), sensitivity and owner. Nothing is overwritten: every change creates a new profile version, and that history is the person's growth record — and, one day, their legacy.

## Working Status

This is a working document. It should evolve through founder usage, user research, product experiments, technical validation, and legal/security review.

## Basis

Grounded in the selfie.Me Strategic Framework and Business Model Canvas, the founder's clarified direction, and the Brain 1 / Brain 2 design in `Docs/FEATURES/Building_Brain1.md` and `Docs/FEATURES/Building_Brain2.md`, formalized in the Architecture, Functional and Technical Design Documents (V03).
