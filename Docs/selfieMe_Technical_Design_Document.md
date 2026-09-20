# selfie.Me — Technical Design Document (TDD)

**Version:** V01 — Refined baseline (supersedes the original v0.1 draft)
**Status:** Approved working baseline for founder pilot engineering
**Owners:** Head of Engineering (accountable), Engineering leads per domain (`§4`), Head of Security/DPO (security/privacy sections)

## Document control

| Field | Value |
| --- | --- |
| Document | Technical Design Document (Part II of the selfie.Me documentation pack) |
| Companion documents | Functional Specification Document (`FSD`), Architecture Design Document (`ADD`) |
| Cross-reference format | `FSD §x.y`, `TDD §x.y`, `ADD §x.y` — sections number independently per document |

### Changelog since v0.1

- Fixed a numbering collision: v0.1 used "§9" both here and in the FSD. This document's sections now run 1–29, referenced only as `TDD §x.y`.
- Added concrete numbers everywhere v0.1 left a parameter undefined: embedding dimensionality and index type (§6.1), rate limits (§10.1), token/context budgets (§20), connection-pool sizing (§18), and idempotency-window duration (§19).
- Added §5.1, resolving the v0.1 inconsistency where Redis was described as holding both disposable cache/locks *and* agent workflow state, while a later section required agent state to survive worker restarts — those cannot both be true of the same store (see `ADD §11` for the architectural fix; this section carries the implementation consequence).
- Added §21, a minimal SQL DDL sketch for the core tables, because "Core Data Model" in v0.1 listed fields with no types, constraints, or indexes — not implementable as written.
- Added §26, an on-call runbook example (vector index rebuild), and §27, a request-scoped example trace, since v0.1 asserted observability requirements without ever showing what one looks like end to end.
- Converted every previously malformed table into valid markdown.
- Moved the "interpretation guide" to the end, matching the structural fix applied to the other two documents.

---

## 1. Technical objectives

The implementation makes personalization durable without coupling core product behavior to a single LLM vendor. The architecture separates orchestration, memory, policy, data access, and model invocation so each can evolve independently. All requests are tenant/user scoped, and every downstream operation carries an authenticated principal and correlation identifier.

## 2. Proposed technology baseline

| Layer | Proposed baseline | Rationale |
| --- | --- | --- |
| Client | Web app (React/Next.js); mobile later | Fast iteration and streaming UI. |
| API | Python/FastAPI (matches the current repository scaffold) | Strong ecosystem for AI APIs and async I/O; team already bootstrapped on it. |
| Transactional DB | PostgreSQL 16 | Relational integrity for identity, consent, memory metadata, decisions, and audit references. |
| Vector retrieval | pgvector initially (`ADD §17.2` shows it holds through pilot scale); dedicated vector store only if a scale-out trigger fires (`ADD §5.2`) | Keeps MVP operationally simple. |
| Cache/ephemeral state | Redis 7 — coordination and cache **only**, never the sole record of durable state | Rate limits, short-lived conversation UI state, locks, job coordination (`ADD §11`). |
| Object storage | S3-compatible encrypted object storage | Files, exports, and large artifacts. |
| Queue/workflow | Durable queue + workers for MVP; adopt a Temporal-class engine when retries/timers/compensations get complex (`ADD §5.2`) | Reliable long-running agent and deletion workflows without premature infrastructure. |
| LLM gateway | Internal model gateway | Provider abstraction, policy, telemetry, prompt/version control, and fallback. |
| Embeddings | Provider-abstracted embedding service, 1,536-dimension vectors as the MVP standard (§6.1) | Avoids binding the memory index to one model provider while keeping index math tractable. |
| Secrets | Managed secrets/KMS | Connector credentials and encryption keys. |
| Observability | OpenTelemetry-compatible traces + centralized logs/metrics | Cross-service debugging and SLOs. |

Technology names are proposed choices, validated against team expertise, cost, data residency, and expected scale — not prescribed by the source documentation pack.

## 3. Service decomposition

| Component | Responsibilities |
| --- | --- |
| API Gateway/BFF | Authentication context, request validation, rate limiting (§10.1), streaming transport, client-oriented aggregation. |
| Conversation Service | Conversation/message persistence, context window assembly request, response lifecycle. |
| Orchestrator | Determines whether a request is direct answer, retrieval, decision workflow, or agent task; coordinates model calls. |
| Memory Service | Candidate extraction, normalization, deduplication, policy checks, CRUD, retrieval, and supersession. |
| Belief Service | Maintains propositions, evidence links, confidence changes, and contradiction state. |
| Decision Service | Decision workspaces, criteria, options, evidence snapshots, and outcomes. |
| Agent Service | Planning, step execution, approval pauses, tool invocation, and execution history. |
| Policy/Consent Service | Consent scopes, data classifications, authorization decisions, retention rules. |
| Connector Service | OAuth/token management, normalized tool interfaces, connector-specific adapters. |
| Model Gateway | Model routing, prompt templates, structured output validation, cost/latency telemetry, safety hooks (§20). |
| File/Ingestion Service | Uploads, malware scanning, parsing, chunking, metadata, and embeddings. |
| Notification Service | Task completion/approval notifications when enabled. |
| Audit Service | Append-only security/product audit events with redaction. |

