selfie.Me

Technical Design Document

Draft v0.1 --- Working baseline / hypotheses to validate

| Field \| Value \|

| --- \| --- \|

| Product \| selfie.Me \|

| Version \| 0.1 \|

| Status \| Initial proposed baseline \|

| Source basis \| Company Documentation Pack - Initial v0.1; detailed
  behaviors are proposed assumptions requiring validation. \|

# PART II --- TECHNICAL DESIGN DOCUMENT (TDD)

## 9. Technical Objectives

The implementation should make personalization durable without coupling
core product behavior to a single LLM vendor. The architecture separates
orchestration, memory, policy, data access and model invocation so that
each can evolve independently. All requests are tenant/user scoped and
every downstream operation carries an authenticated principal and
correlation identifier.

## 10. Proposed Technology Baseline

| Layer \| Proposed baseline \| Rationale \|

| --- \| --- \| --- \|

| Client \| Web app (React/Next.js or equivalent); mobile later \| Fast
  iteration and streaming UI. \|

| API \| TypeScript/Node.js or Python/FastAPI service boundary \| Strong
  ecosystem for AI APIs and service development. \|

| Transactional DB \| PostgreSQL \| Strong relational integrity for
  identity, consent, memory metadata, decisions and audit references. \|

| Vector retrieval \| pgvector initially; dedicated vector store only if
  scale requires \| Keeps MVP operationally simple. \|

| Cache/ephemeral state \| Redis \| Rate limits, short-lived
  conversation/agent state, locks and job coordination. \|

| Object storage \| S3-compatible encrypted object storage \| Files,
  exports and large artifacts. \|

| Queue/workflow \| Durable queue/workflow engine (e.g., managed queue +
  workers; Temporal-class engine when needed) \| Reliable long-running
  agent and deletion workflows. \|

| LLM gateway \| Internal model gateway \| Provider abstraction, policy,
  telemetry, prompt/version control and fallback. \|

| Embeddings \| Provider-abstracted embedding service \| Avoid binding
  memory index to one model provider. \|

| Secrets \| Managed secrets/KMS \| Connector credentials and encryption
  keys. \|

| Observability \| OpenTelemetry-compatible traces + centralized
  logs/metrics \| Cross-service debugging and SLOs. \|

Technology names above are proposed implementation choices because the
source does not prescribe a stack. They should be validated against team
expertise, cost, data residency and expected scale.

## 11. Service Decomposition

| Component \| Responsibilities \|

| --- \| --- \|

| API Gateway/BFF \| Authentication context, request validation, rate
  limiting, streaming transport, client-oriented aggregation. \|

| Conversation Service \| Conversation/message persistence, context
  window assembly request, response lifecycle. \|

| Orchestrator \| Determines whether a request is direct answer,
  retrieval, decision workflow or agent task; coordinates model calls.
  \|

| Memory Service \| Candidate extraction, normalization, deduplication,
  policy checks, CRUD, retrieval and supersession. \|

| Belief Service \| Maintains propositions, evidence links, confidence
  changes and contradiction state. \|

| Decision Service \| Decision workspaces, criteria, options, evidence
  snapshots and outcomes. \|

| Agent Service \| Planning, step execution, approval pauses, tool
  invocation and execution history. \|

| Policy/Consent Service \| Consent scopes, data classifications,
  authorization decisions, retention rules. \|

| Connector Service \| OAuth/token management, normalized tool
  interfaces and connector-specific adapters. \|

| Model Gateway \| Model routing, prompt templates, structured output
  validation, cost/latency telemetry, safety hooks. \|

| File/Ingestion Service \| Uploads, malware scanning, parsing,
  chunking, metadata and embeddings. \|

| Notification Service \| Task completion/approval notifications when
  enabled. \|

| Audit Service \| Append-only security/product audit events with
  redaction. \|

## 12. Core Data Model

| Entity \| Key fields \|

| --- \| --- \|

