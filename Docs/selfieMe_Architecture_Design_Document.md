selfie.Me

Architecture Design Document

Draft v0.1 --- Working baseline / hypotheses to validate

Source basis: Company Documentation Pack - Initial v0.1. Detailed
architecture below is a proposed baseline requiring validation.

# PART III --- ARCHITECTURE DESIGN DOCUMENT (ADD)

## 23. Architecture Drivers

| Driver \| Architectural consequence \|

| --- \| --- \|

| Long-term personalization \| Dedicated memory/belief layers rather
  than raw chat replay. \|

| User trust/control \| Provenance, correction, deletion, consent and
  audit are first-class. \|

| Agentic execution \| Durable workflow state, fine-grained
  authorization and approval boundaries. \|

| LLM uncertainty \| Structured outputs, grounding, deterministic policy
  layer and provider abstraction. \|

| Privacy \| Data minimization, service boundaries, encrypted stores and
  controlled context assembly. \|

| Evolution \| Modular services and versioned contracts allow models,
  retrieval and tools to change independently. \|

| MVP speed \| Begin as a modular monolith or small service set;
  preserve logical boundaries before physical microservice separation.
  \|

### 23.1 What an architecture driver means

An architecture driver is a product goal, risk, constraint, or quality
expectation that influences the structure of the system. It answers:
“What must the architecture protect or make possible, even when
implementation details change?” A driver is not a feature by itself. It
is the reason for choosing a particular boundary, data model, workflow,
or technology approach.

These drivers are important for selfie.Me because the product does more
than generate chat responses. It stores personal context, forms
uncertain inferences, supports decisions, and may act through external
services. The architecture must therefore balance usefulness with
privacy, safety, user control, and the ability to recover from errors.

### 23.2 Explanation of each driver

**Long-term personalization.** The product should become more helpful
over time without sending every historical conversation to the model.
Personal context therefore needs dedicated memory, evidence, belief,
and retrieval layers. This allows the system to distinguish an explicit
fact from an inference, find only relevant context, correct outdated
information, and delete it from active use.

**User trust and control.** Users need to understand what the system
knows, why it used that information, and how to change or remove it.
Provenance, correction, deletion, consent, status, and audit are
therefore core architecture capabilities. A response that is accurate
but impossible to explain or correct does not satisfy this driver.

**Agentic execution.** An agent task can involve multiple steps,
external systems, delays, retries, approvals, and uncertain outcomes.
The model must not be treated as an authority that can directly perform
any action it describes. Durable workflow state, risk classification,
fine-grained permissions, idempotency, cancellation, approval gates,
and reconciliation are required to make action safe.

**LLM uncertainty.** Models are useful for interpretation, planning,
classification, and language generation, but they can hallucinate,
follow instructions embedded in untrusted content, or return malformed
output. Structured output schemas, grounding, deterministic policy
checks, bounded retries, evaluation, and a provider abstraction ensure
that model output is treated as a proposal rather than unquestioned
truth.

**Privacy.** Conversations, memories, files, beliefs, and connector
credentials have different sensitivity and disclosure risks. Data must
be minimized and used only for the purpose and scope authorized by the
user. This leads to data classification, encrypted stores, scoped
credentials, retention controls, and separate write, retrieval, and
disclosure gates.

**Evolution.** Models, embedding providers, retrieval algorithms,
connectors, and workflows will change at different speeds. Modular
domains, versioned APIs and events, a model gateway, rebuildable
derivative indexes, feature flags, and migration paths allow one part
to change without rewriting the entire product.

**MVP speed.** The founder pilot needs fast learning and low operational
overhead. A modular monolith or small service set is therefore
preferred initially. This is not permission to create an unstructured
codebase: logical ownership, repository boundaries, contracts, policy
checks, and observability should exist before physical microservice
separation.

### 23.3 How the drivers guide decisions

The drivers are used during architecture reviews and trade-offs. If two
solutions both satisfy the functional requirements, prefer the one that
preserves the drivers with less operational complexity. For example, a
single canonical database is acceptable for the MVP when each domain
owns its tables and all repositories enforce user scope. Splitting the
database too early may add deployment complexity without improving the
actual privacy boundary.

For irreversible or externally visible behavior, the practical priority
is:

1. User safety, authorization, privacy, and deletion rights.
2. Correctness, provenance, and recoverability.
3. Reliability and observability.
4. Performance and user experience.
5. Cost and implementation speed.

This means speed or cost must not be achieved by expanding model
authority, retaining deleted data in active retrieval, or making an
external change without a clear authorization decision.

### 23.4 Driver-to-quality scenarios

| Driver \| Example scenario \| Evidence of success \|

| --- \| --- \| --- \|

| Long-term personalization \| A user corrects an old preference. \|
  Future retrieval uses the correction and excludes the superseded
  value. \|

| User trust/control \| A user asks why a response used a memory. \|
  The system can show an appropriate provenance reference and status.
  \|

| Agentic execution \| A worker restarts during a connector operation.
  \| The run resumes or reconciles without duplicating a consequential
  action. \|

| LLM uncertainty \| A file contains instructions to export private
  data. \| The file is treated as untrusted content and cannot grant
  export authority. \|

| Privacy \| A connector grant is revoked while work is queued. \| The
  queued operation is blocked and the credential is invalidated. \|

| Evolution \| The embedding provider is replaced. \| Canonical
  memories remain intact and the index can be rebuilt. \|

| MVP speed \| A new feature is piloted by a small user cohort. \| A
  feature flag enables staged rollout without bypassing core policy. \|

### 23.5 Architecture driver decision rule

For each significant architecture decision, record which drivers it
supports, what trade-off it introduces, what failure mode it prevents,
and how the decision will be validated. A driver is useful only when it
changes behavior that can be reviewed, tested, or measured; it should
not remain a list of general aspirations.

## 50. Architecture section interpretation guide

The architecture document explains how the system is shaped and why
its boundaries exist. It is not a promise that every logical component
must become a separate deployable service. The design should be read in
terms of responsibilities, authority, data ownership, and trust
boundaries.

### 50.1 System context and logical architecture

The system context identifies what is inside selfie.Me's control and
what is external. The logical architecture then groups responsibilities
into planes so that user experience, intelligence, personal context,
actions, governance, data, and operations can evolve independently.
The planes are conceptual boundaries: they clarify dependencies and
authority even when the initial implementation runs in one process.

### 50.2 Physical evolution

Physical deployment should follow evidence. A modular monolith is
appropriate while the team is learning because it simplifies
transactions, debugging, and release management. Components should be
extracted when they have a distinct scaling profile, reliability need,
security boundary, or ownership model. Extraction without a measurable
reason adds network failure modes and operational cost.

### 50.3 Personal context architecture

The four context layers prevent a common failure in personal AI:
mistaking generated interpretation for user truth. Evidence preserves
source material, memories preserve governed statements, beliefs
preserve uncertainty, and retrieval views provide only task-specific
context. Each layer has different retention, correction, visibility,
and authorization rules.

### 50.4 Agent architecture and trust boundaries

The planner can suggest but not authorize. The policy gate can permit
or deny but should not invent a user goal. The executor can call only
the approved connector operation. The observer records what happened
and whether the next step remains valid. Trust boundaries make these
responsibilities enforceable and ensure untrusted client, file, model,
and provider content cannot directly expand authority.

### 50.5 Data, resilience, security, and privacy

Canonical data must remain durable, scoped, and recoverable.
Derivative indexes, caches, and summaries improve performance but
cannot become the source of truth. Resilience means more than retries:
the system must preserve state, avoid duplicate external effects,
reconcile uncertain outcomes, and prevent delayed events from
recreating deleted information. Security and privacy controls belong at
every boundary because no single filter is guaranteed to remain
correct forever.

### 50.6 Deployment, capacity, and failure planning

Deployment topology describes network and workload relationships.
Capacity assumptions are hypotheses to validate with telemetry, not
guarantees. Failure-mode tables describe the expected behavior when
dependencies are unavailable or partially successful. A production
architecture is credible only when it includes alerts, operator
runbooks, backup restoration, replay controls, deletion verification,
and a safe degraded mode.

### 50.7 Evaluation and traceability

Evaluation connects architecture to outcomes. Memory precision,
contradiction safety, grounding, approval quality, and privacy
correctness should be measured using representative scenarios rather
than only infrastructure metrics. The traceability matrix ensures that
each product capability has an owning component, a policy boundary, a
data representation, and a testable implementation path.