## 4. Core data model

| Entity | Key fields |
| --- | --- |
| User | `user_id`, `status`, `locale`, `timezone`, `created_at` |
| Conversation | `conversation_id`, `user_id`, `title`, `status`, `created_at`, `archived_at` |
| Message | `message_id`, `conversation_id`, `role`, `content_ref`, `model_execution_id`, `created_at` |
| Memory | `memory_id`, `user_id`, `type`, `canonical_text`/`value`, `explicitness`, `confidence`, `sensitivity_tier` (`ADD §7.1`), `status`, `valid_from`, `valid_to`, `created_at`, `updated_at` |
| MemoryEvidence | `memory_id`, `source_type`, `source_id`, `source_excerpt_hash`, `observed_at` |
| MemoryEmbedding | `memory_id`, `embedding_model`, `embedding_dim` (1536, §6.1), `vector`, `indexed_at` |
| Belief | `belief_id`, `user_id`, `proposition`, `confidence`, `status`, `last_evaluated_at` |
| BeliefEvidence | `belief_id`, `evidence_type`, `evidence_id`, `polarity`, `weight` |
| Decision | `decision_id`, `user_id`, `question`, `status`, `created_at`, `closed_at` |
| DecisionOption | `option_id`, `decision_id`, `label`, `description` |
| DecisionCriterion | `criterion_id`, `decision_id`, `name`, `weight`, `source` |
| DecisionSnapshot | `snapshot_id`, `decision_id`, `evidence_json`, `assumptions_json`, `result_json`, `created_at` |
| AgentRun | `run_id`, `user_id`, `goal`, `status`, `plan_version`, `started_at`, `completed_at` |
| AgentStep | `step_id`, `run_id`, `sequence`, `tool`, `risk_class`, `approval_state`, `status`, `result_ref` |
| Consent | `consent_id`, `user_id`, `scope`, `version`, `granted_at`, `revoked_at` |
| ConnectorGrant | `grant_id`, `user_id`, `provider`, `scopes`, `encrypted_token_ref`, `status` |
| AuditEvent | `event_id`, `principal_id`, `action`, `resource_type`, `resource_id`, `decision`, `metadata_redacted`, `created_at` |

A minimal executable DDL sketch is in §21 — v0.1 listed fields with no types or constraints, which is not directly implementable.

## 5. Memory write pipeline

1. Conversation Service emits an interaction-completed event after the response lifecycle reaches a stable point.
2. Memory extractor receives the minimum required message/context and produces structured candidate memories.
3. Schema validator rejects malformed output and normalizes types, dates, and entities.
4. Classifier assigns memory type, sensitivity tier, explicit/inferred status, and preliminary confidence.
5. Policy/Consent Service decides `STORE`, `REQUIRE_CONFIRMATION`, `TRANSIENT_ONLY`, or `REJECT`.
6. Deduplication searches canonical keys plus semantic similarity against active memories.
7. Memory Service creates a new memory, confirms an existing one, or creates a supersession/contradiction relationship.
8. Embedding is generated asynchronously and indexed.
9. Audit event records the mutation without copying unnecessary private content.

### 5.1 Where agent and workflow state actually lives (fixes a v0.1 inconsistency)

v0.1 listed Redis under "short-lived conversation/agent state" while also requiring agent runs to resume after a worker restart — Redis's default eviction and non-durable configuration cannot honor that guarantee. The corrected rule: **the `AgentRun`/`AgentStep` tables in PostgreSQL are the only durable record of workflow progress.** Redis may cache a read-optimized snapshot of run status for the UI, but that cache is always rebuildable from PostgreSQL and is never consulted to decide what happens next in the state machine.

### 5.2 Candidate memory schema

A candidate memory is a typed structured object, not free text. Minimum fields: `candidate_id`, `type`, `subject`, `predicate`/`attribute`, `value`, `normalized_value`, `temporal_scope`, `explicitness`, `confidence`, `sensitivity`, `source_message_ids`, `rationale_code`, `requires_confirmation`. `rationale_code` is machine-readable (e.g., `USER_EXPLICIT`, `REPEATED_PREFERENCE`, `INFERRED_FROM_OUTCOME`) rather than an unrestricted hidden chain-of-thought field.

### 5.3 Deduplication and supersession

Exact identity uses stable normalized keys where possible. Semantic similarity may suggest duplicates but must not independently merge materially different facts. A new explicit statement that conflicts with an older time-sensitive memory normally supersedes the old memory while retaining history. A conflicting inference creates evidence against the belief rather than overwriting an explicit memory.