| User \| user_id, status, locale, timezone, created_at \|

| Conversation \| conversation_id, user_id, title, status, created_at,
  archived_at \|

| Message \| message_id, conversation_id, role, content_ref,
  model_execution_id, created_at \|

| Memory \| memory_id, user_id, type, canonical_text/value,
  explicitness, confidence, sensitivity, status, valid_from, valid_to,
  created_at, updated_at \|

| MemoryEvidence \| memory_id, source_type, source_id,
  source_excerpt_hash, observed_at \|

| MemoryEmbedding \| memory_id, embedding_model, vector, indexed_at \|

| Belief \| belief_id, user_id, proposition, confidence, status,
  last_evaluated_at \|

| BeliefEvidence \| belief_id, evidence_type, evidence_id, polarity,
  weight \|

| Decision \| decision_id, user_id, question, status, created_at,
  closed_at \|

| DecisionOption \| option_id, decision_id, label, description \|

| DecisionCriterion \| criterion_id, decision_id, name, weight, source
  \|

| DecisionSnapshot \| snapshot_id, decision_id, evidence_json,
  assumptions_json, result_json, created_at \|

| AgentRun \| run_id, user_id, goal, status, plan_version, started_at,
  completed_at \|

| AgentStep \| step_id, run_id, sequence, tool, risk_class,
  approval_state, status, result_ref \|

| Consent \| consent_id, user_id, scope, version, granted_at, revoked_at
  \|

| ConnectorGrant \| grant_id, user_id, provider, scopes,
  encrypted_token_ref, status \|

| AuditEvent \| event_id, principal_id, action, resource_type,
  resource_id, decision, metadata_redacted, created_at \|

## 13. Memory Write Pipeline

1.  Conversation Service emits an interaction-completed event after the
    response lifecycle reaches a stable point.

2.  Memory extractor receives the minimum required message/context and
    produces structured candidate memories.

3.  Schema validator rejects malformed output and normalizes types,
    dates and entities.

4.  Classifier assigns memory type, sensitivity, explicit/inferred
    status and preliminary confidence.

5.  Policy/Consent Service decides STORE, REQUIRE_CONFIRMATION,
    TRANSIENT_ONLY or REJECT.

6.  Deduplication searches canonical keys plus semantic similarity
    against active memories.

7.  Memory Service creates a new memory, confirms an existing one, or
    creates a supersession/contradiction relationship.

8.  Embedding is generated asynchronously and indexed.

9.  Audit event records the mutation without copying unnecessary private
    content.

### 13.1 Candidate memory schema

A candidate memory should be a typed structured object rather than free
text. Minimum fields: candidate_id, type, subject, predicate/attribute,
value, normalized_value, temporal_scope, explicitness, confidence,
sensitivity, source_message_ids, rationale_code and
requires_confirmation. The rationale_code is machine-readable (for
example USER_EXPLICIT, REPEATED_PREFERENCE, INFERRED_FROM_OUTCOME)
rather than an unrestricted hidden chain-of-thought field.

### 13.2 Deduplication and supersession

Exact identity should use stable normalized keys where possible.
Semantic similarity may suggest duplicates but must not independently
merge materially different facts. A new explicit statement that
conflicts with an older time-sensitive memory should normally supersede
the old memory while retaining history. A conflicting inference should
create evidence against the belief rather than overwriting an explicit
memory.

## 14. Memory Retrieval Pipeline

1.  Orchestrator creates a retrieval intent containing the current task,
    entities, requested time horizon and allowed sensitivity classes.

2.  Memory Service performs structured filtering by user, status,
    category and temporal validity.

3.  Semantic retrieval obtains candidate memories using vector
    similarity.

4.  Hybrid ranker combines semantic score, lexical/entity match,
    recency, confidence, explicitness, pinning and task relevance.

5.  Policy layer removes memories not permitted for the current
    surface/tool/domain.