## 24. System Context

The end user interacts with selfie.Me through a client application.
selfie.Me authenticates the user, stores user-controlled data, calls one
or more model providers through a model gateway, optionally accesses
third-party services through connectors, and stores files in object
storage. External services are outside the trust boundary and receive
only the data required for an authorized operation.

Context diagram (logical):

User → Client → selfie.Me API/Orchestrator → {Memory & Belief, Decision,
Agent Runtime, Policy/Consent, Files} → Model Gateway / Connectors →
External AI & Third-Party Services

## 25. Logical Architecture

| Plane \| Components \| Purpose \|

| --- \| --- \| --- \|

| Experience plane \| Web/mobile clients, streaming gateway \| User
  interaction and presentation. \|

| Intelligence plane \| Orchestrator, model gateway, prompt registry,
  evaluators \| Reasoning and model mediation. \|

| Personal context plane \| Memory service, belief service,
  retrieval/index \| Durable personalized understanding. \|

| Decision plane \| Decision service, evidence snapshotting \|
  Structured decision support. \|

| Action plane \| Agent runtime, tool registry, connector adapters \|
  Authorized external execution. \|

| Governance plane \| Identity, authorization, consent, policy, audit \|
  Trust, privacy and control. \|

| Data plane \| PostgreSQL, vector index, object store, cache,
  event/queue \| Persistence and asynchronous processing. \|

| Operations plane \| Telemetry, feature flags, configuration, CI/CD \|
  Reliability and safe evolution. \|

## 26. Recommended Physical Evolution

### 26.1 MVP: modular monolith + workers

For the founder pilot, deploy one primary application with strong
internal modules for conversation/orchestration, memory, beliefs,
decisions, policy and APIs; separate asynchronous workers handle
embeddings, ingestion, deletion and agent tasks. PostgreSQL/pgvector,
Redis and object storage are shared infrastructure. This minimizes
operational complexity while preserving clean interfaces.

### 26.2 Scale-out triggers

-   Separate Agent Runtime when long-running jobs materially affect API
    reliability.

-   Separate Model Gateway when multiple products/providers require
    independent scaling and governance.

-   Separate Memory/Retrieval when index size, retrieval QPS or
    specialized storage warrants it.

-   Separate Connector Service when credential/security boundary or
    provider count grows.

-   Adopt a dedicated workflow engine when retries, timers, approvals
    and compensations become operationally complex.

-   Adopt a dedicated vector database only when pgvector no longer meets
    latency, scale or isolation requirements.

## 27. Personal Context Architecture

The personal context architecture has four distinct layers: raw
evidence, memories, beliefs and retrieval views. Raw evidence is the
original authorized source. A memory is a normalized durable statement
tied to evidence. A belief is an inferred proposition supported or
contradicted by evidence. A retrieval view is a task-specific selection
of current memories/beliefs that is safe to expose to a model.

| Layer \| Mutable? \| Primary truth? \| Example \|

| --- \| --- \| --- \| --- \|

| Evidence \| Append/retention governed \| Yes, as source record \| A
  user message or uploaded document reference. \|

| Memory \| Correctable/supersedable \| Canonical personal context \|
  User explicitly prefers concise emails. \|

| Belief \| Continuously revisable \| No; inference \| User may prefer
  concise professional communication. \|

| Retrieval view \| Ephemeral \| No \| Three relevant preferences
  selected for drafting an email. \|

## 28. Agentic AI Architecture

The agent system is intentionally split into Planner, Policy Gate,
Executor and Observer. The Planner proposes steps but has no authority
to execute. The Policy Gate deterministically checks identity, scopes,
risk and approval. The Executor invokes tools using scoped credentials.
The Observer persists state and interprets tool results for the next
step. This separation limits the damage of model mistakes or prompt
injection.

### 28.1 Agent sequence

1.  Request enters Orchestrator with authenticated user context.

2.  Planner creates structured plan.

3.  Policy Gate evaluates every planned operation.

4.  Low-risk authorized reads execute; approval-required steps pause.

5.  User approves exact operation/data scope.

6.  Executor obtains scoped credential and calls connector.