## 6. Memory retrieval pipeline

1. Orchestrator creates a retrieval intent containing the current task, entities, requested time horizon, and allowed sensitivity classes.
2. Memory Service performs structured filtering by user, status, category, and temporal validity — **before** any similarity search runs (`ADD §35.3` — ownership/lifecycle filtering must precede ranking, never follow it).
3. Semantic retrieval obtains candidate memories using vector similarity.
4. Hybrid ranker combines semantic score, lexical/entity match, recency, confidence, explicitness, pinning, and task relevance.
5. Policy layer removes memories not permitted for the current surface/tool/domain.
6. Context compressor converts selected records into concise grounded context with memory IDs/provenance references, capped at the token budget in §20.
7. LLM receives only the bounded context needed for the request.

Scoring function for experimentation: `score = 0.35 × semantic relevance + 0.20 × entity/task match + 0.15 × recency + 0.15 × confidence + 0.10 × explicitness + 0.05 × user pinning` (weights sum to 1.0). These are starting hypotheses to be evaluated against `ADD §19` targets, not hard-coded product truth.

### 6.1 Embedding and index configuration (new — undefined in v0.1)

| Parameter | Value | Rationale |
| --- | --- | --- |
| Embedding dimension | 1,536 | Matches common current-generation embedding models; keeps the `ADD §17.2` capacity math tractable. |
| Index type | HNSW (`m=16`, `ef_construction=64` as a starting point) | Better query-time recall/latency tradeoff than IVFFlat for a corpus that grows continuously with writes, at the cost of slower index builds — acceptable since writes are incremental, not bulk-reload. |
| Distance metric | Cosine | Standard choice for normalized text embeddings; must match the embedding model's training objective. |
| Re-index trigger | Embedding-model version change | Old and new vectors are never mixed in one similarity query; a version column on `MemoryEmbedding` lets retrieval filter to one embedding generation at a time during a rolling re-index. |

## 7. Belief update algorithm

Beliefs are computed views over evidence, not a replacement for evidence. Each proposition has supporting and contradicting evidence. MVP uses rule-based confidence bands rather than pretending to have calibrated Bayesian probabilities.

| Condition | Proposed behavior |
| --- | --- |
| New explicit user confirmation | Strong positive evidence; may set belief to confirmed unless contradicted by newer explicit evidence. |
| Repeated consistent behavior | Moderate positive evidence; keep as inferred. |
| Single model inference | Weak evidence; do not use for consequential behavior. |
| Explicit correction | Strong negative evidence against the superseded proposition; create/update the replacement. |
| Conflicting reliable sources | Set conflict state; reduce confidence; retrieve both sides when material. |
| Stale time-sensitive belief | Decay retrieval priority; require fresh confirmation for consequential use. |

## 8. Agent runtime design

Agent execution is a state machine: `CREATED → PLANNING → READY → RUNNING → WAITING_APPROVAL/WAITING_EXTERNAL → COMPLETED, FAILED, or CANCELLED`. Each transition is persisted in PostgreSQL (§5.1) so work can resume after process failure.

### 8.1 Planning contract

- **Goal:** normalized user objective.
- **Plan:** ordered steps with dependencies.
- **Tool contract:** tool name, operation, required scopes, input schema, output schema.
- **Risk class:** `READ_ONLY`, `REVERSIBLE_WRITE`, `CONSEQUENTIAL_WRITE`, `HIGH_IMPACT`.
- **Approval requirement:** none, per-step, or explicit final confirmation. `CONSEQUENTIAL_WRITE` and `HIGH_IMPACT` always require explicit approval (`FSD FR-AGT-003`).
- **Data disclosure:** fields that will be sent to the external provider.
- **Success condition and rollback/compensation strategy** where available.

### 8.2 Tool execution controls

- Validate tool arguments against a schema after model generation.
- Authorize the exact operation and resource before execution — re-check, never trust a permission decision made at plan time (`FSD BR-006`).
- Never expose raw OAuth refresh tokens or service secrets to the model.
- Use idempotency keys for writes where provider support exists (window: retain idempotency records for 24 hours for standard writes, 7 days for financial/booking-class operations).
- Bound retries (default: 3 attempts, exponential backoff starting at 500ms, capped at 8s) for transient failures.
- Persist external operation IDs for reconciliation.
- Sanitize untrusted tool output before it is reintroduced into the model context.
- Require renewed approval when the plan materially changes after approval.

## 9. API design

