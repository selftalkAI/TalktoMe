# selfie.Me — Architecture Design Document (ADD)

**Version:** V01 — Refined baseline (supersedes the original v0.1 draft)
**Status:** Approved working baseline for founder pilot engineering
**Owners:** CEO/Founder (accountable), Head of Engineering (architecture), Head of Security/DPO (privacy & security sections)

## Document control

| Field | Value |
| --- | --- |
| Document | Architecture Design Document (Part III of the selfie.Me documentation pack) |
| Companion documents | Functional Specification Document (FSD), Technical Design Document (TDD) |
| Cross-reference format | `FSD §x.y`, `TDD §x.y`, `ADD §x.y` — each document numbers its own sections independently to avoid collisions |
| Review cadence | Re-approved at the start of every MVP phase (see §20) and after any change to a trust boundary, canonical data owner, or ADR |

### Changelog since v0.1

- Fixed a structural defect: v0.1 spliced an "interpretation guide" section (numbered 50) between §23 and §24 with no narrative reason. All interpretation/rationale material now lives at the end of the document (§32–§33).
- Fixed a cross-document numbering collision: v0.1 used overlapping section numbers across the FSD, TDD and ADD (e.g., both the FSD and TDD had a "§9"). Each document now numbers independently; cross-references are always qualified with the document prefix.
- Resolved a real inconsistency: v0.1 listed Redis as "ephemeral state" for both rate limiting *and* agent/workflow state, while a later section required durable, resumable agent state. §11 and §16 now make explicit that Redis is disposable coordination infrastructure only — the durable agent state machine lives exclusively in PostgreSQL.
- Added §7 (Data Classification and Encryption Posture): v0.1 called the product "privacy-first" without ever addressing whether the server can read user content in plaintext. This is now an explicit, resolved architectural decision (ADR-011) with a stated future upgrade path.
- Added a STRIDE-based threat model (§12.1), concrete capacity math with worked numbers (§17), a cost/unit-economics model (§31), a compliance and certification roadmap (§30), an incident severity matrix and launch-readiness gate (§29), and a RACI ownership table (§25.1).
- Converted every previously malformed table (broken pipe/markdown artifacts from the source document pack) into valid tables.
- Converted the "Open Questions" section into founder decisions with recorded rationale (§22) — a small number of items remain genuinely open and are marked as such.

---

## 1. Purpose and reading guide

This document explains how selfie.Me is shaped and why its boundaries exist. It is not a promise that every logical component becomes a separate deployable service — it is a contract about responsibility, authority, data ownership, and trust boundaries that must hold regardless of physical deployment shape.

Read it alongside `FSD` (what the product does) and `TDD` (how it is implemented). A change to a trust boundary, a canonical data owner, or a lifecycle guarantee in any one document requires an update to the other two (see `TDD §36`).

## 2. Architecture drivers

An architecture driver is a product goal, risk, constraint, or quality expectation that shapes structure even as implementation details change. selfie.Me stores personal context, forms uncertain inferences, supports decisions, and may act through external services — so the architecture must balance usefulness against privacy, safety, user control, and recoverability.

| Driver | Architectural consequence |
| --- | --- |
| Long-term personalization | Dedicated memory/belief/retrieval layers rather than raw chat replay. |
| User trust and control | Provenance, correction, deletion, consent and audit are first-class, not admin afterthoughts. |
| Agentic execution | Durable workflow state, fine-grained authorization, and approval boundaries. |
| LLM uncertainty | Structured outputs, grounding, a deterministic policy layer, and provider abstraction. |
| Privacy (see §7) | Data minimization, encrypted stores, scoped credentials, and controlled context assembly — with an explicit, documented answer to "who can read plaintext, and when." |
| Evolution | Modular services and versioned contracts so models, retrieval, and tools change independently. |
| MVP speed | Modular monolith or small service set; preserve logical boundaries before physical separation. |
| Unit economics | Model inference is the dominant variable cost; the architecture must make cost observable per user and per feature from day one (§31). |

### 2.1 Priority order for irreversible or externally visible decisions

When drivers conflict, resolve in this order:

1. User safety, authorization, privacy, and deletion rights.
2. Correctness, provenance, and recoverability.
3. Reliability and observability.
4. Performance and user experience.
5. Cost and implementation speed.

Speed or cost must never be purchased by expanding model authority, retaining deleted data in active retrieval, or making an external change without a clear authorization decision. This is a non-negotiable operating principle, not a guideline to be traded away under launch pressure.

### 2.2 Driver-to-quality scenarios

| Driver | Example scenario | Evidence of success |
| --- | --- | --- |
| Long-term personalization | A user corrects an old preference. | Future retrieval uses the correction and excludes the superseded value within one write cycle. |
| User trust/control | A user asks why a response used a memory. | The system shows a provenance reference and status inline, not only in an admin tool. |
| Agentic execution | A worker restarts mid-connector-operation. | The run resumes or reconciles without duplicating a consequential action. |
| LLM uncertainty | A file contains instructions to export private data. | The file is treated as untrusted content and cannot grant export authority. |
| Privacy | A connector grant is revoked while work is queued. | The queued operation is blocked and the credential invalidated within one polling interval (target: ≤60s). |
| Evolution | The embedding provider is replaced. | Canonical memories remain intact; the index rebuild completes without user-visible downtime. |
| MVP speed | A new feature is piloted with a small cohort. | A feature flag enables staged rollout without bypassing core policy checks. |
| Unit economics | Model spend grows faster than user count. | Per-user cost dashboards (§31) catch the divergence within one billing cycle, before it becomes a board-level surprise. |

### 2.3 Decision rule

For each significant architecture decision, record which drivers it supports, what trade-off it introduces, what failure mode it prevents, and how it will be validated (see the ADR format in §15). A driver only matters if it changes behavior that can be reviewed, tested, or measured.

## 3. System context

The end user interacts with selfie.Me through a client application. selfie.Me authenticates the user, stores user-controlled data, calls one or more model providers through a model gateway, optionally accesses third-party services through connectors, and stores files in object storage. External services are outside the trust boundary and receive only the minimum data required for an authorized operation.