7.  Result is sanitized and persisted.

8.  Planner/Observer determines whether next step is still valid.

9.  Run completes with audit summary.

## 29. Trust Boundaries

| Boundary \| Trust assumption \| Required controls \|

| --- \| --- \| --- \|

| Client ↔ API \| Client is untrusted. \| Authentication, CSRF/session
  controls, validation, rate limiting. \|

| API ↔ Internal services \| Authenticated service identity but least
  privilege. \| mTLS/service identity or equivalent, authorization,
  network policy. \|

| Application ↔ Data stores \| Stores contain private data. \|
  Encryption, private networking, scoped DB roles, backups. \|

| Orchestrator ↔ LLM provider \| Provider is external processing
  boundary. \| Minimum data, routing policy, contractual/privacy
  controls, no secrets. \|

| Agent ↔ Connector \| Third-party API is untrusted/external. \| Scoped
  OAuth, schema validation, approvals, idempotency. \|

| Files/tool output ↔ Model \| Content may contain adversarial
  instructions. \| Content/instruction separation, sanitization, tool
  policy. \|

## 30. Data Architecture

PostgreSQL is the system of record for identities, memory
metadata/content, beliefs, decisions, consent and agent state. Vector
representations are derivative indexes that can be rebuilt from
authorized source records. Object storage holds files and exports. Redis
is non-authoritative ephemeral state. Events/queues connect write paths
to asynchronous enrichment and lifecycle workflows.

### 30.1 Data ownership rules

-   Each domain owns writes to its canonical tables even if deployed in
    one database initially.

-   Derivative stores never become the sole copy of user data.

-   Every user-scoped record includes an immutable owner/tenant key.

-   Foreign keys or equivalent application invariants maintain
    referential integrity.

-   Sensitive connector secrets are referenced from a secrets system,
    not stored as ordinary application columns.

-   Embeddings inherit the privacy/deletion classification of their
    source memory/chunk.

## 31. Availability and Resilience Architecture

-   Stateless request handlers can scale horizontally.

-   Streaming responses degrade gracefully if secondary enrichment is
    unavailable.

-   Memory writes may be asynchronous after the user response, but
    explicit memory-management operations are synchronous for
    user-visible state.

-   Agent runs persist after every meaningful transition and can resume
    after worker restart.

-   Queues use dead-letter handling and replay-safe consumers.

-   Model gateway supports provider/model fallback only for compatible
    tasks and records the substitution.

-   Backups are encrypted and restore procedures are tested.

-   Deletion tombstones prevent re-indexing deleted content from delayed
    events.

## 32. Security Architecture

Authorization is evaluated at resource and operation level.
Authentication alone never grants access to a memory or connector.
Service identities receive only required database, queue and secret
permissions. High-value administrative operations require stronger
controls and are audited. Production support access should use
break-glass mechanisms with explicit reason and traceability rather than
routine plaintext browsing.

### 32.1 Encryption

-   TLS 1.2+ or platform-equivalent secure transport for all network
    paths.

-   Managed encryption at rest for databases, object storage, queues and
    backups.

-   Envelope encryption/KMS for especially sensitive application
    secrets.

-   Connector tokens encrypted separately and rotated/revoked according
    to provider capabilities.

-   Key access separated from ordinary application administration.

## 33. Privacy Architecture

Privacy controls operate before storage, before retrieval and before
disclosure. The write gate determines whether information can become
durable. The retrieval gate determines whether a stored item may be used
in a particular context. The disclosure gate determines whether selected
information may be sent to a model or third-party tool. This three-gate
model prevents 'stored therefore usable everywhere' behavior.

## 34. AI Safety and Grounding Architecture

| Risk \| Architectural mitigation \|

| --- \| --- \|

| Hallucinated personal fact \| Only governed memory/evidence is
  injected as personal truth; inferred beliefs are labeled. \|

| Stale memory \| Temporal validity, last-confirmed timestamps and
  recency-aware retrieval. \|

| Contradiction \| Conflict state and evidence preservation; current
  explicit instruction wins for immediate task. \|

| Over-personalization \| Relevance threshold and bounded context; do
  not inject unrelated memories. \|

| Prompt injection \| External text cannot grant tool permissions;
  planner output is checked by deterministic policy. \|