| Method / Path | Purpose |
| --- | --- |
| `POST /v1/conversations` | Create conversation. |
| `POST /v1/conversations/{id}/messages` | Send user message; stream assistant result. |
| `GET /v1/memories` | Search/list current memories. |
| `POST /v1/memories` | Create explicit memory. |
| `PATCH /v1/memories/{id}` | Correct, confirm, pin, or suppress memory. |
| `DELETE /v1/memories/{id}` | Delete memory and enqueue downstream cleanup. |
| `GET /v1/beliefs` | List user-visible inferred beliefs where product policy exposes them. |
| `POST /v1/beliefs/{id}/challenge` | Challenge/suppress an inferred belief. |
| `POST /v1/decisions` | Create decision workspace. |
| `POST /v1/decisions/{id}/analyze` | Generate/update decision analysis. |
| `POST /v1/agents/runs` | Create an agent run. |
| `GET /v1/agents/runs/{id}` | Get status/plan/results. |
| `POST /v1/agents/runs/{id}/approve` | Approve a pending step or plan. |
| `POST /v1/agents/runs/{id}/cancel` | Cancel run. |
| `GET /v1/consents` | List consent state. |
| `PUT /v1/consents/{scope}` | Grant/update consent. |
| `DELETE /v1/consents/{scope}` | Revoke consent. |
| `POST /v1/exports` | Create data export. |
| `DELETE /v1/account` | Initiate account deletion. |

### 10.1 API conventions and rate limits (numbers added — undefined in v0.1)

- OAuth/OIDC access token or secure session authenticates the caller.
- All resource IDs are opaque UUID/ULID-class identifiers.
- Mutating endpoints accept idempotency keys where duplicate submission is plausible.
- Errors use stable codes plus human-readable messages and correlation IDs.
- Pagination uses opaque cursors.
- Sensitive fields are omitted by default and require explicit authorized expansion.
- Versioning begins at `/v1`; breaking contract changes require a new major API version.
- **Rate limits (per authenticated user, sliding window):** 60 req/min on `POST /v1/conversations/{id}/messages`; 10 req/min on memory/consent/agent mutation endpoints; 5 req/min on `POST /v1/exports` and `DELETE /v1/account`. Limits are configurable per environment and are a Policy/Consent Service concern, not hard-coded per endpoint, so they can be tuned without a deploy.

## 11. Security design

| Threat | Control |
| --- | --- |
| Cross-tenant data leakage | Mandatory user/tenant predicates in repositories; row-level controls where appropriate; authorization tests. |
| Prompt injection from files/tools | Treat external content as untrusted data; separate instructions from evidence; tool allowlists; output sanitization. |
| Connector credential theft | Tokens stored encrypted in secret store; never logged or sent to LLM. |
| Excessive agent authority | Fine-grained scopes, risk classification, approvals, least privilege, short-lived credentials. |
| Memory poisoning | Provenance, explicit/inferred distinction, confidence, contradiction tracking, user correction. |
| Sensitive data in logs | Structured redaction, allowlisted fields, content-free metrics. |
| Replay/duplicate writes | Idempotency keys, operation IDs, state-machine guards. |
| Model/provider data exposure | Minimum context, provider configuration, contractual/privacy review, routing policy (`ADD §30.2`). |
| Account takeover | MFA-capable identity, session revocation, anomaly/rate controls. |
| Deletion gaps | Data inventory, deletion orchestration, tombstones, verification jobs. |

## 12. Privacy and retention implementation

Data classes have separate retention policies: conversation content (24 months rolling, `FSD §7.3`), durable memories, embeddings, files, agent execution data, security audit data (3 years), and backups (90 days post-deletion-completion). A deletion coordinator owns erasure workflows across PostgreSQL, vector indexes, object storage, caches, and external connector-derived artifacts. Active retrieval must honor deletion immediately even if asynchronous physical erasure is still completing.

## 13. Observability

- Correlation ID spans client request, orchestration, retrieval, model calls, tool calls, and persistence.
- Metrics: request latency, model latency/tokens/cost (`§20`, `ADD §31`), memory retrieval precision proxies, memory mutation rate, tool success, approval rate, agent completion rate, queue lag, deletion SLA.
- Traces record component timing and IDs, not unrestricted private message bodies.
- Security events include failed authorization, unusual connector behavior, bulk export, and deletion actions.
- Model executions retain model identifier, prompt-template version, policy version, and structured-output validation status.

A concrete example trace is given in §27.

## 14. Testing strategy

| Level | Examples |
| --- | --- |
| Unit | Memory classification rules, ranker scoring, consent evaluation, state transitions, redaction. |
| Contract | API schemas, connector adapters, model structured-output schemas. |
| Integration | Conversation→memory write; retrieval→response; agent→approval→tool; deletion across stores. |
| Security | IDOR/cross-user access, prompt injection, SSRF/tool misuse, token leakage, rate-limit bypass. |
| AI evaluation | Memory relevance, false-memory rate, contradiction handling, grounding, decision transparency, tool selection (targets in `ADD §19`). |
| Load | Concurrent streaming conversations, vector retrieval, queue throughput, long-running agents. |
| Resilience | Provider outage, queue restart, DB failover, duplicate events, partial deletion failure. |
| User acceptance | Onboarding clarity, memory control, decision flow, approval comprehension. |