```
User → Client → selfie.Me API/Orchestrator → {Memory & Belief, Decision,
Agent Runtime, Policy/Consent, Files} → Model Gateway / Connectors →
External AI & Third-Party Services
```

## 4. Logical architecture

| Plane | Components | Purpose |
| --- | --- | --- |
| Experience | Web/mobile clients, streaming gateway | User interaction and presentation. |
| Intelligence | Orchestrator, model gateway, prompt registry, evaluators | Reasoning and model mediation. |
| Personal context | Memory service, belief service, retrieval/index | Durable personalized understanding. |
| Decision | Decision service, evidence snapshotting | Structured decision support. |
| Action | Agent runtime, tool registry, connector adapters | Authorized external execution. |
| Governance | Identity, authorization, consent, policy, audit | Trust, privacy, and control. |
| Data | PostgreSQL, vector index, object store, cache, event/queue | Persistence and asynchronous processing. |
| Operations | Telemetry, feature flags, configuration, CI/CD | Reliability and safe evolution. |

Planes are conceptual boundaries that clarify dependency and authority even when the initial implementation runs in one process (`TDD §37.2`).

## 5. Recommended physical evolution

### 5.1 MVP: modular monolith + workers

One primary application with strong internal module boundaries (conversation/orchestration, memory, beliefs, decisions, policy, APIs), plus separate asynchronous workers for embeddings, ingestion, deletion, and agent tasks. PostgreSQL/pgvector, Redis, and object storage are shared infrastructure. This minimizes operational complexity while preserving clean interfaces for later extraction.

### 5.2 Scale-out triggers

| Trigger condition | Extraction target |
| --- | --- |
| Long-running agent jobs materially affect API reliability (e.g., p99 API latency regresses when agent worker queue backs up) | Separate Agent Runtime |
| Multiple products/providers need independent scaling and governance for model calls | Separate Model Gateway |
| Index size, retrieval QPS, or specialized storage needs exceed pgvector's practical envelope (see §17.2) | Separate Memory/Retrieval service, then dedicated vector database |
| Credential/security boundary or provider count grows past what one service can review safely | Separate Connector Service |
| Retries, timers, approvals, and compensations become operationally complex to hand-roll | Adopt a dedicated workflow engine (e.g., Temporal-class) |

Extraction without a measurable trigger adds network failure modes and operational cost without improving the privacy or reliability boundary it claims to protect (`ADR-001`).

## 6. Personal context architecture

Four distinct layers, each with different retention, correction, visibility, and authorization rules:

| Layer | Mutable? | Primary truth? | Example |
| --- | --- | --- | --- |
| Evidence | Append/retention governed | Yes, as source record | A user message or uploaded document reference. |
| Memory | Correctable/supersedable | Canonical personal context | "User explicitly prefers concise emails." |
| Belief | Continuously revisable | No — inference | "User may prefer concise professional communication generally." |
| Retrieval view | Ephemeral, task-scoped | No | "Three relevant preferences selected for drafting an email." |

This separation prevents a generated interpretation from being mistaken for user truth. Evidence answers "where did this come from?"; memory answers "what durable statement may be reused?"; belief answers "what tentative pattern does the system currently infer?"; a retrieval view answers "what small, purpose-specific subset may this request see?" (rationale in §32.1).

## 7. Data classification and encryption posture

This section did not exist in v0.1 and is the most important addition in this revision. A product that markets itself as "privacy-first" must have an explicit, defensible answer to: **who can read a user's memory content, under what conditions, and why.** WhatsApp's entire brand rests on being able to say "not even we can read your messages." selfie.Me cannot make that claim today, and pretending otherwise would be a governance failure the first time a regulator, security researcher, or enterprise customer asks the question directly. This section states the real posture and the roadmap to a stronger one.

### 7.1 Data classification tiers

| Tier | Examples | Encryption requirement | Access requirement |
| --- | --- | --- | --- |
| T0 — Public | Marketing content, public docs | TLS in transit only | None |
| T1 — Internal | Aggregated, de-identified metrics | Encrypted at rest (managed) | Employee auth |
| T2 — Confidential (default for personal data) | Conversations, memories, beliefs, decisions, files | Encrypted at rest (managed) + envelope-encrypted at the application layer per user (§7.2) | Owning user, or break-glass with audit (§12.2) |
| T3 — Restricted (sensitive categories) | Health, financial account detail, government ID, sexual orientation, immigration status, legal matters | Field-level envelope encryption with per-category keys; excluded from default retrieval and default model context | Owning user only; explicit per-category opt-in required before write (`FSD FR-PRV-001`, `FR-MEM-009`); never included in embeddings without separate consent |
| Never stored | Passwords, full payment card numbers, government-issued secret credentials, connector refresh tokens as plaintext | N/A — hard block at the write gate, not a consent question | N/A |

### 7.2 Current posture (MVP): server-side application encryption

For the founder pilot, selfie.Me uses **envelope encryption at the application layer**, not end-to-end encryption:

- Every T2/T3 record is encrypted with a per-user data encryption key (DEK); DEKs are wrapped by a KMS-managed key encryption key (KEK).
- The application (not the client) holds the ability to decrypt, because retrieval, embedding generation, and LLM context assembly require plaintext server-side.
- This means selfie.Me employees with sufficient privilege *can* technically access plaintext through break-glass procedures (§12.2) — this must be stated to users plainly in the privacy notice, not obscured behind the word "encrypted."
- T3 categories get a separate DEK per category so that a T3 breach or a single compromised key does not expose T2 data and vice versa.

### 7.3 Why not end-to-end encryption on day one

True E2E (client-holds-only-key) would prevent the AI pipeline from doing anything server-side: no server-side embedding generation, no server-side retrieval ranking, no server-side memory extraction. Every current LLM-based feature requires the server (or a provider it calls) to see plaintext at inference time. Claiming E2E while running server-side LLM inference would be a **misrepresentation**, and this document explicitly rejects making that claim until the technical approach changes.

### 7.4 Roadmap (post-MVP, tracked as ADR-011)