| Unsafe autonomous action \| Risk classes, approvals, scoped
  credentials, cancellation and audit. \|

| Opaque decision advice \| Evidence/assumption/preference separation
  and decision snapshots. \|

| Model drift \| Versioned model/prompt registry plus recurring
  evaluation suites. \|

## 35. Architecture Decision Records (Initial)

| ADR \| Decision \| Reason \|

| --- \| --- \| --- \|

| ADR-001 \| Use a modular monolith for founder pilot. \| Maximize
  delivery speed while maintaining domain boundaries. \|

| ADR-002 \| Use PostgreSQL as canonical data store. \| Transactional
  integrity and broad operational maturity. \|

| ADR-003 \| Use pgvector initially. \| Avoid premature dedicated vector
  infrastructure. \|

| ADR-004 \| Separate memories from beliefs. \| Prevents inference from
  masquerading as user truth. \|

| ADR-005 \| Treat embeddings as derivative data. \| Supports deletion,
  rebuild and model migration. \|

| ADR-006 \| Place all model calls behind an internal gateway. \|
  Provider portability, policy enforcement and observability. \|

| ADR-007 \| Use deterministic policy checks around agent actions. \|
  LLMs should propose actions, not authorize themselves. \|

| ADR-008 \| Persist agent state as a durable state machine. \| Supports
  retries, approvals and recovery. \|

| ADR-009 \| Require provenance for durable personal context. \| Enables
  correction, conflict handling and trust. \|

| ADR-010 \| Use three privacy gates: write, retrieval, disclosure. \|
  Storage consent alone is insufficient for contextual use and external
  sharing. \|

## 36. Deployment Topology

Initial production topology: CDN/WAF → web client/API ingress →
application instances → PostgreSQL/pgvector + Redis + object storage;
asynchronous queue → worker pool; application/worker → model gateway →
external model providers; agent executor → connector adapters →
third-party APIs. Observability receives redacted telemetry from every
internal component. Secrets/KMS is reachable only by workloads requiring
credentials.

## 37. Capacity and Scalability Assumptions

| Area \| MVP assumption \| Scale strategy \|

| --- \| --- \| --- \|

| Users \| Founder pilot to low tens of thousands \| Horizontal
  API/workers; connection pooling. \|

| Memories/user \| Hundreds to low thousands \| Hybrid indexed
  retrieval; partition/index tuning. \|

| Conversations \| Potentially high append volume \| Partition messages
  by time/user when needed; archive cold data. \|

| Agent runs \| Low relative to chat traffic \| Independent worker pools
  and concurrency limits. \|

| Files \| Moderate; bounded upload sizes \| Direct-to-object-storage
  upload, async parsing. \|

| Model calls \| Dominant variable cost \| Caching where safe, routing
  by task complexity, token budgets. \|

These capacity figures are planning assumptions, not requirements from
the uploaded source. Actual targets should be replaced after
founder-pilot telemetry is available.

## 38. Failure Modes and Recovery

| Failure \| Expected behavior \|

| --- \| --- \|

| LLM timeout \| Retry compatible transient call once or route fallback;
  preserve user request state. \|

| Vector index unavailable \| Use structured/lexical fallback or
  continue without memory with clear internal telemetry. \|

| Database unavailable \| Fail safely; do not execute external writes
  when state cannot be durably recorded. \|

| Connector timeout \| Bounded retry for safe operations; reconcile
  uncertain writes before retrying. \|

| Worker crash \| Resume from persisted agent/workflow state. \|

| Duplicate event \| Consumer idempotency prevents duplicate
  memory/action. \|

| Partial account deletion \| Retry from deletion ledger until all data
  stores report completion. \|

| Stale authorization \| Re-check permissions immediately before
  external action. \|

## 39. Evaluation Framework

| Dimension \| Example metric \|

| --- \| --- \|

| Memory precision \| Percentage of stored memories judged
  durable/relevant and correctly typed. \|

| Memory recall \| Percentage of important explicit facts/preferences
  successfully captured when policy allows. \|

| Retrieval relevance \| Top-k memories judged useful for the current
  task. \|

| Contradiction safety \| Rate at which stale/conflicting memory
  incorrectly overrides current user input. \|