## 15. Deployment and delivery

Separate development, staging, and production environments with isolated databases, secrets, and connector credentials. Infrastructure is defined as code. CI performs linting, tests, dependency/security scanning, and migration checks. CD deploys progressively (canary at 5% → 25% → 100% of traffic, with automated rollback on error-rate or latency regression) with health checks. Database migrations are backward-compatible during rolling deployment. Feature flags gate new memory and agent behaviors.

## 16. Runtime request and response contracts

Every request is normalized into a request context containing:

| Field | Purpose |
| --- | --- |
| `principal_id` | Authenticated user or service principal making the request. |
| `tenant_id` | Isolation boundary used in every repository and event. |
| `correlation_id` | Joins client, API, model, queue, and connector telemetry. |
| `idempotency_key` | Prevents duplicate mutation when a client retries. |
| `locale` and `timezone` | Supports deterministic presentation and time interpretation. |
| `consent_snapshot` | Records the policy basis used for this operation. |

The response envelope provides a stable status, a typed result, an error code when applicable, a correlation ID, and pagination/continuation information when the operation is incomplete. Streaming endpoints emit explicit `started`, `delta`, `tool_status`, `approval_required`, `completed`, and `failed` events. Clients must be able to safely reconnect and determine whether the final response was already persisted.

## 17. Persistence and transaction boundaries

Canonical mutations use a database transaction whenever related records must change atomically — e.g., correcting a memory updates its status, creates the replacement relationship, and writes the audit reference in one transaction. Expensive work such as embedding generation, file parsing, or provider calls never runs inside that transaction.

The outbox pattern is used for events that must be published after a successful commit: an outbox row is created in the same transaction as the domain mutation, and a worker publishes it and records delivery status. Consumers must be idempotent because delivery may be repeated. This avoids the failure mode where the database commits but a memory-index or deletion event is lost.

Repositories require a user/tenant scope as an input rather than relying on callers to remember an additional filter. Tests exercise empty, mismatched, deleted, and cross-user identifiers.

## 18. Database and index implementation guidance

Use foreign keys, check constraints, unique constraints, and timestamp/status invariants for safety that does not depend on model behavior. Recommended indexes: owner+status on user-scoped entities, conversation+creation-time for messages, active-memory lookup keys, agent-run+state, consent-scope+current-status. Query plans are reviewed before introducing broad semantic retrieval.

Embeddings include the source record ID, owner/tenant key, embedding-model version, content hash, sensitivity classification, index status, and deletion timestamp where relevant. The retrieval query filters ownership and active status **before** similarity ranking; similarity is never a substitute for authorization (`§6`, step 2). Re-indexing is resumable and safe to run concurrently with normal writes.

**Connection pooling (new — undefined in v0.1):** use PgBouncer in transaction-pooling mode; size the pool at roughly `(number of API/worker instances × max concurrent DB-bound requests per instance)`, starting at 100 server-side connections for the pilot scale in `ADD §17.1`, reviewed at each capacity re-check.

## 19. API error model and idempotency

API errors use stable machine-readable codes: `VALIDATION_ERROR`, `NOT_FOUND`, `FORBIDDEN`, `CONSENT_REQUIRED`, `CONFLICT`, `DEPENDENCY_UNAVAILABLE`, `POLICY_DENIED`, `RETRYABLE_OPERATION_UNKNOWN`. Human-readable text may change, but clients branch on the code and HTTP status.

Mutation endpoints persist idempotency results for a bounded period appropriate to the operation (§8.2 gives concrete windows for tool calls; ordinary API mutations default to 24 hours). A repeated key with the same request fingerprint returns the original result; reusing a key for a different payload returns a conflict. External writes additionally persist provider operation IDs so an uncertain timeout can be reconciled before another attempt.

## 20. Model gateway implementation

The model gateway is the only application boundary allowed to invoke an external model provider. It should:

1. Select a provider and model using task, region, data-classification, availability, cost, and latency policy.
2. Resolve a versioned prompt template and system policy.
3. Assemble only the approved context fields and mark evidence as data, not instructions.
4. Enforce token, timeout, and output-size budgets: **target context budget of ≤8K tokens of retrieved personal context per request**, reserving headroom against typical 128K-token provider context windows for conversation history and system instructions; **request timeout budget of 10s for interactive chat, 60s for background extraction/analysis jobs.**
5. Validate structured output against a schema and reject or repair only through bounded, observable logic (max 1 repair attempt before surfacing a recoverable failure).
6. Return model metadata, usage, provider request ID, and policy version without exposing secrets or unrestricted prompts to ordinary logs.

Provider fallback must be task-compatible and privacy-compatible (`ADD ADR-012`). A provider with different retention, region, or tool behavior is not a valid fallback merely because it is available.

## 21. Minimal schema DDL sketch (new — v0.1 gave fields with no types)