| Phase | Approach | What it buys |
| --- | --- | --- |
| Now (MVP) | Server-side envelope encryption, strict access control, break-glass audit | Protects against external breach and unauthorized internal access; does not protect against a compelled disclosure or insider with break-glass rights. |
| Phase 2 | On-device embedding generation for retrieval (client computes vectors from a local small model before any server call for T3 content) | Server never sees T3 plaintext for retrieval purposes; still sees it if the user asks the assistant to reason over it. |
| Phase 3 (research) | Confidential computing (trusted execution environments) for the model-gateway inference path, or client-side key management with server processing inside an attested enclave | Approaches an E2E-equivalent guarantee for a subset of workloads without abandoning server-side AI. |

The product marketing and the privacy notice must track whichever phase is actually shipped — this document is the source of truth for what claim is currently true.

## 8. Agentic AI architecture

The agent system is split into Planner, Policy Gate, Executor, and Observer. The Planner proposes steps but has no authority to execute. The Policy Gate deterministically checks identity, scopes, risk, and approval. The Executor invokes tools using scoped credentials. The Observer persists state and interprets tool results for the next step. This separation limits the damage of model mistakes or prompt injection.

The Agentic Service implements this loop as a LangGraph `StateGraph`: Planner and Executor/Policy Gate are graph nodes, and each `AgentRun` is its own graph thread (keyed by `run_id`) held in a checkpointer. A step requiring approval pauses the graph with LangGraph's `interrupt()` rather than the service hand-rolling a wait state; `POST /v1/agents/runs/{id}/approve` resumes that exact thread. This is an implementation detail of the Agentic Service, not a change to the roles, the policy in ADR-007, or the state machine in `TDD §8`.

### 8.1 Agent sequence

1. Request enters the Orchestrator with authenticated user context.
2. Planner creates a structured plan.
3. Policy Gate evaluates every planned operation.
4. Low-risk authorized reads execute; approval-required steps pause.
5. User approves the exact operation and data scope.
6. Executor obtains a scoped credential and calls the connector.
7. Result is sanitized and persisted.
8. Planner/Observer determines whether the next step is still valid.
9. Run completes with an audit summary.

## 9. Trust boundaries

| Boundary | Trust assumption | Required controls |
| --- | --- | --- |
| Client ↔ API | Client is untrusted. | Authentication, CSRF/session controls, input validation, rate limiting (default: 60 req/min/user on chat endpoints, 10 req/min/user on mutation endpoints — see `TDD §17.1`). |
| API ↔ Internal services | Authenticated service identity, least privilege. | mTLS/service identity or equivalent, authorization, network policy. |
| Application ↔ Data stores | Stores contain private data. | Encryption, private networking, scoped DB roles, backups. |
| Orchestrator ↔ LLM provider | Provider is an external processing boundary. | Minimum data, routing policy, zero-retention/no-training contract terms (§30.2), no secrets in prompts. |
| Agent ↔ Connector | Third-party API is untrusted/external. | Scoped OAuth, schema validation, approvals, idempotency. |
| Files/tool output ↔ Model | Content may contain adversarial instructions. | Content/instruction separation, sanitization, tool policy. |

## 10. Data architecture

PostgreSQL is the system of record for identities, memory metadata/content, beliefs, decisions, consent, and agent state. Vector representations are derivative indexes rebuildable from authorized source records. Object storage holds files and exports. Redis is non-authoritative ephemeral state (§11 clarifies what "ephemeral" excludes). Events/queues connect write paths to asynchronous enrichment and lifecycle workflows.

### 10.1 Data ownership rules

- Each domain owns writes to its canonical tables even when deployed in one database initially.
- Derivative stores never become the sole copy of user data.
- Every user-scoped record includes an immutable owner/tenant key.
- Foreign keys or equivalent application invariants maintain referential integrity.
- Sensitive connector secrets are referenced from a secrets system, never stored as ordinary application columns.
- Embeddings inherit the privacy/deletion classification of their source memory/chunk.

## 11. Availability and resilience architecture

- Stateless request handlers scale horizontally.
- Streaming responses degrade gracefully if secondary enrichment is unavailable.
- Memory writes may be asynchronous after the user response; explicit memory-management operations (create/correct/delete) are synchronous for user-visible state.
- **Agent runs persist after every meaningful transition in PostgreSQL and can resume after worker restart. Redis is used only for short-lived coordination — rate-limit counters, distributed locks, and cache — and is never the sole holder of a fact needed to resume a workflow.** This corrects an internal inconsistency in v0.1, where Redis was described simultaneously as disposable cache and as agent-state storage.
- Queues use dead-letter handling and replay-safe consumers.
- Model gateway supports provider/model fallback only for compatible, privacy-compatible tasks and records the substitution.
- Backups are encrypted and restore procedures are tested quarterly at minimum.
- Deletion tombstones prevent re-indexing deleted content from delayed events.

## 12. Security architecture

Authorization is evaluated at resource and operation level; authentication alone never grants access to a memory or connector. Service identities receive only required database, queue, and secret permissions. High-value administrative operations require stronger controls and are audited. Production support access uses break-glass mechanisms with an explicit reason, dual approval for T3 data, and mandatory notification to the affected user in their audit/activity log (transparency principle, not just an internal control).

### 12.1 Threat model (STRIDE)

| Threat category | Example in selfie.Me | Mitigation |
| --- | --- | --- |
| Spoofing | Attacker reuses a stolen session token to impersonate a user. | Short-lived tokens, refresh rotation, device/session list with revocation (`FSD FR-ID-003`), anomaly-based step-up auth. |
| Tampering | A compromised client sends a manipulated tool-call approval. | Server re-validates the exact operation server-side; approval binds to a signed, exact-match operation descriptor, not a free-form confirmation. |
| Repudiation | A user disputes that they approved a consequential agent action. | Immutable audit event with principal, operation, timestamp, and the exact approved payload hash. |
| Information disclosure | Vector similarity search returns another user's memory due to a missing scope filter. | Ownership/status filter applied *before* similarity ranking, never after (`TDD §35.3`); automated cross-user retrieval test in CI (`FSD §8` acceptance criteria). |
| Denial of service | Abusive client floods the chat endpoint or triggers expensive embedding regeneration. | Rate limiting, per-user token budgets, circuit breakers on the model gateway, queue backpressure. |
| Elevation of privilege | A prompt-injected instruction inside a file asks the agent to call an unauthorized connector operation. | Untrusted content is data, never instruction; Policy Gate re-authorizes every step independent of model output (`ADR-007`). |