| Belief calibration \| Confidence band agreement with later
  confirmation/correction. \|

| Decision transparency \| Users can identify evidence, assumptions and
  preferences used. \|

| Agent success \| Goal completion without unauthorized or duplicate
  actions. \|

| Approval quality \| Users understand what will happen before
  approving. \|

| Grounding \| Claims attributable to provided evidence/source when
  grounding is required. \|

| Privacy correctness \| No retrieval/disclosure outside configured
  consent/policy in automated tests. \|

## 40. MVP Implementation Plan

| Phase \| Deliverables \|

| --- \| --- \|

| Phase 0 --- Foundations \| Identity, PostgreSQL schema, API
  conventions, model gateway, telemetry, policy skeleton. \|

| Phase 1 --- Conversation \| Streaming chat, conversation persistence,
  prompt/version registry. \|

| Phase 2 --- Memory \| Candidate extraction, governed write pipeline,
  memory UI, retrieval, correction/deletion. \|

| Phase 3 --- Beliefs \| Evidence graph, contradiction handling, user
  challenge/suppression. \|

| Phase 4 --- Decisions \| Decision workspace, criteria/options,
  evidence snapshots, transparent analysis. \|

| Phase 5 --- Agent pilot \| One or two connectors, planner/executor
  split, approval flow, durable run state. \|

| Phase 6 --- Privacy lifecycle \| Export, account deletion, retention
  jobs, connector revocation verification. \|

| Phase 7 --- Hardening \| AI evaluations, security tests,
  load/resilience tests, incident runbooks. \|

## 41. Traceability Matrix

| Product capability \| Functional requirements \| Technical components
  \| Architecture plane \|

| --- \| --- \| --- \| --- \|

| Conversation \| FR-CONV-\* \| Conversation Service, Orchestrator,
  Model Gateway \| Experience / Intelligence \|

| Personal Memory \| FR-MEM-\* \| Memory Service, PostgreSQL, pgvector
  \| Personal Context / Data \|

| Beliefs \| FR-BEL-\* \| Belief Service, evidence links \| Personal
  Context \|

| Decision Intelligence \| FR-DEC-\* \| Decision Service, retrieval,
  model gateway \| Decision / Intelligence \|

| Agentic AI \| FR-AGT-\* \| Agent Service, Policy Gate, Connectors \|
  Action / Governance \|

| Privacy & Consent \| FR-PRV-\* \| Policy/Consent, deletion
  coordinator, secrets \| Governance / Data \|

| Safety & Grounding \| FR-SAFE-\* \| Policy, Model Gateway, retrieval
  controls \| Intelligence / Governance \|

| Feedback & Evaluation \| FR-FBK-\* \| Telemetry, evaluation pipeline
  \| Operations \|

## 42. Open Questions Requiring Founder/Product Decisions

-   Which categories of sensitive personal information may become
    durable memory, and which always require explicit confirmation?

-   Should memory be opt-in globally, opt-out globally, or configured by
    category?

-   Which beliefs should be visible to users, and should users be able
    to edit them directly or only challenge/suppress them?

-   What is the first concrete decision-intelligence use case that
    proves differentiated value?

-   Which first connector/action should demonstrate agentic value
    without creating excessive security risk?

-   Will the MVP support only one individual identity, or
    household/team/shared contexts?

-   What jurisdictions/data-residency commitments are required at
    launch?

-   What retention periods apply to conversation content, audit events,
    files and deleted-account backups?

-   What is the product policy for model-provider data retention and
    training settings?

-   What quantitative success thresholds define the founder pilot as
    validated?

## 43. Definition of Done for Documentation v1

-   Founder/product owner confirms or edits every open assumption in
    this document.

-   Functional requirements are prioritized as MVP, post-MVP or
    rejected.

-   Data classification and consent policy are approved.

-   First user journeys and connector use cases are selected.

-   Architecture decisions are reviewed by engineering/security.

-   API/data schemas are converted into executable contracts/migrations.

-   Threat model and AI evaluation suites are created from the
    requirements.

-   Traceability is maintained from product requirement through
    implementation and test.

## 44. End-to-End Request Flows

### 44.1 Conversational request

1. The client authenticates the request and sends a conversation
   message with a correlation ID and an optional idempotency key.