This is illustrative, not a migration file — actual migrations live in the codebase and are the source of truth. It exists so the data model in §4 is reviewable as something implementable.

```sql
create table users (
    user_id uuid primary key default gen_random_uuid(),
    status text not null default 'active' check (status in ('active','suspended','deleted')),
    locale text not null default 'en-US',
    timezone text not null default 'UTC',
    created_at timestamptz not null default now()
);

create table memories (
    memory_id uuid primary key default gen_random_uuid(),
    user_id uuid not null references users(user_id),
    type text not null check (type in
        ('fact','preference','goal','relationship','event','routine',
         'constraint','project_context','user_instruction')),
    canonical_text text not null,
    explicitness text not null check (explicitness in ('explicit','inferred')),
    confidence numeric(3,2) not null check (confidence between 0 and 1),
    sensitivity_tier text not null check (sensitivity_tier in ('T0','T1','T2','T3')),
    status text not null default 'candidate'
        check (status in ('candidate','active','requires_confirmation','suppressed','superseded','deleted')),
    valid_from timestamptz not null default now(),
    valid_to timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
create index idx_memories_user_status on memories (user_id, status);

create table memory_embeddings (
    memory_id uuid not null references memories(memory_id),
    embedding_model text not null,
    embedding_dim int not null default 1536,
    vector vector(1536) not null,
    indexed_at timestamptz not null default now(),
    primary key (memory_id, embedding_model)
);
create index idx_memory_embeddings_hnsw
    on memory_embeddings using hnsw (vector vector_cosine_ops)
    with (m = 16, ef_construction = 64);

create table agent_runs (
    run_id uuid primary key default gen_random_uuid(),
    user_id uuid not null references users(user_id),
    goal text not null,
    status text not null check (status in
        ('created','planning','ready','running','waiting_approval',
         'waiting_external','completed','failed','cancelled')),
    plan_version int not null default 1,
    started_at timestamptz not null default now(),
    completed_at timestamptz
);
create index idx_agent_runs_user_status on agent_runs (user_id, status);
```

## 22. Queue, worker, and workflow behavior

Jobs declare a type, owner, attempt number, visibility timeout, maximum attempts, and deduplication key. Workers acknowledge a job only after its durable state transition succeeds. Dead-letter queues retain the reason, payload reference, and correlation ID while applying the same privacy controls as normal logs.

Long-running agent and deletion workflows persist a checkpoint after each meaningful transition. Timers, approvals, retries, and compensation steps are represented as data so a worker restart cannot lose the workflow. Administrative replay requires an explicit operator action and must not bypass current authorization or deletion tombstones.

## 23. File ingestion and untrusted content

Uploads use short-lived signed upload URLs where possible, enforce size (50MB default, `ADD §17.1`) and content-type limits, scan for malware, and assign a quarantine status before parsing. Parsers treat documents, metadata, OCR text, spreadsheets, and tool responses as untrusted content. Extracted chunks inherit the source owner, consent scope, sensitivity, and deletion lifecycle.

Chunking and embedding are asynchronous. A failed parse is visible as a failed ingestion rather than silently producing an empty source. The model may use extracted text only after the ingestion record is authorized and indexed; text inside a file cannot grant a connector permission or override system policy.

## 24. Security and privacy control points

| Point | Required checks |
| --- | --- |
| API ingress | Authentication, input schema, rate limits (§10.1), CSRF/session protection where applicable. |
| Repository access | Owner/tenant scope, resource status, operation authorization. |
| Context assembly | Consent, sensitivity, purpose, temporal validity, minimum necessary fields. |
| Model gateway | Provider policy, prompt/version controls, output schema, redacted telemetry. |
| Tool execution | Exact operation, connector grant, resource scope, risk and approval state. |
| Data lifecycle | Revocation/deletion tombstones, derivative cleanup, backup policy. |
| Operations | Break-glass access, immutable audit, secret rotation, alerting. |

Defense in depth matters because a defect in a model prompt, retrieval query, or UI check must not become the only barrier protecting private data.

## 25. Configuration, secrets, and feature flags

Configuration distinguishes non-secret operational settings, provider settings, policy versions, and secrets. Secrets are injected through the environment's secret manager, rotated without source changes, and excluded from logs, error messages, traces, and model context. Local development may use documented placeholder credentials, but production startup rejects placeholders.

Feature flags gate high-risk behaviors such as inferred-memory storage, new connectors, autonomous retries, and model-provider routing. A flag change is auditable, scoped by environment or cohort, and reversible. Flags must not be used to bypass authorization or deletion controls.

## 26. On-call runbook example: vector index rebuild (new)

v0.1 asserted "re-indexing must be resumable" without ever showing what that means operationally. Example runbook, illustrating the required shape for any operational procedure in this system:

1. **Trigger:** embedding model version bump, or index corruption alert.
2. **Precondition check:** confirm the new embedding model has passed the `ADD §19` evaluation targets on a shadow sample before rebuilding production.
3. **Execution:** background worker walks `memories` in `(user_id, memory_id)` batches of 500, generates embeddings under the new model version, writes to `memory_embeddings` with the new `embedding_model` value — **the old rows are not deleted until the new index is verified**, so retrieval can keep serving the old generation throughout.
4. **Cutover:** once coverage reaches 100% and a sampled precision check passes, retrieval switches to filter on the new `embedding_model` value; old rows are deleted after a 7-day safety window.
5. **Rollback:** if precision regresses post-cutover, flip retrieval back to the prior `embedding_model` value immediately — no data was lost because old vectors were retained through the safety window.
6. **Alerting:** job owner is paged if the batch walk stalls for >30 minutes or the error rate on embedding calls exceeds 2%.

## 27. Example request trace (new)

Illustrates §13's observability requirements concretely for `POST /v1/conversations/{id}/messages`:

```
correlation_id=c-8f2a
  → api-ingress       [12ms]  auth ok, rate-limit ok
  → orchestrator       [4ms]  classify: retrieval-eligible
  → memory-service    [38ms]  filter(user=U1, status=active) → 240 candidates
                              → vector search (top 20) → policy filter → 6 selected
  → model-gateway     [910ms] provider=X, model=Y, prompt_v=14, tokens_in=1840, tokens_out=310
                              structured-output: valid
  → conversation-svc   [6ms]  persist response, model_execution_id=m-771
  → outbox              [—]   enqueue interaction-completed event
  total: 970ms (within NFR-002 P50 target)
```

No message body appears in the trace itself — only IDs, counts, timings, and policy decisions, per `§13` and `ADD §33` observability-without-surveillance principle.

## 28. Migration, backup, and recovery procedures

Schema migrations are additive and backward-compatible across the deployment window: add nullable fields or new tables, deploy code that supports both versions, backfill in bounded batches, then enforce constraints after verification. Destructive changes require a reviewed rollback or restore plan.

Backups are encrypted, access-controlled, monitored, and tested by restoring into an isolated environment (quarterly drill, `FSD NFR-005`). Recovery objectives are recorded separately for core conversation data, memory indexes, files, audit events, and asynchronous workflow state. Rebuilding a derivative index from canonical data is preferred to treating a backup of the index as the only recovery path.

## 29. Technical definition of done

A technical capability is complete only when its happy path, failure path, authorization path, privacy lifecycle, observability, and rollback behavior are defined. The implementation includes:

- versioned API/schema or event contracts;
- owner-scoped persistence and migration;
- structured logs and metrics with redaction;
- unit, integration, and security tests appropriate to the risk;
- retry/idempotency behavior for asynchronous or external operations;
- feature-flag and configuration behavior for staged rollout;
- operational documentation for alerting, replay, recovery, and deletion (§26 gives the required shape);
- model/prompt/provider version traceability where AI is involved.

## 30. Technical decisions still requiring validation

The proposed stack remains intentionally provider-neutral where it matters and concrete where a number was missing and blocking (embedding dimension, rate limits, token budgets, pool sizing — all now set in this revision). Before production selection, the team should validate PostgreSQL/pgvector query performance against the `ADD §17.2` worked estimate with representative memory volume, choose the identity/session approach, confirm the queue/workflow product, define data residency and provider-retention requirements (`ADD §22`, §30.2), and test the cost and latency of the model gateway against the `ADD §31` cost model. These decisions are captured as ADR updates with measured evidence, not preference alone.

## 31. Technical theory and implementation rationale

The technical design translates product trust principles into enforceable runtime behavior. The most important distinction is between canonical state and derived or speculative state. Canonical records — users, consent, messages, memories, decisions, approvals, agent transitions — require transactional integrity. Embeddings, caches, summaries, rankings, and model suggestions are derived artifacts and must be reproducible, versioned, and disposable.

### 31.1 Request context as a security boundary

`principal_id`, `tenant_id`, correlation data, idempotency information, and the consent snapshot are the minimum context needed to interpret an operation safely. Passing this context through repositories, jobs, model calls, and connector adapters prevents a background worker from losing the identity or purpose under which work was authorized. A missing scope is a hard error, not an implicit global query.

### 31.2 Transactions and asynchronous work

Transactions protect related canonical changes; queues protect responsiveness and isolate slow or unreliable dependencies. The outbox pattern connects them: commit the domain mutation and its pending event together, then deliver the event asynchronously. Consumers must be idempotent because at-least-once delivery is safer and more operationally realistic than assuming exactly-once execution.

### 31.3 Retrieval is authorization plus relevance

Semantic similarity only estimates usefulness. It does not establish ownership, consent, freshness, sensitivity permission, or whether the record is active. Retrieval must first constrain the candidate set by security and lifecycle rules, then rank the remaining records by task relevance (`§6`, step 2) — this ordering prevents a highly similar but deleted, private, stale, or cross-user record from entering the model context.