### 12.2 Break-glass access

Break-glass access to T2/T3 plaintext requires: a logged reason code, time-bound elevation (default 4 hours, auto-expiring), dual approval for T3, and an entry in the user's own audit/activity view stating that support accessed their data, when, and why. Routine plaintext browsing is never permitted; this is enforced technically (access requests are logged and rate-limited at the authorization layer), not only by policy.

### 12.3 Encryption

- TLS 1.2+ (moving to TLS 1.3 as the default) for all network paths.
- Managed encryption at rest for databases, object storage, queues, and backups.
- Envelope encryption/KMS for T2/T3 application data (§7.2) and especially sensitive application secrets.
- Connector tokens encrypted separately, with rotation/revocation according to each provider's capabilities.
- Key access is separated from ordinary application administration (a database admin cannot also mint decryption grants).

## 13. Privacy architecture

Privacy controls operate before storage, before retrieval, and before disclosure:

- **Write gate** — may this information become durable at all?
- **Retrieval gate** — may this stored item be used in this particular context?
- **Disclosure gate** — may this selected information be sent to a model or third-party tool?

This three-gate model prevents "stored therefore usable everywhere" behavior: information can be stored but excluded from a particular model call, retrieved internally but withheld from a connector, or logically deleted from active use while physical cleanup completes.

## 14. AI safety and grounding architecture

| Risk | Architectural mitigation |
| --- | --- |
| Hallucinated personal fact | Only governed memory/evidence is injected as personal truth; inferred beliefs are labeled as such in the prompt and the UI. |
| Stale memory | Temporal validity, last-confirmed timestamps, recency-aware retrieval. |
| Contradiction | Conflict state and evidence preservation; current explicit instruction wins for the immediate task. |
| Over-personalization | Relevance threshold and bounded context; unrelated memories are never injected merely because they exist. |
| Prompt injection | External text cannot grant tool permissions; planner output is checked by deterministic policy regardless of what the model "believes" it is authorized to do. |
| Unsafe autonomous action | Risk classes, approvals, scoped credentials, cancellation, and audit (§8). |
| Opaque decision advice | Evidence/assumption/preference separation and decision snapshots (`FSD §4.5`). |
| Model drift | Versioned model/prompt registry plus recurring evaluation suites (§19). |
| Self-harm or crisis disclosure | Content classifier flags high-risk disclosures; the assistant responds with a documented, reviewed safety script and surfaces crisis resources rather than attempting open-ended personalized advice — this path bypasses ordinary memory-write eligibility entirely and is excluded from durable memory unless the user explicitly asks it to be retained. |

## 15. Architecture Decision Records

Each ADR states context, decision, and consequences so a future team can tell whether the original reasoning still holds.

| ADR | Decision | Reason | Consequence / what would change this |
| --- | --- | --- | --- |
| ADR-001 | Modular monolith for the founder pilot. | Maximizes delivery speed while preserving domain boundaries. | Revisit when a scale-out trigger in §5.2 fires. |
| ADR-002 | PostgreSQL as the canonical data store. | Transactional integrity and broad operational maturity. | Revisit only under a proven multi-region write-latency requirement no single-primary Postgres topology can meet. |
| ADR-003 | pgvector initially, not a dedicated vector database. | Avoids premature infrastructure; concrete capacity math in §17.2 shows it is sufficient at pilot scale. | Revisit when index size or QPS crosses the thresholds in §17.2. |
| ADR-004 | Separate memories from beliefs. | Prevents inference from masquerading as user truth. | Foundational; not expected to change. |
| ADR-005 | Treat embeddings as derivative data. | Supports deletion, rebuild, and model migration. | Foundational; not expected to change. |
| ADR-006 | All model calls go through an internal gateway. | Provider portability, policy enforcement, observability, cost tracking. | Foundational; not expected to change. |
| ADR-007 | Deterministic policy checks around agent actions; the model proposes, never authorizes. | LLMs cannot be trusted as an authorization system. | Foundational; not expected to change. |
| ADR-008 | Agent state persisted as a durable state machine in PostgreSQL, never in Redis. | Supports retries, approvals, and recovery; fixes the v0.1 inconsistency. | Foundational; not expected to change. |
| ADR-009 | Durable personal context requires provenance. | Enables correction, conflict handling, and trust. | Foundational; not expected to change. |
| ADR-010 | Three privacy gates: write, retrieval, disclosure. | Storage consent alone is insufficient for contextual use and external sharing. | Foundational; not expected to change. |
| ADR-011 (new) | MVP uses server-side application encryption, not end-to-end encryption; on-device/confidential-compute path is a tracked roadmap item (§7.4). | Current LLM pipeline requires server-side plaintext; pretending otherwise is a governance and legal risk. | Revisit as soon as on-device embedding generation for T3 categories is feasible — this changes the privacy notice's claims, so legal/DPO sign-off is required before the marketing claim changes. |
| ADR-012 (new) | Model providers must contractually agree to zero data retention / no training on request or response content. | Personal memory data must never become training data for a third party's foundation model. | If no provider offers acceptable terms at required latency/cost, escalate to CEO/board before shipping with a provider that does not meet this bar. |

## 16. Deployment topology

Initial production topology: CDN/WAF → web client/API ingress → application instances → PostgreSQL/pgvector + Redis + object storage; asynchronous queue → worker pool; application/worker → model gateway → external model providers; agent executor → connector adapters → third-party APIs. Observability receives redacted telemetry from every internal component. Secrets/KMS is reachable only by workloads requiring credentials.

## 17. Capacity and scalability assumptions

### 17.1 Planning table