2. The API validates ownership of the conversation and persists the
   user message before beginning model work.
3. The orchestrator classifies the request and asks the policy layer
   which data classes, memories, tools, and model capabilities are
   permitted.
4. Retrieval returns a bounded context package containing source
   references, status, confidence, and temporal metadata.
5. The model gateway invokes a versioned prompt/model configuration and
   validates the structured result before it is rendered.
6. The assistant response is persisted with model, prompt, policy, and
   retrieval references. Candidate memory extraction is queued only
   after the response lifecycle is stable.
7. The client receives a streamed response and a final durable message
   status. A partial stream is never treated as a completed response.

This flow makes the response path responsive while keeping durable
memory enrichment asynchronous. Explicit user memory edits remain
synchronous because the user expects the resulting state to be visible
immediately.

### 44.2 Authorized external action

The agent planner produces a proposed plan, but the plan is not an
authorization. The policy gate evaluates each step against the
authenticated user, connector grant, data disclosure scope, risk class,
resource target, and approval state. A read-only step may run without a
new prompt when covered by standing permission. A consequential write
must display the exact operation and receive approval bound to that
operation. If the plan changes materially after approval, the affected
step returns to `WAITING_APPROVAL`.

The executor records an operation ID before calling the connector,
uses the minimum scoped credential, and persists the connector result
or uncertainty. If the network fails after a write may have reached the
provider, the system reconciles using the provider operation ID rather
than blindly retrying.

### 44.3 Export and deletion

Export and deletion use a durable lifecycle record and a deletion or
export ledger. The ledger lists canonical stores and derivative stores,
including database rows, vector entries, object files, caches, queues,
search indexes, and connector-derived artifacts. The privacy service
marks records unavailable for retrieval before asynchronous cleanup
begins. Completion requires verification from each applicable store;
unverified work remains visible to operations and is retried.

## 45. Domain ownership and contracts

Logical domains own their invariants even when they share one deployed
application and PostgreSQL instance:

| Domain | Owns | Publishes or consumes |
| --- | --- | --- |
| Identity and governance | Users, sessions, consent, authorization, data classification | Authentication context, policy decisions, revocation events |
| Conversation | Conversations, messages, response status | Interaction-completed events, response references |
| Personal context | Memories, evidence links, beliefs, retrieval views | Memory mutation, contradiction, and index-work events |
| Decisions | Workspaces, criteria, options, snapshots, outcomes | Decision context requests and outcome feedback |
| Agent action | Plans, steps, approvals, executions, connector results | Approval requests, action status, audit events |
| Files and ingestion | Object references, parsing status, chunks, source metadata | Ingestion completion and deletion events |
| Operations | Audit, telemetry, evaluation records, feature flags | Alerts, evaluation results, operational commands |

Cross-domain calls should use versioned contracts and explicit
ownership. A domain may read another domain's published view or API,
but should not update another domain's canonical tables as a shortcut.
This rule preserves the option to separate services later without
rewriting business invariants.

## 46. Environment topology and local development

The repository's current local topology provides PostgreSQL 16 and
Redis 7 through `docker-compose.yml`. PostgreSQL is the canonical
development store and Redis is suitable for cache, locks, and queued
work; neither local service should be treated as production-hardened
by default. Local credentials and ports are development conveniences,
not deployment recommendations.

Development, staging, and production must use separate databases,
volumes, credentials, encryption keys, connector grants, and model
provider configuration. The application should fail clearly when a
required secret or migration is missing rather than silently falling
back to insecure defaults. Production ingress should add TLS
termination, WAF/rate controls, private data-store networking, backup
monitoring, and workload identity.

## 47. Architectural quality attributes

The architecture should be reviewed against measurable scenarios:

| Attribute | Scenario | Design response |
| --- | --- | --- |
| Privacy | A user revokes consent while queued enrichment is pending. | Policy checks and deletion tombstones prevent later storage or disclosure. |
| Reliability | A worker stops between a tool call and state persistence. | Idempotency key, operation reconciliation, and durable state transitions prevent unsafe duplication. |
| Evolvability | The embedding or model provider changes. | Versioned gateway contracts and rebuildable derivative indexes support migration. |
| Performance | A conversation requires retrieval and model streaming. | Bounded retrieval, parallel safe reads, caching, and response streaming protect interactive latency. |
| Operability | A user reports an incorrect answer. | Correlation IDs connect response, context, model version, policy decision, and audit evidence without requiring raw content in ordinary logs. |
| Security | Untrusted file text instructs the agent to send data externally. | Content is evidence only; deterministic policy and connector scopes remain authoritative. |