6.  Context compressor converts selected records into concise grounded
    context with memory IDs/provenance references.

7.  LLM receives only the bounded context needed for the request.

A proposed scoring function for experimentation is: score = 0.35
semantic relevance + 0.20 entity/task match + 0.15 recency + 0.15
confidence + 0.10 explicitness + 0.05 user pinning. These weights are
starting hypotheses and must be evaluated rather than hard-coded as
product truth.

## 15. Belief Update Algorithm

Beliefs are computed views over evidence rather than a replacement for
evidence. Each proposition has supporting and contradicting evidence.
Confidence updates should be deterministic enough to test and inspect.
MVP can use rule-based confidence bands rather than pretending to have
calibrated Bayesian probabilities.

| Condition \| Proposed behavior \|

| --- \| --- \|

| New explicit user confirmation \| Strong positive evidence; may set
  belief to confirmed unless contradicted by newer explicit evidence. \|

| Repeated consistent behavior \| Moderate positive evidence; keep as
  inferred. \|

| Single model inference \| Weak evidence; do not use for consequential
  behavior. \|

| Explicit correction \| Strong negative evidence against superseded
  proposition; create/update replacement. \|

| Conflicting reliable sources \| Set conflict state; reduce confidence;
  retrieve both sides when material. \|

| Stale time-sensitive belief \| Decay retrieval priority and require
  fresh confirmation for consequential use. \|

## 16. Agent Runtime Design

Agent execution is modeled as a state machine: CREATED → PLANNING →
READY → RUNNING → WAITING_APPROVAL/WAITING_EXTERNAL → COMPLETED, FAILED
or CANCELLED. Each transition is persisted so work can resume after
process failure.

### 16.1 Planning contract

-   Goal: normalized user objective.

-   Plan: ordered steps with dependencies.

-   Tool contract: tool name, operation, required scopes, input schema
    and output schema.

-   Risk class: READ_ONLY, REVERSIBLE_WRITE, CONSEQUENTIAL_WRITE,
    HIGH_IMPACT.

-   Approval requirement: none, per-step, or explicit final
    confirmation.

-   Data disclosure: fields that will be sent to the external provider.

-   Success condition and rollback/compensation strategy where
    available.

### 16.2 Tool execution controls

-   Validate tool arguments against a schema after model generation.

-   Authorize the exact operation and resource before execution.

-   Never expose raw OAuth refresh tokens or service secrets to the
    model.

-   Use idempotency keys for writes where provider support exists.

-   Bound retries and use exponential backoff for transient failures.

-   Persist external operation IDs for reconciliation.

-   Sanitize untrusted tool output before it is reintroduced into the
    model context.

-   Require renewed approval when the plan materially changes after
    approval.

## 17. API Design

| Method / Path \| Purpose \|

| --- \| --- \|

| POST /v1/conversations \| Create conversation. \|

| POST /v1/conversations/{id}/messages \| Send user message; stream
  assistant result. \|

| GET /v1/memories \| Search/list current memories. \|

| POST /v1/memories \| Create explicit memory. \|

| PATCH /v1/memories/{id} \| Correct, confirm, pin or suppress memory.
  \|

| DELETE /v1/memories/{id} \| Delete memory and enqueue downstream
  cleanup. \|

| GET /v1/beliefs \| List user-visible inferred beliefs where product
  policy exposes them. \|

| POST /v1/beliefs/{id}/challenge \| Challenge/suppress an inferred
  belief. \|

| POST /v1/decisions \| Create decision workspace. \|

| POST /v1/decisions/{id}/analyze \| Generate/update decision analysis.
  \|

| POST /v1/agents/runs \| Create an agent run. \|

| GET /v1/agents/runs/{id} \| Get status/plan/results. \|

| POST /v1/agents/runs/{id}/approve \| Approve a pending step or plan.
  \|

| POST /v1/agents/runs/{id}/cancel \| Cancel run. \|