### 31.4 Structured model output and bounded autonomy

Schemas make model output testable, but schemas do not make it true. Candidate memories, beliefs, decisions, and plans require validation, provenance, policy evaluation, and sometimes user confirmation. Retries and repair prompts must be bounded (§20, step 5) because repeated generation can turn a malformed result into an unobservable loop. Autonomy is bounded by the tools, scopes, risk classes, budgets, and state transitions that application code controls.

### 31.5 External operations and uncertainty

Distributed systems cannot always tell whether a timed-out external write happened. The design records an operation ID before execution, uses provider idempotency where available, and reconciles unknown outcomes before retrying. The user-facing state should say "outcome needs confirmation" rather than falsely reporting failure or success — especially important for messages, bookings, payments, deletions, and other irreversible actions.

### 31.6 Data lifecycle as an implementation concern

Retention, revocation, correction, export, and deletion are data flows across every store, not single-row operations. The same owner, classification, status, and source identifiers travel with database records, vector chunks, objects, queue payloads, caches, logs, and provider references. Tombstones and lifecycle ledgers ensure delayed work cannot recreate data that a user has deleted.

### 31.7 Observability without surveillance

The system needs enough telemetry to explain latency, authorization, model versions, retrieval decisions, retries, and failures — not unrestricted copies of private conversations in logs (§27 is a worked example). Allowlisted metadata, content hashes, redacted fields, sampled traces, and protected audit records provide operational evidence while reducing accidental exposure. Access to exceptional diagnostic content must itself be authorized and audited (`ADD §12.2`).

### 31.8 Technical invariants

1. Every query and job is scoped to an owner or tenant.
2. Every external model or tool call has a policy decision.
3. Every durable mutation has an audit reference and lifecycle state.
4. Every retry has a bounded policy and a duplicate-protection key.
5. Every derivative index can be invalidated and rebuilt (§26).
6. Every asynchronous workflow can resume or fail visibly.
7. Every secret is excluded from prompts, logs, client responses, and ordinary telemetry.
8. Every breaking contract or model/prompt change is versioned and traceable.

## 32. Cross-document implementation traceability

The three design documents are used together, not as independent descriptions. The `FSD` defines what the user can expect; the `ADD` defines where trust and responsibility reside; this document defines how those responsibilities become schemas, state transitions, APIs, jobs, and tests. For example, the functional requirement that a user can delete a memory (`FSD FR-MEM-010`) maps to the architecture's privacy gates and lifecycle ownership (`ADD §13`, §25), then to this document's tombstones, outbox events, index cleanup, repository filters (§17, §18), and deletion verification tests (§14).

Any implementation change that alters user-visible behavior updates the corresponding requirement and acceptance evidence. Any change to trust boundaries, canonical ownership, lifecycle guarantees, or provider behavior updates the architecture decision record and this technical contract. This traceability prevents documentation from describing a safer system than the code actually implements.

## 33. Technical section interpretation guide

The technical design turns the functional contract and architecture principles into implementable mechanisms. Technology choices are proposed baselines; the invariants, ownership rules, lifecycle guarantees, and security controls are the durable requirements.

**Objectives and technology baseline.** The objective is provider-independent personalization with explicit control over data and actions. PostgreSQL is canonical because relational integrity matters more than premature specialization; Redis is ephemeral support infrastructure only (§5.1); object storage holds large artifacts; pgvector is a derivative retrieval index (§6.1).

**Service decomposition.** The listed services are responsibility boundaries — who owns a rule and where a mutation should occur — not a mandate for immediate network separation.

**Data model and lifecycle.** Entities represent business meaning, not just model output. Foreign keys and status constraints protect canonical relationships; provenance and timestamps support correction and explanation; owner keys protect isolation (§21 shows this concretely).

**Memory, retrieval, and belief processing.** Memory writing favors precision and policy compliance. Retrieval favors authorized relevance over maximum similarity. Belief processing preserves supporting and contradictory evidence instead of hiding disagreement behind one score.

**Agent runtime and API behavior.** The agent state machine makes long-running work truthful and recoverable. Streaming is a transport optimization, not proof that work completed — the durable message or run record is the source for reconnect, refresh, audit, and support workflows.

**Security, privacy, and observability.** Security controls are layered: ingress validation, repository scoping, context filtering, gateway policy, connector authorization, secret management, and lifecycle enforcement.

**Testing, delivery, and operations.** Unit tests validate local rules; contract tests protect boundaries; integration tests validate lifecycle flows; security tests challenge isolation and authority; AI evaluations measure quality; load and resilience tests validate operational assumptions.

**Technical change rule.** Any change to a model provider, prompt, embedding model, schema, connector, retention policy, or authorization rule can affect user trust. Such changes require a version, owner, migration or rollback plan, evaluation evidence, and an update to the relevant functional and architecture documentation.