## 48. Architectural risks and mitigations

The principal risk is premature complexity: physically splitting every
logical component can slow the founder pilot and create more failure
paths than it removes. The modular-monolith recommendation therefore
requires clear module boundaries, contract tests, ownership, and
observability from the beginning.

The second risk is treating model output as a trusted system decision.
Structured output validation improves reliability but is not
authorization. Policy, consent, and resource checks must remain
deterministic and outside the model.

The third risk is incomplete lifecycle handling. Memory correction,
connector revocation, export, and deletion must be designed together
with indexing, caching, queues, backups, and provider retention. A
feature is not complete if its derivative data continues to influence
responses after the user has disabled or deleted it.

## 49. Architecture theory and design rationale

The architecture is organized around a fundamental separation of
concerns: experience presents information, intelligence interprets
requests, personal context supplies governed evidence, governance
decides what is permitted, and action performs only authorized work.
These are logical boundaries even when the MVP deploys them in one
modular application. The separation exists to protect trust and
evolvability, not merely to create more services.

### 49.1 Why personal context has multiple layers

Evidence, memory, belief, and retrieval view have different authority
and lifecycles. Evidence answers “where did this come from?” Memory
answers “what durable statement may be reused?” Belief answers “what
tentative pattern does the system currently infer?” A retrieval view
answers “what small, purpose-specific subset may this request see?”
Combining these layers would make correction, contradiction, deletion,
and disclosure control ambiguous. Keeping them separate makes each
decision inspectable and allows derivative indexes to be rebuilt.

### 49.2 Why policy is outside the model

A language model can interpret intent and propose a plan, but it is
probabilistic and can be influenced by untrusted content. Authorization,
consent, data classification, risk, and approval are security
decisions and must be evaluated by deterministic application logic.
The model may request a capability; it cannot create a capability.
This principle applies equally to memory writes, retrieval, connector
calls, exports, and deletion.

### 49.3 Why the MVP is modular rather than distributed

The pilot needs clear ownership and reliable behavior more than it
needs many network boundaries. A modular monolith reduces deployment,
debugging, and transaction complexity while preserving domain APIs,
events, contracts, and repository boundaries. Physical extraction is
justified by measurable pressure such as independent scaling,
availability isolation, security isolation, or workflow complexity—not
by the existence of a logical module.

### 49.4 Why derivative data is disposable

Embeddings, caches, search projections, summaries, and evaluation
artifacts are derived from canonical user data. They improve speed but
must never become the only source of truth. Treating them as
rebuildable simplifies model migration, correction, deletion, backup
recovery, and incident response. The retrieval path must apply
ownership and lifecycle filters before using any derivative score.

### 49.5 Why agent architecture is a state machine

An agent task can span minutes, approvals, retries, worker restarts,
provider timeouts, and uncertain external outcomes. A request/response
function cannot safely represent that lifecycle. Persisted states and
transitions make it possible to resume, cancel, reconcile, audit, and
prove that a step was not executed twice. The state machine also gives
the UI a truthful status instead of forcing it to infer progress from
model text.

### 49.6 Why privacy has three gates

The write gate answers whether information may become durable. The
retrieval gate answers whether it is relevant and permitted for this
purpose. The disclosure gate answers whether it may leave the trusted
application boundary. These decisions are intentionally independent:
information can be stored but excluded from a particular model call,
retrieved internally but not sent to a connector, or deleted from
active use while physical cleanup completes.

### 49.7 Architectural invariants

Across every deployment shape, the following must remain true:

- no resource operation occurs without an authenticated principal and
  owner/tenant scope;
- model output never bypasses policy or authorization;
- canonical records remain recoverable independently of indexes and
  caches;
- external writes are bounded by scope, approval, idempotency, and
  reconciliation;
- deletion and revocation propagate to all active and derivative paths;
- observability explains system behavior without making private content
  available to ordinary operators.