| GET /v1/consents \| List consent state. \|

| PUT /v1/consents/{scope} \| Grant/update consent. \|

| DELETE /v1/consents/{scope} \| Revoke consent. \|

| POST /v1/exports \| Create data export. \|

| DELETE /v1/account \| Initiate account deletion. \|

### 17.1 API conventions

-   OAuth/OIDC access token or secure session authenticates the caller.

-   All resource IDs are opaque UUID/ULID-class identifiers.

-   Mutating endpoints accept idempotency keys where duplicate
    submission is plausible.

-   Errors use stable codes plus human-readable messages and correlation
    IDs.

-   Pagination uses opaque cursors.

-   Sensitive fields are omitted by default and require explicit
    authorized expansion.

-   Versioning begins at /v1; breaking contract changes require a new
    major API version.

## 18. Security Design

| Threat \| Control \|

| --- \| --- \|

| Cross-tenant data leakage \| Mandatory user/tenant predicates in
  repositories; row-level controls where appropriate; authorization
  tests. \|

| Prompt injection from files/tools \| Treat external content as
  untrusted data; separate instructions from evidence; tool allowlists;
  output sanitization. \|

| Connector credential theft \| Tokens stored encrypted in secret store;
  never logged or sent to LLM. \|

| Excessive agent authority \| Fine-grained scopes, risk classification,
  approvals, least privilege and short-lived credentials. \|

| Memory poisoning \| Provenance, explicit/inferred distinction,
  confidence, contradiction tracking, user correction. \|

| Sensitive data in logs \| Structured redaction, allowlisted fields,
  content-free metrics. \|

| Replay/duplicate writes \| Idempotency keys, operation IDs and
  state-machine guards. \|

| Model/provider data exposure \| Minimum context, provider
  configuration, contractual/privacy review and routing policy. \|

| Account takeover \| MFA-capable identity, session revocation,
  anomaly/rate controls. \|

| Deletion gaps \| Data inventory, deletion orchestration, tombstones
  and verification jobs. \|

## 19. Privacy and Retention Implementation

Data classes should have separate retention policies: conversation
content, durable memories, embeddings, files, agent execution data,
security audit data and backups. A deletion coordinator owns erasure
workflows across PostgreSQL, vector indexes, object storage, caches and
external connector-derived artifacts. Active retrieval must honor
deletion immediately even if asynchronous physical erasure is still
completing.

## 20. Observability

-   Correlation ID spans client request, orchestration, retrieval, model
    calls, tool calls and persistence.

-   Metrics: request latency, model latency/tokens/cost, memory
    retrieval precision proxies, memory mutation rate, tool success,
    approval rate, agent completion rate, queue lag and deletion SLA.

-   Traces record component timing and IDs, not unrestricted private
    message bodies.

-   Security events include failed authorization, unusual connector
    behavior, bulk export and deletion actions.

-   Model executions retain model identifier, prompt-template version,
    policy version and structured-output validation status.

## 21. Testing Strategy

| Level \| Examples \|

| --- \| --- \|

| Unit \| Memory classification rules, ranker scoring, consent
  evaluation, state transitions, redaction. \|

| Contract \| API schemas, connector adapters, model structured-output
  schemas. \|

| Integration \| Conversation→memory write; retrieval→response;
  agent→approval→tool; deletion across stores. \|

| Security \| IDOR/cross-user access, prompt injection, SSRF/tool
  misuse, token leakage, rate-limit bypass. \|

| AI evaluation \| Memory relevance, false-memory rate, contradiction
  handling, grounding, decision transparency, tool selection. \|

| Load \| Concurrent streaming conversations, vector retrieval, queue
  throughput, long-running agents. \|

| Resilience \| Provider outage, queue restart, DB failover, duplicate
  events, partial deletion failure. \|

| User acceptance \| Onboarding clarity, memory control, decision flow,
  approval comprehension. \|

## 22. Deployment and Delivery