| Area | MVP assumption | Scale strategy |
| --- | --- | --- |
| Users | Founder pilot to low tens of thousands (target: 10,000 by end of pilot) | Horizontal API/workers; connection pooling (PgBouncer, transaction mode). |
| Memories/user | Hundreds to low thousands (planning figure: 1,500/user at maturity) | Hybrid indexed retrieval; partition/index tuning. |
| Conversations | Potentially high append volume | Partition messages by time/user when needed; archive cold data after 24 months (§17.3). |
| Agent runs | Low relative to chat traffic (planning figure: <5% of active users run an agent task weekly) | Independent worker pools and concurrency limits. |
| Files | Moderate; bounded upload sizes (50 MB default cap) | Direct-to-object-storage upload, async parsing. |
| Model calls | Dominant variable cost (see §31) | Caching where safe, routing by task complexity, token budgets. |

These figures are planning assumptions, not requirements from the source documentation pack. They must be replaced with measured founder-pilot telemetry before any production capacity commitment.

### 17.2 Worked capacity math: does pgvector hold at pilot scale?

Assume 10,000 users × 1,500 memories/user = 15,000,000 vectors. At a 1,536-dimension embedding stored as float32 (4 bytes/dimension): 1,536 × 4 bytes = 6,144 bytes/vector, so raw vector data ≈ 15,000,000 × 6,144 bytes ≈ **92 GB**. An HNSW index over that volume typically adds 1.5–2× overhead, putting total index size in the **140–185 GB** range — well within a single well-provisioned PostgreSQL instance (managed offerings commonly support multi-TB volumes), and query latency for HNSW at this scale is expected to stay in the low tens of milliseconds for top-k retrieval. **Conclusion: pgvector is sufficient through the entire founder-pilot target; the scale-out trigger in §5.2 (dedicated vector database) is not expected to fire during MVP.** Re-run this calculation before every 10x growth in either user count or memories/user.

### 17.3 Retention-driven storage growth

Conversation content is retained 24 months on a rolling basis, then archived to cold object storage and removed from the hot transactional path (`FSD §7`, retention decision in §22). This bounds the growth of the primary conversation table independent of user growth and keeps backup/restore windows predictable.

## 18. Failure modes and recovery

| Failure | Expected behavior |
| --- | --- |
| LLM timeout | Retry a compatible transient call once, or route to fallback; preserve user request state. |
| Vector index unavailable | Fall back to structured/lexical retrieval, or continue without memory with clear internal telemetry — never fail the whole request. |
| Database unavailable | Fail safely; never execute external writes when state cannot be durably recorded. |
| Connector timeout | Bounded retry for safe operations; reconcile uncertain writes via the provider's operation ID before retrying. |
| Worker crash | Resume from persisted agent/workflow state. |
| Duplicate event | Consumer idempotency prevents duplicate memory/action. |
| Partial account deletion | Retry from the deletion ledger until every applicable store reports completion. |
| Stale authorization | Re-check permissions immediately before any external action, never rely on a permission check performed earlier in the request. |

## 19. Evaluation framework

| Dimension | Example metric | MVP target |
| --- | --- | --- |
| Memory precision | % of stored memories judged durable/relevant and correctly typed | ≥ 90% on sampled human review |
| Memory recall | % of important explicit facts/preferences captured when policy allows | ≥ 80% on scripted eval conversations |
| Retrieval relevance | Top-k memories judged useful for the current task | ≥ 85% top-3 relevance on eval set |
| Contradiction safety | Rate at which stale/conflicting memory incorrectly overrides current user input | < 1% on adversarial eval set (target: 0, tracked as a guardrail metric) |
| Belief calibration | Confidence-band agreement with later confirmation/correction | Within 15 points of stated confidence band |
| Decision transparency | Users can identify evidence, assumptions, and preferences used | ≥ 90% in usability testing |
| Agent success | Goal completion without unauthorized or duplicate actions | ≥ 95% completion, 0 tolerated unauthorized actions |
| Approval quality | Users understand what will happen before approving | ≥ 90% comprehension in usability testing |
| Grounding | Claims attributable to provided evidence/source when grounding is required | ≥ 95% |
| Privacy correctness | No retrieval/disclosure outside configured consent/policy | 0 violations in automated tests (release-blocking if violated) |

## 20. MVP implementation plan

| Phase | Deliverables | Exit gate |
| --- | --- | --- |
| Phase 0 — Foundations | Identity, PostgreSQL schema, API conventions, model gateway, telemetry, policy skeleton, encryption posture implemented (§7.2). | Security review sign-off; §29 launch-readiness checklist items relevant to this phase pass. |
| Phase 1 — Conversation | Streaming chat, conversation persistence, prompt/version registry. | Latency NFRs met (`FSD NFR-002`) under synthetic load. |
| Phase 2 — Memory | Candidate extraction, governed write pipeline, memory UI, retrieval, correction/deletion. | Cross-user isolation test suite passes; correction-affects-future-retrieval test passes. |
| Phase 3 — Beliefs | Evidence graph, contradiction handling, user challenge/suppression. | Belief calibration eval meets §19 target. |
| Phase 4 — Decisions | Decision workspace, criteria/options, evidence snapshots, transparent analysis. | Decision transparency usability target met. |
| Phase 5 — Agent pilot | One or two connectors, planner/executor split, approval flow, durable run state. | Agent state survives an injected worker restart in staging; zero unauthorized-action incidents in eval. |
| Phase 6 — Privacy lifecycle | Export, account deletion, retention jobs, connector revocation verification. | Deletion verified across every store in the deletion ledger in a staged test account. |
| Phase 7 — Hardening | AI evaluations, security tests, load/resilience tests, incident runbooks. | Independent security review passed; on-call runbook rehearsed. |

## 21. Traceability matrix

| Product capability | Functional requirements | Technical components | Architecture plane |
| --- | --- | --- | --- |
| Conversation | `FSD FR-CONV-*` | Conversation Service, Orchestrator, Model Gateway | Experience / Intelligence |
| Personal memory | `FSD FR-MEM-*` | Memory Service, PostgreSQL, pgvector | Personal Context / Data |
| Beliefs | `FSD FR-BEL-*` | Belief Service, evidence links | Personal Context |
| Decision intelligence | `FSD FR-DEC-*` | Decision Service, retrieval, model gateway | Decision / Intelligence |
| Agentic AI | `FSD FR-AGT-*` | Agent Service, Policy Gate, Connectors | Action / Governance |
| Privacy and consent | `FSD FR-PRV-*` | Policy/Consent, deletion coordinator, secrets, KMS | Governance / Data |
| Safety and grounding | `FSD FR-SAFE-*` | Policy, Model Gateway, retrieval controls | Intelligence / Governance |
| Feedback and evaluation | `FSD FR-FBK-*` | Telemetry, evaluation pipeline | Operations |

