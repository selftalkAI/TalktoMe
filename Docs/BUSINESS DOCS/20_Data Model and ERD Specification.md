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

## Key Relationships

SourceCapture produces Memories; Memories support BeliefVersions and Decisions; Decisions link Goals and Outcomes; AgentRuns create Inferences; UserFeedback confirms/rejects Inferences; all derived objects retain provenance. Memories and Beliefs also support ProfileEntry proposals; an accepted ProfileEntry supersedes the previous accepted entry for that domain, never deleting it.

## Working Status

This is a working document. It should evolve through founder usage, user research, product experiments, technical validation, and legal/security review.

## Basis

Grounded in the selfie.Me Strategic Framework and Business Model Canvas, the founder's clarified direction, and the Two Brains / Profile implementation plan formalized in the Architecture, Functional and Technical Design Documents (V02).