Use separate development, staging and production environments with
isolated databases, secrets and connector credentials. Infrastructure is
defined as code. CI performs linting, tests, dependency/security
scanning and migration checks. CD deploys progressively with health
checks and rollback. Database migrations are backward-compatible during
rolling deployment. Feature flags gate new memory and agent behaviors.

## 23. Runtime request and response contracts

Every request entering the application should be normalized into a
request context containing:

| Field | Purpose |
| --- | --- |
| `principal_id` | Authenticated user or service principal making the request. |
| `tenant_id` | Isolation boundary used in every repository and event. |
| `correlation_id` | Joins client, API, model, queue, and connector telemetry. |
| `idempotency_key` | Prevents duplicate mutation when a client retries. |
| `locale` and `timezone` | Supports deterministic presentation and time interpretation. |
| `consent_snapshot` | Records the policy basis used for this operation. |

The response envelope should provide a stable status, a typed result,
an error code when applicable, a correlation ID, and pagination or
continuation information when the operation is incomplete. Streaming
endpoints should emit explicit `started`, `delta`, `tool_status`,
`approval_required`, `completed`, and `failed` events. Clients must be
able to safely reconnect and determine whether the final response was
already persisted.

## 24. Persistence and transaction boundaries

Canonical mutations should use a database transaction whenever related
records must change atomically. For example, correcting a memory
updates its status, creates the replacement relationship, and writes
the audit reference in one transaction. Expensive work such as
embedding generation, file parsing, or provider calls should not run
inside that transaction.

The outbox pattern is recommended for events that must be published
after a successful commit. An outbox row is created in the same
transaction as the domain mutation; a worker publishes it and records
delivery status. Consumers must be idempotent because delivery may be
repeated. This avoids the failure mode where the database commits but a
memory-index or deletion event is lost.

Repositories must require a user or tenant scope as an input rather
than relying on callers to remember an additional filter. Tests should
exercise empty, mismatched, deleted, and cross-user identifiers.

## 25. Database and index implementation guidance

Use foreign keys, check constraints, unique constraints, and
timestamp/status invariants for safety that does not depend on model
behavior. Recommended indexes include owner plus status on user-scoped
entities, conversation plus creation time for messages, active memory
lookup keys, agent run plus state, and consent scope plus current
status. Query plans should be reviewed before introducing broad
semantic retrieval.

Embeddings should include the source record ID, owner/tenant key,
embedding-model version, content hash, sensitivity classification,
index status, and deletion timestamp where relevant. The retrieval
query must filter ownership and active status before similarity ranking;
similarity is never a substitute for authorization. Re-indexing must
be resumable and safe to run concurrently with normal writes.

## 26. API error model and idempotency

API errors should use stable machine-readable codes such as
`VALIDATION_ERROR`, `NOT_FOUND`, `FORBIDDEN`, `CONSENT_REQUIRED`,
`CONFLICT`, `DEPENDENCY_UNAVAILABLE`, `POLICY_DENIED`, and
`RETRYABLE_OPERATION_UNKNOWN`. Human-readable text may change, but
clients should branch on the code and HTTP status.

Mutation endpoints should persist idempotency results for a bounded
period appropriate to the operation. A repeated key with the same
request fingerprint returns the original result; reusing a key for a
different payload returns a conflict. External writes additionally
persist provider operation IDs so an uncertain timeout can be
reconciled before another attempt.

## 27. Model gateway implementation

The model gateway is the only application boundary allowed to invoke
an external model provider. It should:

1. Select a provider and model using task, region, data-classification,
   availability, cost, and latency policy.
2. Resolve a versioned prompt template and system policy.
3. Assemble only the approved context fields and mark evidence as data,
   not instructions.
4. Enforce token, timeout, and output-size budgets.
5. Validate structured output against a schema and reject or repair only
   through bounded, observable logic.
6. Return model metadata, usage, provider request ID, and policy
   version without exposing secrets or unrestricted prompts to ordinary
   logs.