## 22. Founder decisions on prior open questions

v0.1 left ten open questions unresolved. A founder pilot cannot proceed with all of them open — leaving them open is itself a decision (usually the wrong one, by default). The following are now decided; two remain genuinely open and are marked as such.

| Question | Decision | Rationale |
| --- | --- | --- |
| Which sensitive categories may become durable memory? | T3 categories (health, financial account detail, government ID, sexual orientation, immigration status, legal matters) require explicit per-category opt-in before any write; passwords, full card numbers, and government secret credentials are never stored, full stop — this is a hard block, not a consent question. | Matches §7.1 classification; removes ambiguity that would otherwise be resolved ad hoc by an engineer under deadline pressure. |
| Should memory be opt-in, opt-out, or per-category? | Per-category. Default ON for T2 categories (preferences, goals, routines); default OFF for T3 until explicit confirmation. | Balances usefulness (most value comes from ordinary preferences) against risk (sensitive categories carry the highest harm if mishandled). |
| Should beliefs be user-editable or only challengeable? | Challengeable/suppressible only, never directly editable. A user who wants to assert something as fact should create an explicit memory instead. | Directly editing a belief would blur the evidence/inference boundary that ADR-004 exists to protect. |
| First decision-intelligence use case? | Everyday trade-off decisions with no regulated-advice exposure (e.g., "should I take this job offer," "which apartment fits my constraints") — explicitly not medical, legal, or financial advice. | Proves the decision workspace UX and grounding model without triggering regulated-advice liability before the trust loop is proven. |
| First connector? | Read-only calendar + email digest (no write actions in the pilot). | Highest everyday value, lowest risk profile — validates the full planner/policy/executor/observer loop without a HIGH_IMPACT risk class in play. |
| Individual vs. household/shared identity? | Individual only for MVP. | Shared-context authorization is materially more complex and not required to prove the core trust loop (`FSD §8.1`). |
| Jurisdictions and data residency? | Launch in US and EU. GDPR compliance (not just residency) applies from day one regardless of hosting region; dedicated EU regional infrastructure is a post-MVP commitment once EU user volume justifies it. | GDPR obligations attach based on whose data is processed, not where the server sits — residency and compliance are separate commitments and must not be conflated. |
| Retention periods? | Conversation content: 24 months rolling, then archive. Audit/security events: 3 years. Deleted-account backups: purged within 90 days of deletion-workflow completion, bounded by backup rotation. | Matches typical security-audit retention norms while keeping deletion promises meaningful (a "deleted" account should not linger in backups indefinitely). |
| Model-provider data retention/training policy? | Contractual zero-retention, no-training terms required from any model provider before integration (ADR-012). | Personal memory data must never become another company's training data — this is a brand-defining commitment, not a negotiable procurement detail. |
| Quantitative pilot success thresholds? | ≥40% week-4 retention, ≥70% of sampled stored memories judged accurate by the owning user, 0 confirmed cross-user data leakage incidents, NPS ≥ 40. | Gives the team an unambiguous "did the pilot work" answer instead of a subjective retrospective. |

**Genuinely still open (require product research, not just a founder call):**

- Pricing model and whether any tier gates memory capacity or agent connector count — needs willingness-to-pay research before deciding.
- Whether decision-workspace outputs should ever be shareable with a third party (e.g., a partner co-deciding on an apartment) — this has real authorization-model implications and should not be decided casually.

## 23. Definition of done for documentation v1

- Founder/product owner has confirmed or edited every decision in §22.
- Functional requirements are prioritized as MVP, post-MVP, or rejected (`FSD §8.1`).
- Data classification (§7.1) and consent policy are approved by the DPO/security owner.
- First user journeys and connector use cases are selected (done in §22).
- Architecture decisions are reviewed by engineering and security (ADR table, §15).
- API/data schemas are converted into executable contracts/migrations (`TDD §12`).
- Threat model (§12.1) and AI evaluation suites (§19) are created from the requirements.
- Traceability is maintained from product requirement through implementation and test (§21).

## 24. End-to-end request flows

### 24.1 Conversational request

1. The client authenticates the request and sends a conversation message with a correlation ID and an optional idempotency key.
2. The API validates ownership of the conversation and persists the user message before beginning model work.
3. The orchestrator classifies the request and asks the policy layer which data classes, memories, tools, and model capabilities are permitted.
4. Retrieval returns a bounded context package containing source references, status, confidence, and temporal metadata.
5. The model gateway invokes a versioned prompt/model configuration and validates the structured result before it is rendered.
6. The assistant response is persisted with model, prompt, policy, and retrieval references. Candidate memory extraction is queued only after the response lifecycle is stable.
7. The client receives a streamed response and a final durable message status. A partial stream is never treated as a completed response.

### 24.2 Authorized external action

The agent planner produces a proposed plan, which is not itself an authorization. The policy gate evaluates each step against the authenticated user, connector grant, data disclosure scope, risk class, resource target, and approval state. A read-only step may run without a new prompt when covered by standing permission. A consequential write must display the exact operation and receive approval bound to that operation. If the plan changes materially after approval, the affected step returns to `WAITING_APPROVAL`.

The executor records an operation ID before calling the connector, uses the minimum scoped credential, and persists the connector result or uncertainty. If the network fails after a write may have reached the provider, the system reconciles using the provider's operation ID rather than blindly retrying.

### 24.3 Export and deletion

Export and deletion use a durable lifecycle record and a deletion or export ledger listing every canonical and derivative store — database rows, vector entries, object files, caches, queues, search indexes, and connector-derived artifacts. The privacy service marks records unavailable for retrieval before asynchronous cleanup begins. Completion requires verification from each applicable store; unverified work remains visible to operations and is retried.

## 25. Domain ownership and contracts

Logical domains own their invariants even when they share one deployed application and PostgreSQL instance:

| Domain | Owns | Publishes or consumes |
| --- | --- | --- |
| Identity and governance | Users, sessions, consent, authorization, data classification | Authentication context, policy decisions, revocation events |
| Conversation | Conversations, messages, response status | Interaction-completed events, response references |
| Personal context | Memories, evidence links, beliefs, retrieval views | Memory mutation, contradiction, and index-work events |
| Decisions | Workspaces, criteria, options, snapshots, outcomes | Decision context requests and outcome feedback |
| Agent action | Plans, steps, approvals, executions, connector results | Approval requests, action status, audit events |
| Files and ingestion | Object references, parsing status, chunks, source metadata | Ingestion completion and deletion events |
| Operations | Audit, telemetry, evaluation records, feature flags | Alerts, evaluation results, operational commands |

A domain may read another domain's published view or API but must not update another domain's canonical tables as a shortcut. This preserves the option to separate services later without rewriting business invariants.

### 25.1 Ownership RACI

| Activity | Responsible | Accountable | Consulted | Informed |
| --- | --- | --- | --- | --- |
| Architecture decisions (ADRs) | Head of Engineering | CEO/Founder | Security lead, affected domain owners | Whole engineering team |
| Data classification changes (§7.1) | Security/DPO | CEO/Founder | Legal, product | Engineering |
| New connector approval | Agent action domain owner | Head of Engineering | Security lead, legal (if writes data externally) | Product |
| Incident response (SEV1/2, §29.1) | On-call engineer | Head of Engineering | Security lead, DPO (if privacy-impacting) | CEO/Founder, affected users per breach-notification policy |
| Privacy notice claims (e.g., encryption posture, §7) | DPO/Legal | CEO/Founder | Head of Engineering, Head of Product | All users, at time of material change |

## 26. Environment topology and local development

The repository's current local topology provides PostgreSQL 16 and Redis 7 through `docker-compose.yml`. PostgreSQL is the canonical development store; Redis is suitable for cache, locks, and queued work. Neither local service is production-hardened by default.

Development, staging, and production must use separate databases, volumes, credentials, encryption keys, connector grants, and model-provider configuration. The application must fail clearly when a required secret or migration is missing rather than silently falling back to insecure defaults. Production ingress adds TLS termination, WAF/rate controls, private data-store networking, backup monitoring, and workload identity.

## 27. Architectural quality attributes

| Attribute | Scenario | Design response |
| --- | --- | --- |
| Privacy | A user revokes consent while queued enrichment is pending. | Policy checks and deletion tombstones prevent later storage or disclosure. |
| Reliability | A worker stops between a tool call and state persistence. | Idempotency key, operation reconciliation, and durable state transitions prevent unsafe duplication. |
| Evolvability | The embedding or model provider changes. | Versioned gateway contracts and rebuildable derivative indexes support migration. |
| Performance | A conversation requires retrieval and model streaming. | Bounded retrieval, parallel-safe reads, caching, and response streaming protect interactive latency. |
| Operability | A user reports an incorrect answer. | Correlation IDs connect response, context, model version, policy decision, and audit evidence without requiring raw content in ordinary logs. |
| Security | Untrusted file text instructs the agent to send data externally. | Content is evidence only; deterministic policy and connector scopes remain authoritative. |

## 28. Architectural risks and mitigations

**Premature complexity.** Physically splitting every logical component can slow the founder pilot and create more failure paths than it removes. The modular-monolith recommendation requires clear module boundaries, contract tests, ownership, and observability from the beginning to remain safe.

**Treating model output as a trusted decision.** Structured output validation improves reliability but is not authorization. Policy, consent, and resource checks must remain deterministic and outside the model.

**Incomplete lifecycle handling.** Memory correction, connector revocation, export, and deletion must be designed together with indexing, caching, queues, backups, and provider retention. A feature is not complete if its derivative data continues to influence responses after the user has disabled or deleted it.

**Overclaiming privacy.** The single biggest reputational risk for a "privacy-first" product is a gap between what the privacy notice claims and what the architecture actually does (§7). This must be reviewed every time the encryption posture or provider mix changes, not just at launch.

## 29. Incident management and launch readiness

### 29.1 Incident severity matrix

| Severity | Definition | Example | Response target |
| --- | --- | --- | --- |
| SEV1 | Confirmed cross-user data exposure, or full service outage | User A's memories returned to User B | Page on-call immediately; CEO/DPO notified within 1 hour; GDPR 72-hour breach-notification clock starts if personal data is confirmed exposed |
| SEV2 | Partial outage or a security control failure without confirmed exposure | Policy gate fails open for one connector type | Page on-call; fix or mitigate within 4 hours |
| SEV3 | Degraded experience, no security impact | Elevated latency on retrieval | Business-hours response, next business day fix |
| SEV4 | Cosmetic or low-impact bug | UI copy error | Backlog |

Every incident gets a blameless postmortem with an owner, a root cause, and at least one preventive action tracked to completion — the goal is a system that fails safely and learns, not a search for who to blame.

### 29.2 Launch readiness gate

Before any phase in §20 ships to real users, the following must be true (adapted from standard large-company launch-readiness review practice):

- [ ] Security review completed for the phase's new surface area.
- [ ] Privacy review completed if the phase touches T2/T3 data flows.
- [ ] On-call rotation and runbook exist for the new component.
- [ ] Rollback plan tested (not just documented).
- [ ] Relevant §19 evaluation targets met on a held-out eval set.
- [ ] Cost per active user for the new feature is estimated and within the §31 model's bounds.

## 30. Compliance and certification roadmap

| Requirement | MVP posture | Target for general availability |
| --- | --- | --- |
| GDPR (EU users) | Core rights (access, correction, erasure, portability) implemented per `FSD §4.7`; DPA templates ready for any sub-processor (including model providers). | Full compliance program with a named DPO, ROPA (Records of Processing Activities), and completed DPIA for the memory/belief pipeline. |
| CCPA/CPRA (California users) | Export and deletion mechanisms shared with GDPR implementation. | Formal "Do Not Sell/Share" posture documented (expected: N/A, as no data is sold — but this must be stated explicitly, not assumed). |
| SOC 2 Type II | Not started; architecture (encryption, access control, audit logging) is designed to be SOC2-compatible from day one. | Target: begin Type I readiness assessment after Phase 5 (§20), Type II observation period after GA. |
| ISO 27001 / 27701 | Not started. | Evaluate after SOC 2, driven by enterprise customer demand if the product moves beyond individual consumers. |
| Breach notification | Process defined in §29.1 (72-hour GDPR clock). | Same process, audited annually. |

