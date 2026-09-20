# selfie.Me — Functional Specification Document (FSD)

**Version:** V01 — Refined baseline (supersedes the original v0.1 draft)
**Status:** Approved working baseline for founder pilot
**Owners:** CEO/Founder (accountable), Head of Product (functional scope), Head of Security/DPO (privacy sections)

## Document control

| Field | Value |
| --- | --- |
| Document | Functional Specification Document (Part I of the selfie.Me documentation pack) |
| Companion documents | Architecture Design Document (`ADD`), Technical Design Document (`TDD`) |
| Cross-reference format | `FSD §x.y`, `TDD §x.y`, `ADD §x.y` — sections number independently per document |

### Changelog since v0.1

- Fixed a numbering collision: v0.1 had a "§9" in both this document and the TDD, which made cross-referencing ambiguous. This document's sections now run 1–13, and are never referenced by bare number outside this file.
- Added §9, Trust & Safety and Abuse Prevention — v0.1 had zero mention of self-harm/crisis disclosure handling, abuse of the memory system (e.g., someone else's data entered about a third party), or content policy, despite the product explicitly capturing sensitive personal disclosures. This is a material gap for any consumer AI product at this scale.
- Added §10, Success Metrics and Guardrails — a functional spec without a definition of product success is a wish list. Added a north-star metric, activation/retention targets, and explicit guardrail metrics that must never be traded off for growth.
- Added §11.2, Data Classification Reference, linking directly to `ADD §7.1` so sensitivity tiers are defined once and referenced everywhere instead of being restated loosely per requirement.
- Tightened previously vague requirements into testable statements (e.g., FR-MEM-009 sensitivity handling now points to concrete tiers; FR-AGT-003 approval requirement now references the risk classes defined in `TDD §16.1`).
- Converted every previously malformed table into valid markdown.
- Moved the "interpretation guide" to the end of the document, matching the same structural fix applied to the ADD.

---

## 1. Purpose and scope

This FSD defines the functional behavior of selfie.Me v1/MVP: actors, capabilities, workflows, requirements, business rules, errors, and acceptance expectations. It deliberately avoids binding the product to a specific cloud provider or programming language — those choices live in the `TDD`.

### 1.1 In scope

- Account, authentication, and user profile.
- Conversational AI sessions.
- Personal memory capture, review, correction, deletion, and retrieval.
- Preference, goal, relationship, and life-event representations.
- Belief/evolution model with confidence, evidence, and contradiction handling.
- Decision workspaces for structured choices.
- Agentic planning and tool execution under user authorization.
- Files and user-provided sources as contextual evidence.
- Consent, privacy controls, data export, and deletion.
- Safety/grounding behavior, audit events, and feedback.
- Trust & safety controls for sensitive disclosures and third-party data (§9).
- Basic notifications for long-running or scheduled agent tasks, if enabled.

### 1.2 Out of scope for initial MVP

- Fully autonomous financial, medical, legal, or employment decisions.
- Unrestricted background monitoring of private accounts.
- Training foundation models on an individual user's private data (hard commitment — see `ADD ADR-012`).
- Public social network/community features.
- Advertising personalization based on private memory.
- Silent storage of highly sensitive (T3, `ADD §7.1`) information without an explicit product policy and user control.
- Irreversible external actions without authorization.
- Shared/household/team identity contexts (`ADD §22` — individual identity only for MVP).

## 2. Actors and roles

| Actor | Description | Key permissions |
| --- | --- | --- |
| End User | Primary owner of a selfie.Me account. | Chat, manage memory, configure consent, create decisions, approve actions, export/delete data. |
| AI Assistant | Conversational reasoning layer acting for the user within policy. | Read authorized context, propose memory, create plans, call approved tools. |
| Memory Service | System actor managing durable personal context. | Store/retrieve/update/supersede/delete governed memory. |
| Agent Runtime | Executes multi-step tasks. | Plan, call tools, pause for approval, record execution. |
| External Tool/Connector | Third-party service or internal capability. | Receives only the minimum authorized data for a specific action. |
| Administrator/Support | Operational role with tightly restricted access. | Service operations; break-glass only for plaintext access, per `ADD §12.2` — never routine. |

## 3. Functional domains and requirements

### 3.1 Identity, account, and profile

| ID | Requirement |
| --- | --- |
| FR-ID-001 | The system shall allow a user to create and authenticate an account using supported identity methods. |
| FR-ID-002 | The system shall maintain a canonical user profile containing only explicit profile fields and references to governed memories. |
| FR-ID-003 | The user shall be able to view active sessions/devices and revoke sessions. |
| FR-ID-004 | The system shall support account-level locale, timezone, language, and communication preferences. |
| FR-ID-005 | The system shall prevent cross-user retrieval of memory, files, decisions, and agent executions — verified by automated tests, not policy alone (`ADD §12.1`). |
| FR-ID-006 (new) | The system shall support account recovery without weakening authentication (e.g., no security-question-only recovery for accounts holding T3 data). |

### 3.2 Conversation

| ID | Requirement |
| --- | --- |
| FR-CONV-001 | The user shall be able to create, continue, rename, archive, and delete conversations. |
| FR-CONV-002 | Each assistant response shall be generated from the current request plus an explicitly assembled context bundle. |
| FR-CONV-003 | The system shall distinguish conversation-local context from durable personal memory. |
| FR-CONV-004 | The user shall be able to request that information from a conversation not be remembered. |
| FR-CONV-005 | When durable memory materially influences a response, the system shall identify the relevant memory basis to the user. |
| FR-CONV-006 | A fresh explicit instruction from the user shall take precedence over older preferences when they conflict for the current task. |
| FR-CONV-007 (new) | The system shall detect when a user's message describes another named individual's sensitive information and route it through the third-party data rule (`FR-SAFE-007`) rather than storing it as the user's own memory. |

### 3.3 Personal memory

| ID | Requirement |
| --- | --- |
| FR-MEM-001 | The system shall extract candidate memories from interactions using configurable eligibility rules. |
| FR-MEM-002 | Candidate memories shall be classified at minimum as fact, preference, goal, relationship, event, routine, constraint, project/context, or user instruction. |
| FR-MEM-003 | Every durable memory shall retain provenance, creation time, last-confirmed time, confidence/status, and sensitivity classification (`ADD §7.1`). |
| FR-MEM-004 | The system shall support explicit memories created directly by the user. |
| FR-MEM-005 | The system shall support inferred memories only when policy allows, and shall label them as inferred wherever displayed. |
| FR-MEM-006 | The user shall be able to view, search, correct, confirm, pin, suppress, and delete memories. |
| FR-MEM-007 | A correction shall preserve an audit trail while preventing superseded content from being treated as current. |
| FR-MEM-008 | The retrieval layer shall rank memories by relevance, recency, confidence, explicitness, and task compatibility (scoring function in `TDD §14`). |
| FR-MEM-009 | Memories classified T3 (`ADD §7.1`) shall use stricter capture (explicit per-category opt-in), retrieval (excluded from default context), and display rules than T2 memories. |
| FR-MEM-010 | Deletion shall remove the memory from active retrieval immediately and trigger downstream deletion workflows per the retention schedule (§7.3). |
| FR-MEM-011 (new) | The system shall never write a T3-category memory without an explicit, per-category confirmation step distinct from general account consent. |

### 3.4 Belief and evolution model

| ID | Requirement |
| --- | --- |
| FR-BEL-001 | The system shall represent model beliefs separately from source facts and explicit user statements. |
| FR-BEL-002 | A belief shall include proposition, confidence, evidence references, timestamps, and current status. |
| FR-BEL-003 | New evidence may strengthen, weaken, supersede, or contradict a belief. |
| FR-BEL-004 | The system shall not convert a low-confidence inference into an explicit user fact without confirmation. |
| FR-BEL-005 | Conflicting evidence shall be retained as a contradiction until resolved by reliable evidence or user confirmation. |
| FR-BEL-006 | Beliefs used for consequential decisions shall meet a configurable confidence and evidence threshold (default: ≥0.7 confidence, ≥2 corroborating evidence items). |
| FR-BEL-007 | The user shall be able to challenge an inferred belief and prevent its future use. Beliefs are challengeable/suppressible only, never directly editable — see rationale in `ADD §22`. |

### 3.5 Decision intelligence

| ID | Requirement |
| --- | --- |
| FR-DEC-001 | The user shall be able to create a decision workspace with a question, options, constraints, and desired outcome. |
| FR-DEC-002 | The system shall propose decision criteria based on the request and authorized personal context. |
| FR-DEC-003 | The user shall be able to add, remove, or weight criteria. |
| FR-DEC-004 | The system shall distinguish factual evidence from preference-based tradeoffs and model assumptions. |
| FR-DEC-005 | The system shall provide rationale and uncertainty rather than only a selected option. |
| FR-DEC-006 | The system shall preserve decision snapshots so users can understand why a decision looked reasonable at a particular time. |
| FR-DEC-007 | Outcome feedback may update preferences or beliefs only under the applicable memory policy. |
| FR-DEC-008 (new) | The system shall refuse to present itself as giving regulated financial, medical, or legal advice; decision workspaces touching those domains shall carry a visible disclaimer and shall not be the pilot's flagship use case (`ADD §22`). |

### 3.6 Agentic tasks and actions

| ID | Requirement |
| --- | --- |
| FR-AGT-001 | The assistant shall be able to transform an eligible user goal into a multi-step plan. |
| FR-AGT-002 | Each step shall declare required tools, data access, and whether user approval is required. |
| FR-AGT-003 | The agent shall request approval before any step classified `CONSEQUENTIAL_WRITE` or `HIGH_IMPACT` (`TDD §16.1`) unless a valid standing permission covers the exact action. |
| FR-AGT-004 | The user shall be able to cancel a running agent task. |
| FR-AGT-005 | Tool calls shall be idempotent where technically possible and carry execution identifiers. |
| FR-AGT-006 | The agent shall record tool inputs/outputs in a redacted execution log appropriate to the user's audit view. |
| FR-AGT-007 | On tool failure, the agent shall retry only according to bounded retry policy and otherwise surface a recoverable failure. |
| FR-AGT-008 | The agent shall not broaden tool permissions merely to complete a task. |
| FR-AGT-009 (new) | The MVP's first connector shall be read-only (calendar/email digest, `ADD §22`); write-capable connectors are excluded from the pilot until the approval flow is validated end to end. |

### 3.7 Consent, privacy, and user control

| ID | Requirement |
| --- | --- |
| FR-PRV-001 | The product shall provide clear, per-category controls for whether eligible interactions may create durable memory, defaulting per `ADD §22` (ON for T2, OFF for T3). |
| FR-PRV-002 | The system shall request explicit consent before connecting external data sources. |
| FR-PRV-003 | Users shall be able to revoke connector access and invalidate stored connector credentials/tokens. |
| FR-PRV-004 | Users shall be able to export their personal data in a documented, portable machine-readable format within a bounded SLA (target: available within 24 hours of request). |
| FR-PRV-005 | Users shall be able to request account deletion. |
| FR-PRV-006 | The system shall support retention rules by data class (§7.3). |
| FR-PRV-007 | The system shall record consent version, scope, time, and revocation state. |
| FR-PRV-008 | Private data shall not be used for unrelated purposes without a separately valid legal/product basis and corresponding user controls. |
| FR-PRV-009 (new) | The privacy notice shall accurately state the current encryption posture (`ADD §7`) and shall be updated before, not after, any change to that posture takes effect. |

### 3.8 Safety and grounding

| ID | Requirement |
| --- | --- |
| FR-SAFE-001 | The assistant shall treat retrieved memory as contextual evidence, not automatically as current truth. |
| FR-SAFE-002 | When evidence conflicts, the assistant shall prefer current explicit user input or ask for clarification when the conflict matters. |
| FR-SAFE-003 | External factual claims requiring freshness shall be grounded in authorized sources or identified as uncertain. |
| FR-SAFE-004 | The system shall prevent prompt/tool output from directly overriding system security and authorization policy. |
| FR-SAFE-005 | The system shall support domain-specific safeguards for high-impact advice and actions. |
| FR-SAFE-006 | The system shall log policy decisions needed for incident investigation without unnecessarily logging private content. |
| FR-SAFE-007 (new) | If a user's message discloses information primarily about a named third party (not the user), the system shall not create a durable memory attributed as the third party's personal data without a documented product policy for that case; by default such content is treated as conversation-local only. |
| FR-SAFE-008 (new) | If a message indicates a plausible self-harm or crisis situation, the system shall respond using a reviewed, non-personalized safety script and surface crisis resources, bypassing ordinary memory-write eligibility for that turn (`ADD §14`). |

### 3.9 Feedback and quality

| ID | Requirement |
| --- | --- |
| FR-FBK-001 | Users shall be able to provide response-level feedback. |
| FR-FBK-002 | Users shall be able to report an incorrect memory or belief directly from the relevant UI. |
| FR-FBK-003 | The system shall capture non-sensitive operational metrics for latency, errors, retrieval quality, and agent success. |
| FR-FBK-004 | Model/prompt versions associated with an execution shall be traceable for evaluation. |

## 4. Functional theory and behavioral interpretation

The requirements in §3.1–§3.9 describe a controlled personal-context system, not a collection of screens or endpoints. The product must preserve the distinction between what the user said, what the system inferred, what the system currently believes, and what the assistant is allowed to do — the central functional principle behind every domain.

**Identity** establishes who is making a request; it does not by itself decide what that person may access. Authorization is evaluated against the resource, operation, consent state, and current account status.

**Conversation** is the interaction surface, not the complete personal memory store. The context assembler creates a purpose-bound bundle for each response instead of replaying all historical text. Fresh instructions take priority for the immediate task because users must be able to change their mind without first repairing every older record.

**Memory** is a governed representation, not a transcript copy or an unreviewable model summary. The write decision favors precision over volume: storing fewer correct memories is safer than filling the archive with speculation.

**Beliefs** represent hypotheses derived from evidence and must remain distinguishable from explicit facts. A belief becomes safer with repeated, relevant, recent, user-confirmed evidence; unsafe when based on a single model inference or stale behavior.

**Decision intelligence** should improve the user's reasoning rather than hide it behind a recommendation. Criteria and weights are user-editable because a mathematically consistent result can still be wrong for the user's actual priorities.

**Agentic action** is an execution coordinator, not an independent authority. Idempotency is a user-protection concept: when a network timeout leaves the outcome uncertain, the system must reconcile the prior operation instead of duplicating an email, booking, payment, or data change.

**Consent and privacy** are purpose- and scope-bound. Permission to store a preference does not automatically authorize sending it to an external connector.

**Safety and grounding**: retrieved context is evidence for reasoning, not an instruction to obey, and not proof that a statement is still true. The product must prefer a transparent limitation over a confident but unsupported personal claim.

### 4.1 Functional invariants

1. A current explicit user instruction takes precedence for the immediate task over stale or inferred context.
2. Deleted, suppressed, or unauthorized records are not returned by normal retrieval.
3. Model output may propose a fact, belief, plan, or action but cannot grant itself storage, disclosure, or execution authority.
4. Every durable personal record has provenance and a lifecycle state.
5. Every consequential external action has an authorization decision, an execution identity, and an auditable outcome or uncertainty.
6. A user-visible success state is emitted only after the corresponding state is durably recorded or explicitly marked as pending.
7. Content describing a third party is never silently treated as durable memory about that third party (`FR-SAFE-007`).

## 5. Key user journeys

### 5.1 First-run onboarding

1. User creates an account and completes authentication.
2. Product explains the difference between chat history, durable memory, inferred beliefs, and external connectors, and states the current encryption posture in plain language (`ADD §7.2`).
3. User chooses initial memory preferences per category and reviews privacy/consent controls.
4. User optionally supplies profile information and goals.
5. System creates only explicit profile/memory records authorized by the onboarding choices.
6. User enters the first conversation.

### 5.2 Memory capture and correction

1. User states information that may be useful later.
2. Memory extraction produces one or more candidate memories.
3. Policy engine evaluates category, sensitivity, consent, confidence, and duplication.
4. Eligible memory is stored; sensitive or ambiguous items require confirmation.
5. Later retrieval uses the memory only when relevant.
6. User corrects the information.
7. Original record is superseded, correction becomes current, and future retrieval excludes the obsolete version.

### 5.3 Decision workspace

1. User asks for help making a decision.
2. Assistant identifies options, constraints, and missing facts.
3. Authorized personal preferences and goals are retrieved.
4. Assistant builds criteria and separates evidence, assumptions, and preferences.
5. User adjusts criteria/weights if desired.
6. System produces a transparent tradeoff analysis and records a decision snapshot.
7. Optional outcome feedback is recorded later.

### 5.4 Agent action

1. User requests an action-oriented task.
2. Planner decomposes the task into steps and determines required tools.
3. Authorization layer verifies connector scope and approval requirements.
4. Agent executes reversible/read-only steps.
5. Before a consequential write/action, agent displays what will happen and requests approval.
6. Execution continues, records results, and returns a concise completion summary.
7. Failures are recoverable and do not silently repeat consequential actions.

### 5.5 Crisis or sensitive-disclosure interaction (new)

1. User discloses a message the safety classifier flags as plausible self-harm/crisis content (`FR-SAFE-008`).
2. The assistant responds with a reviewed, non-personalized safety script and crisis resources, not an open-ended personalized reply.
3. The turn is excluded from ordinary memory-write eligibility.
4. If the user explicitly asks the system to remember something from that conversation, the standard write-gate rules apply as usual — the exclusion is automatic-only, not a permanent block.

## 6. Business rules

| Rule | Definition |
| --- | --- |
| BR-001 | Current explicit user instructions override older preferences for the current request. |
| BR-002 | A memory marked deleted/suppressed is never returned by normal retrieval. |
| BR-003 | An inferred belief cannot silently overwrite an explicit user statement. |
| BR-004 | Contradictory evidence lowers confidence or creates a conflict state; it is not discarded merely because it is inconvenient. |
| BR-005 | High-sensitivity (T3) information is stored only under the applicable per-category consent (`FR-MEM-011`). |
| BR-006 | External write actions require a valid authorization decision at execution time, re-checked immediately before execution, not cached from plan time. |
| BR-007 | Connector tokens are secrets and are never included in LLM prompts. |
| BR-008 | The minimum necessary context is supplied to models and tools. |
| BR-009 | A model-generated statement is not provenance for an external fact unless it points to an actual source. |
| BR-010 | Account deletion overrides ordinary retention except for narrowly required security/legal records (§7.3). |
| BR-011 (new) | A model provider integration is not permitted without a contractual no-training, bounded-retention commitment (`ADD ADR-012`). |
| BR-012 (new) | Content primarily describing a named third party is never attributed as that third party's own governed memory (`FR-SAFE-007`). |

## 7. Non-functional requirements

| ID | Requirement | Target | Measurement |
| --- | --- | --- | --- |
| NFR-001 | Availability | 99.9% monthly for core API after production launch (error budget: ~43 min/month); MVP may run a lower internal SLO while validated. | Uptime monitoring, monthly error-budget review |
| NFR-002 | Interactive latency | P50 first useful response < 3s, P95 < 8s, excluding long tool work; stream responses where possible. | APM tracing, tagged by endpoint |
| NFR-003 | Memory retrieval latency | P95 < 500ms for a typical retrieval request, excluding embedding generation on write. | APM tracing |
| NFR-004 | Scalability | Stateless API/worker tiers horizontally scalable; partition user data by tenant/user key. | Load test at 2x projected peak (`ADD §17.1`) |
| NFR-005 | Durability | Durable user records backed by managed persistence with tested backup/restore, quarterly restore drill. | Restore drill logs |
| NFR-006 | Security | TLS in transit; encryption at rest; least-privilege service identities; secret management. | Security review, penetration test before GA |
| NFR-007 | Privacy | Data minimization, retention enforcement, deletion workflow, consent traceability. | Automated privacy test suite (`ADD §19`) |
| NFR-008 | Observability | Distributed traces, structured logs, metrics, and security audit events with content redaction. | Trace coverage audit |
| NFR-009 | Accessibility | Core web experience designed toward WCAG 2.2 AA. | Accessibility audit before GA |
| NFR-010 | Portability | User export available in documented machine-readable formats, delivered within 24 hours of request. | Export SLA monitoring |
| NFR-011 | Model resilience | Provider abstraction permits model substitution and graceful fallback for supported tasks. | Fallback drill in staging |
| NFR-012 | Auditability | Critical memory mutations, consent changes, and external actions have immutable audit events. | Audit log completeness check |
| NFR-013 (new) | Cost efficiency | Per-active-user model spend tracked monthly and reviewed against `ADD §31` model; any feature projected to move token volume >20% requires cost sign-off before rollout. | Cost dashboard, tied to `ADD §29.2` launch gate |

A target without a measurement method is not a real requirement — every NFR above must have a dashboard or test that can fail a release, not just a number in a document.

## 8. Acceptance criteria for MVP

- A user can have a conversation, create durable memories, inspect them, correct them, and delete them.
- Deleted/suppressed memories stop appearing in retrieval tests.
- Memory provenance and explicit/inferred status are visible in internal/admin debugging and user-facing review where appropriate.
- A decision workspace can combine user-provided options with retrieved preferences while showing assumptions separately.
- An agent can complete at least one read-only and one write-enabled connector workflow, pausing for approval before the write.
- Revoked connector access prevents subsequent tool calls.
- Account export and deletion workflows complete in test environments with verifiable downstream state.
- Automated evaluation demonstrates that contradictory old memory does not override a fresh explicit user instruction.
- Security tests demonstrate user A cannot retrieve user B's memory through API, vector search, or agent tooling.
- A crisis-disclosure test conversation triggers the safety script and is excluded from ordinary memory write (`FR-SAFE-008`).

### 8.1 Requirement priority and release classification

| Category | Meaning | Release treatment |
| --- | --- | --- |
| MVP / must-have | Required for a trustworthy founder pilot, or for legal/privacy/security safety. | Must have implementation, test coverage, and an owner before pilot release. |
| MVP / should-have | Important to usability or learning; a documented manual fallback is acceptable initially. | Implement when it does not delay core trust controls. |
| Post-MVP | Valuable after the primary workflow and product-market assumptions are validated. | Keep the requirement; define a target release or discovery milestone. |
| Policy decision | Cannot be implemented correctly until a product, legal, or user-research decision is made. | Track as an explicit decision with an approver; do not silently choose a default (see `ADD §22` for decisions already made). |

The MVP should prioritize the smallest complete trust loop: a user can capture a memory, understand why it was stored, correct or delete it, and verify that the correction affects future responses. Agentic automation and additional connectors are not complete features if this loop is unreliable.

## 9. Trust & safety and abuse prevention

This section did not exist in v0.1. A product that captures sensitive personal disclosures at scale needs an explicit trust & safety posture before launch, not after the first incident.

### 9.1 Content and conduct risks specific to a personal-memory product

| Risk | Handling |
| --- | --- |
| Self-harm/crisis disclosure | Safety script + resources, excluded from default memory write (`FR-SAFE-008`, journey §5.5). |
| Disclosure about a third party (e.g., a partner's health condition) | Not stored as governed memory about that third party by default (`FR-SAFE-007`, `BR-012`). |
| Attempted misuse of the agent for harassment or surveillance of another person (e.g., "track my ex's location") | Policy Gate denies the plan at the authorization layer regardless of what the planner proposes; this is a hard deny, not a confidence-based judgment call. |
| Prompt injection via uploaded files attempting to exfiltrate other users' data or escalate agent authority | Content/instruction separation (`ADD §14`); cannot succeed because authority is never derived from model output. |
| Underage users | Age-gating at signup; MVP is not designed or marketed for users under 18, and onboarding must include an age attestation. |

### 9.2 Escalation path

A flagged conversation that indicates imminent risk to the user or a third party is escalated to a documented human review process with a defined responder and SLA (target: acknowledgment within 1 hour during pilot). This process is a policy decision requiring legal input before GA and is tracked as a blocking item for Phase 6 (`ADD §20`).

### 9.3 What this MVP explicitly does not attempt

Automated detection of all harmful content is not achievable with certainty. The product commits to a narrow, well-tested set of high-confidence triggers (self-harm, third-party PII, explicit harassment requests) rather than an overbroad filter that degrades ordinary conversation quality. This scope is reviewed every phase as false-positive/false-negative rates are measured.

## 10. Success metrics and guardrails

A functional spec without success criteria cannot be evaluated as a product. These are the metrics a CEO reviews at each pilot milestone.

### 10.1 North star

**Weekly active memory interactions per retained user** — a proxy for "the assistant is actually being used as a personal memory system," not just a chatbot. This is preferred over raw DAU because it directly reflects the product's differentiated value (§4).

### 10.2 Growth and engagement targets (pilot exit criteria, ties to `ADD §22`)

| Metric | Target |
| --- | --- |
| Week-4 retention | ≥ 40% |
| Memory accuracy (user-sampled review) | ≥ 70% judged accurate |
| Net Promoter Score | ≥ 40 |
| Agent task completion rate | ≥ 95%, 0 unauthorized actions |

### 10.3 Guardrail metrics (must never be traded off for growth)

| Guardrail | Threshold | Consequence if breached |
| --- | --- | --- |
| Confirmed cross-user data leakage incidents | 0 | Release-blocking; triggers SEV1 process (`ADD §29.1`) |
| Contradiction safety (stale memory overriding fresh instruction) | < 1% on adversarial eval | Blocks the release that introduced the regression |
| Unauthorized/duplicate agent actions | 0 tolerated | Blocks agent feature rollout until root-caused |
| Privacy notice accuracy (`FR-PRV-009`) | 100% — no gap between claim and implementation | Immediate legal/DPO review, not a backlog item |

Guardrails exist precisely because growth metrics create pressure to loosen exactly the controls this document spends most of its length defining. Any proposal to relax a guardrail requires CEO-level sign-off, not a product-manager-level decision.

## 11. Functional state models

### 11.1 Memory lifecycle

A memory begins as `CANDIDATE` and is evaluated against consent, sensitivity, confidence, and duplication rules. It may become `ACTIVE`, `REQUIRES_CONFIRMATION`, `SUPPRESSED`, `SUPERSEDED`, or `DELETED`. Only active records are eligible for ordinary retrieval. Superseded records remain available to audit and history workflows but are excluded from current-context use unless the user explicitly requests history.

### 11.2 Data classification reference

Memory sensitivity classification (`FR-MEM-003`, `FR-MEM-009`) uses the tiers defined once, canonically, in `ADD §7.1` (T0–T3). This document does not restate the tier definitions to avoid the two documents drifting out of sync — always resolve a sensitivity question against `ADD §7.1`.

### 11.3 Agent lifecycle

An agent run progresses through `CREATED`, `PLANNING`, `READY`, `RUNNING`, `WAITING_APPROVAL`, `WAITING_EXTERNAL`, and a terminal state of `COMPLETED`, `FAILED`, or `CANCELLED`. Every transition has a timestamp, actor or service principal, reason code, and correlation identifier. A terminal run cannot be resumed by an ordinary retry without creating a new attempt or an explicitly safe recovery action.

### 11.4 Deletion lifecycle

Account deletion and memory deletion are user-visible workflows, not a single database statement. A request is recorded as `REQUESTED`, active retrieval is blocked immediately, dependent cleanup jobs are scheduled, and the request moves through `IN_PROGRESS`, `COMPLETED`, or `FAILED_RETRYABLE`. A retryable failure identifies the affected store and next action without making the user repeat the original request.

## 12. Error and recovery behavior

Errors must be understandable to the user and actionable to the system:

- **Validation errors** — the request is incomplete or malformed; show the field or action that must be corrected and do not create partial state.
- **Authorization errors** — the caller is not allowed to access the resource or perform the action; do not reveal whether another user's resource exists.
- **Consent errors** — the requested context or connector is not covered by current consent; explain the required permission and provide a route to review it.
- **Transient dependency errors** — a model, queue, database, or connector is temporarily unavailable; preserve the request where safe, show a retryable status, and avoid duplicate external writes.
- **Policy or safety refusal** — the system cannot perform the requested action under product policy; explain the boundary and offer a safe alternative when one exists.

No user-facing success message is emitted until the corresponding state change is durable. For asynchronous work, the interface states that processing is pending and provides a status view rather than implying completion.

### 12.1 Notifications and user communication

Notifications are optional for the initial MVP, but the functional contract stays consistent whether a user is watching the screen or returns later. A notification may report that an agent needs approval, a long-running task completed, an export is ready, or a deletion workflow requires attention. Notifications never include full private memory, connector tokens, or sensitive tool output.

Every notification links to an authenticated in-product status view. Users can disable non-essential notifications while retaining security and legally required account messages.

### 12.2 Accessibility and inclusive interaction expectations

Core workflows must be usable with keyboard navigation, screen readers, adequate contrast, visible focus indicators, and text alternatives for voice or visual content. Streaming responses expose meaningful status updates to assistive technology. Approval dialogs identify the exact action, destination, data being disclosed, and available cancel path without relying on color alone.

### 12.3 Functional traceability and evidence

Each implemented requirement links to at least one user journey, API or UI behavior, and verification artifact. Evidence may be an automated test, an evaluation case, a security test, or a reviewed manual acceptance script. Requirements involving deletion, consent, authorization, or external writes require negative-path evidence as well as the happy path.

## 13. Functional specification interpretation guide

This document defines the behavior users and operators should be able to rely on. The tables are normative requirements; this section describes their intended meaning so a requirement is never implemented as an isolated screen or endpoint.

**Scope and product boundaries.** The scope describes the smallest trustworthy product boundary. In-scope capabilities must work together: identity controls access, conversation creates context, memory governs what can persist, and privacy controls how that context is reused.

**Actors and responsibility.** An actor is a source of authority or responsibility, not necessarily a separate deployable service. Administrators operate the platform and should not routinely read user content.

**Requirements and acceptance meaning.** "Shall" statements are testable obligations. A requirement is incomplete if it only describes the happy path — invalid input, denied authorization, missing consent, stale data, dependency failure, cancellation, retry, and deletion behavior must be defined for each requirement.

**Domain relationship model.** Identity establishes ownership; conversation records interaction; memory stores approved durable context; beliefs store uncertain propositions; decisions organize trade-offs; agents execute tasks; and privacy and safety govern all of them. A belief must never be displayed as a confirmed profile fact, and a chat message must never automatically become durable memory.

**User journey interpretation.** Journeys describe observable sequences, not implementation steps. Every journey has a visible beginning, an honest intermediate state, and a verifiable end state.

**Business-rule interpretation.** Business rules are cross-feature invariants enforced in application services and background workers, not only in the UI. A mobile client, API caller, queued job, and model-generated plan must receive the same authorization and privacy outcome.

**Non-functional requirement interpretation.** Availability without privacy is not success; low latency without correct grounding is not success. When a target cannot be met, the product degrades gracefully and communicates the limitation instead of producing a misleading success.

**MVP acceptance philosophy.** The MVP is complete when the core trust loop is demonstrably reliable: the user can provide information, see how it is represented, use it in a relevant interaction, correct it, and remove it. Agent actions, decision support, and integrations are valuable only when they preserve that loop. A large feature count does not compensate for incorrect memory, hidden disclosure, unauthorized action, or unreliable deletion.