Provider fallback must be task-compatible and privacy-compatible. A
provider with different retention, region, or tool behavior is not a
valid fallback merely because it is available.

## 28. Queue, worker, and workflow behavior

Jobs should declare a type, owner, attempt number, visibility timeout,
maximum attempts, and deduplication key. Workers acknowledge a job only
after its durable state transition succeeds. Dead-letter queues must
retain the reason, payload reference, and correlation ID while applying
the same privacy controls as normal logs.

Long-running agent and deletion workflows should persist a checkpoint
after each meaningful transition. Timers, approvals, retries, and
compensation steps must be represented as data so a worker restart
cannot lose the workflow. Administrative replay requires an explicit
operator action and must not bypass current authorization or deletion
tombstones.

## 29. File ingestion and untrusted content

Uploads should use short-lived signed upload URLs where possible,
enforce size and content-type limits, scan for malware, and assign a
quarantine status before parsing. Parsers must treat documents,
metadata, OCR text, spreadsheets, and tool responses as untrusted
content. Extracted chunks inherit the source owner, consent scope,
sensitivity, and deletion lifecycle.

Chunking and embedding are asynchronous. A failed parse must be visible
as a failed ingestion rather than silently producing an empty source.
The model may use extracted text only after the ingestion record is
authorized and indexed; text inside a file cannot grant a connector
permission or override system policy.

## 30. Security and privacy control points

The implementation should enforce controls at multiple independent
points:

| Point | Required checks |
| --- | --- |
| API ingress | Authentication, input schema, rate limits, CSRF/session protection where applicable |
| Repository access | Owner/tenant scope, resource status, operation authorization |
| Context assembly | Consent, sensitivity, purpose, temporal validity, minimum necessary fields |
| Model gateway | Provider policy, prompt/version controls, output schema, redacted telemetry |
| Tool execution | Exact operation, connector grant, resource scope, risk and approval state |
| Data lifecycle | Revocation/deletion tombstones, derivative cleanup, backup policy |
| Operations | Break-glass access, immutable audit, secret rotation, alerting |

Defense in depth is important because a defect in a model prompt,
retrieval query, or UI check must not become the only barrier protecting
private data.

## 31. Configuration, secrets, and feature flags

Configuration should distinguish non-secret operational settings,
provider settings, policy versions, and secrets. Secrets must be
injected through the environment's secret manager, rotated without
source changes, and excluded from logs, error messages, traces, and
model context. Local development may use documented placeholder
credentials, but production startup should reject placeholders.

Feature flags should gate high-risk behaviors such as inferred-memory
storage, new connectors, autonomous retries, and model-provider
routing. A flag change should be auditable, scoped by environment or
cohort, and reversible. Flags must not be used to bypass authorization
or deletion controls.

## 32. Migration, backup, and recovery procedures

Schema migrations should be additive and backward-compatible across the
deployment window: add nullable fields or new tables, deploy code that
supports both versions, backfill in bounded batches, then enforce
constraints after verification. Destructive changes require a reviewed
rollback or restore plan.

Backups must be encrypted, access-controlled, monitored, and tested by
restoring into an isolated environment. Recovery objectives should be
recorded separately for core conversation data, memory indexes, files,
audit events, and asynchronous workflow state. Rebuilding a derivative
index from canonical data is preferred to treating a backup of the
index as the only recovery path.

## 33. Technical definition of done

A technical capability is complete only when its happy path, failure
path, authorization path, privacy lifecycle, observability, and
rollback behavior are defined. The implementation should include:

- versioned API/schema or event contracts;
- owner-scoped persistence and migration;
- structured logs and metrics with redaction;
- unit, integration, and security tests appropriate to the risk;
- retry/idempotency behavior for asynchronous or external operations;
- feature-flag and configuration behavior for staged rollout;
- operational documentation for alerting, replay, recovery, and deletion;
- model/prompt/provider version traceability where AI is involved.

