# Data Model and ERD Specification

*Version 0.3 | Company Document 20*

Define the initial logical entities.

## Core Entities

- User
- SourceCapture
- Memory
- MemoryChunk
- Topic
- Person
- Relationship
- Event
- Belief
- BeliefVersion
- BeliefChange
- Goal
- Decision
- DecisionOutcome
- Lesson
- Conversation
- AgentRun
- Inference
- UserFeedback
- Permission
- AuditEvent
- **ProfileEntry:** domain, version, content, source memory/belief ids, benchmark reference, status (proposed/accepted/superseded/rejected)
- **Brain1ProfileVersion (V03):** the structured 12-section profile as JSON, one row per version
- **Brain1Outcome (V03):** how the user responded to a reply (persona and principles used, outcome)
- **Brain1OpenQuestion (V03):** what Brain 1 still wants to learn, with priority and status
- **Brain1Run (V03):** trace of one turn (cores, tools, Context Pack, persona, plan, checks)

## Key Relationships

SourceCapture produces Memories; Memories support BeliefVersions and Decisions; Decisions link Goals and Outcomes; AgentRuns create Inferences; UserFeedback confirms/rejects Inferences; all derived objects retain provenance. Memories and Beliefs also support ProfileEntry proposals; an accepted ProfileEntry supersedes the previous accepted entry for that domain, never deleting it.

## Working Status

This is a working document. It should evolve through founder usage, user research, product experiments, technical validation, and legal/security review.

## Basis

Grounded in the selfie.Me Strategic Framework and Business Model Canvas, the founder's clarified direction, and the Brain 1 / Brain 2 design in `Docs/FEATURES/Building_Brain1.md` and `Building_Brain2.md`, formalized in the Architecture, Functional and Technical Design Documents (V03).