### 30.2 Model provider contractual requirements (ties to ADR-012)

Every model provider integrated via the Model Gateway must contractually commit to: no training on submitted content, defined data retention period (target: zero or shortest available), region-of-processing disclosure, and a security posture (e.g., SOC 2) verifiable before integration. This is a procurement gate, not a nice-to-have.

## 31. Cost model and unit economics

A privacy-first personal AI product's dominant variable cost is model inference. This was entirely absent from v0.1 and must be tracked from the first user.

### 31.1 Rough per-user monthly cost model (planning estimate, to be replaced with measured data after Phase 1)

| Cost driver | Assumption | Estimated monthly cost/active user |
| --- | --- | --- |
| Chat completions | ~50 messages/month, ~1,500 input + 400 output tokens/message (with retrieved context) | Provider-dependent; treat as the single largest line item and instrument per-call cost from day one |
| Memory extraction | 1 extraction call per interaction, small prompt | Secondary but non-trivial at scale — batch where safe |
| Embeddings | ~5 new memories/month/user at pilot maturity | Small relative to chat completions |
| Storage (Postgres + object storage) | See §17.2 for vector storage math | Small relative to model cost at this scale |
| Infrastructure (compute, Redis, queue) | Shared, amortized across users | Decreases per-user as the user base grows |

### 31.2 Operating principle

Per-user and per-feature cost must be visible on an internal dashboard before a feature ships broadly, not discovered on a monthly cloud bill. A feature that materially changes the cost curve (e.g., allowing longer retrieved context windows, or adding a second connector) requires the same review rigor as a security change (§29.2 launch gate should include a cost checkbox for any feature expected to move token volume by more than 20%).

## 32. Architecture theory and design rationale

The architecture is organized around a separation of concerns: experience presents information, intelligence interprets requests, personal context supplies governed evidence, governance decides what is permitted, and action performs only authorized work. These are logical boundaries even when the MVP deploys them in one modular application. The separation protects trust and evolvability, not merely to create more services.

### 32.1 Why personal context has multiple layers

Evidence, memory, belief, and retrieval view have different authority and lifecycles. Combining these layers would make correction, contradiction, deletion, and disclosure control ambiguous. Keeping them separate makes each decision inspectable and allows derivative indexes to be rebuilt.

### 32.2 Why policy is outside the model

A language model can interpret intent and propose a plan, but it is probabilistic and can be influenced by untrusted content. Authorization, consent, data classification, risk, and approval are security decisions and must be evaluated by deterministic application logic. The model may request a capability; it cannot create a capability. This applies equally to memory writes, retrieval, connector calls, exports, and deletion.

### 32.3 Why the MVP is modular rather than distributed

The pilot needs clear ownership and reliable behavior more than it needs many network boundaries. A modular monolith reduces deployment, debugging, and transaction complexity while preserving domain APIs, events, contracts, and repository boundaries. Physical extraction is justified by measurable pressure (§5.2), not by the mere existence of a logical module.

### 32.4 Why derivative data is disposable

Embeddings, caches, search projections, summaries, and evaluation artifacts are derived from canonical user data. They improve speed but must never become the only source of truth. Treating them as rebuildable simplifies model migration, correction, deletion, backup recovery, and incident response.

### 32.5 Why agent architecture is a state machine

An agent task can span minutes, approvals, retries, worker restarts, provider timeouts, and uncertain external outcomes. A request/response function cannot safely represent that lifecycle. Persisted states and transitions make it possible to resume, cancel, reconcile, audit, and prove that a step was not executed twice.

### 32.6 Why privacy has three gates

The write, retrieval, and disclosure gates are intentionally independent decisions: information can be stored but excluded from a particular model call, retrieved internally but not sent to a connector, or deleted from active use while physical cleanup completes.

### 32.7 Why encryption posture is an explicit, versioned claim (new)

Cryptographic claims age badly if they are made once in marketing copy and never revisited. §7 exists so that "what can selfie.Me technically read, and why" has one canonical, dated answer that product, legal, and security all point to — instead of three different answers when a customer, regulator, or journalist asks.

### 32.8 Architectural invariants

Across every deployment shape, the following must remain true:

1. No resource operation occurs without an authenticated principal and owner/tenant scope.
2. Model output never bypasses policy or authorization.
3. Canonical records remain recoverable independently of indexes and caches.
4. External writes are bounded by scope, approval, idempotency, and reconciliation.
5. Deletion and revocation propagate to all active and derivative paths.
6. Observability explains system behavior without making private content available to ordinary operators.
7. The stated encryption/privacy posture (§7) always matches what the deployed system actually does.

## 33. Architecture interpretation guide

This section — deliberately placed last, unlike v0.1's mid-document placement — collects "how to read this document" notes for reviewers new to the pack.

- **System context and logical architecture** describe what is inside selfie.Me's control and what is external, and group responsibilities into planes so user experience, intelligence, personal context, actions, governance, data, and operations can evolve independently.
- **Physical evolution** should follow evidence: extract a component when it has a distinct scaling profile, reliability need, security boundary, or ownership model — not on schedule.
- **Personal context architecture** exists to prevent a generated interpretation from being mistaken for user truth.
- **Agent architecture and trust boundaries** make Planner/Policy/Executor/Observer responsibilities enforceable, ensuring untrusted client, file, model, and provider content cannot directly expand authority.
- **Data, resilience, security, and privacy** sections describe why canonical data must remain durable, scoped, and recoverable, while derivative indexes, caches, and summaries must never become the source of truth.
- **Deployment, capacity, and failure planning** are hypotheses to validate with telemetry (§17), not guarantees — revisit the capacity math in §17.2 before every order-of-magnitude growth milestone.
- **Evaluation and traceability** connect architecture to outcomes: memory precision, contradiction safety, grounding, approval quality, and privacy correctness should be measured with representative scenarios, not only infrastructure metrics.