## 34. Technical decisions still requiring validation

The proposed stack remains intentionally provider-neutral. Before
production selection, the team should validate PostgreSQL/pgvector
query performance with representative memory volume, choose the
identity/session approach, confirm the queue or workflow product,
define data residency and provider-retention requirements, and test
the cost and latency of the model gateway. These decisions should be
captured as ADR updates with measured evidence rather than preference
alone.

## 35. Technical theory and implementation rationale

The technical design translates product trust principles into
enforceable runtime behavior. The most important distinction is between
canonical state and derived or speculative state. Canonical records
such as users, consent, messages, memories, decisions, approvals, and
agent transitions require transactional integrity. Embeddings, caches,
summaries, rankings, and model suggestions are derived artifacts and
must be reproducible, versioned, and disposable.

### 35.1 Request context as a security boundary

`principal_id`, `tenant_id`, correlation data, idempotency information,
and the consent snapshot are not convenience metadata. They are the
minimum context needed to interpret an operation safely. Passing this
context through repositories, jobs, model calls, and connector
adapters prevents a background worker from losing the identity or
purpose under which work was authorized. A missing scope should be a
hard error, not an implicit global query.

### 35.2 Transactions and asynchronous work

Transactions protect related canonical changes; queues protect
responsiveness and isolate slow or unreliable dependencies. They solve
different problems and should not be mixed casually. The outbox
pattern connects them: commit the domain mutation and its pending
event together, then deliver the event asynchronously. Consumers must
be idempotent because at-least-once delivery is safer and more
operationally realistic than assuming exactly-once execution.

### 35.3 Retrieval is authorization plus relevance

Semantic similarity only estimates usefulness. It does not establish
ownership, consent, freshness, sensitivity permission, or whether the
record is active. Retrieval must first constrain the candidate set by
security and lifecycle rules, then rank the remaining records by task
relevance. This ordering prevents a highly similar but deleted,
private, stale, or cross-user record from entering the model context.

### 35.4 Structured model output and bounded autonomy

Schemas make model output testable, but schemas do not make it true.
Candidate memories, beliefs, decisions, and plans require validation,
provenance, policy evaluation, and sometimes user confirmation.
Retries and repair prompts must be bounded because repeated generation
can turn a malformed result into an unobservable loop. Autonomy is
bounded by the tools, scopes, risk classes, budgets, and state
transitions that application code controls.

### 35.5 External operations and uncertainty

Distributed systems cannot always tell whether a timed-out external
write happened. The design therefore records an operation ID before
execution, uses provider idempotency where available, and reconciles
unknown outcomes before retrying. The user-facing state should say
“outcome needs confirmation” rather than falsely reporting failure or
success. This is especially important for messages, bookings, payments,
deletions, and other irreversible actions.

### 35.6 Data lifecycle as an implementation concern

Retention, revocation, correction, export, and deletion are data
flows across every store, not single-row operations. The same owner,
classification, status, and source identifiers must travel with
database records, vector chunks, objects, queue payloads, caches,
logs, and provider references. Tombstones and lifecycle ledgers ensure
that delayed work cannot recreate data that a user has deleted.

### 35.7 Observability without surveillance

The system needs enough telemetry to explain latency, authorization,
model versions, retrieval decisions, retries, and failures. It does
not need unrestricted copies of private conversations in logs.
Allowlisted metadata, content hashes, redacted fields, sampled traces,
and protected audit records provide operational evidence while
reducing accidental exposure. Access to exceptional diagnostic content
must itself be authorized and audited.

### 35.8 Technical invariants

Implementation and code review should preserve these invariants:

1. Every query and job is scoped to an owner or tenant.
2. Every external model or tool call has a policy decision.
3. Every durable mutation has an audit reference and lifecycle state.
4. Every retry has a bounded policy and a duplicate-protection key.
5. Every derivative index can be invalidated and rebuilt.
6. Every asynchronous workflow can resume or fail visibly.
7. Every secret is excluded from prompts, logs, client responses, and
   ordinary telemetry.
8. Every breaking contract or model/prompt change is versioned and
   traceable.

## 36. Cross-document implementation traceability

The three design documents should be used together rather than as
independent descriptions. The functional specification defines what
the user can expect; the architecture document defines where trust and
responsibility reside; and this technical document defines how those
responsibilities become schemas, state transitions, APIs, jobs, and
tests. For example, the functional requirement that a user can delete
a memory maps to the architecture's privacy gates and lifecycle
ownership, then to technical tombstones, outbox events, index cleanup,
repository filters, and deletion verification tests.

Any implementation change that alters user-visible behavior should
update the corresponding requirement and acceptance evidence. Any
change to trust boundaries, canonical ownership, lifecycle guarantees,
or provider behavior should update the architecture decision record
and technical contract. This traceability prevents documentation from
describing a safer system than the code actually implements.

## 37. Technical section interpretation guide

The technical design turns the functional contract and architecture
principles into implementable mechanisms. Technology choices are
proposed baselines; the invariants, ownership rules, lifecycle
guarantees, and security controls are the durable requirements.

### 37.1 Objectives and technology baseline

The objective is provider-independent personalization with explicit
control over data and actions. PostgreSQL is the proposed canonical
store because relational integrity matters more than premature
specialization. Redis is ephemeral support infrastructure, object
storage holds large artifacts, and pgvector is a derivative retrieval
index. Each choice should be revisited using measured latency, cost,
scale, residency, and team-operability evidence.

### 37.2 Service decomposition

The listed services are responsibility boundaries. They define who
owns a rule and where a mutation should occur. They do not require
immediate network separation. A module may call another module through
an internal contract during the MVP, provided it preserves ownership,
authorization, versioning, and observability.

### 37.3 Data model and lifecycle

Entities should represent business meaning, not just model output.
Foreign keys and status constraints protect canonical relationships;
provenance and timestamps support correction and explanation; owner
keys protect isolation. Every new data entity should document its
source, sensitivity, retention, derivative indexes, deletion behavior,
and user-visible representation.

### 37.4 Memory, retrieval, and belief processing

Memory writing favors precision and policy compliance. Retrieval favors
authorized relevance rather than maximum similarity. Belief processing
preserves supporting and contradictory evidence instead of hiding
disagreement behind one score. These pipelines should be observable,
versioned, and replayable against test fixtures without exposing
private content in ordinary logs.

### 37.5 Agent runtime and API behavior

The agent state machine makes long-running work truthful and
recoverable. APIs should expose stable resource state, typed errors,
pagination, idempotency, and correlation identifiers. Streaming is a
transport optimization, not proof that work completed. The durable
message or run record is the source for reconnect, refresh, audit, and
support workflows.

### 37.6 Security, privacy, and observability

Security controls must be layered: ingress validation, repository
scoping, context filtering, gateway policy, connector authorization,
secret management, and lifecycle enforcement. Privacy-safe
observability records enough metadata to investigate behavior without
turning logs into a second ungoverned copy of the user's life.

### 37.7 Testing, delivery, and operations

Unit tests validate local rules; contract tests protect boundaries;
integration tests validate lifecycle flows; security tests challenge
isolation and authority; AI evaluations measure quality; load and
resilience tests validate operational assumptions. Delivery should use
backward-compatible migrations, isolated environments, progressive
rollouts, feature flags, health checks, rollback plans, and documented
recovery procedures.

### 37.8 Technical change rule

Any change to a model provider, prompt, embedding model, schema,
connector, retention policy, or authorization rule can affect user
trust. Such changes require a version, owner, migration or rollback
plan, evaluation evidence, and an update to the relevant functional and
architecture documentation. This keeps implementation behavior aligned
with the promises made to users.
