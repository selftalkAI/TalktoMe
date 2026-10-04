# Brain 1 — Specification

> **Status:** Approved baseline — proposed defaults in §22 adopted 2026-10-03 (changeable any time) · **Model:** Ollama `llama3.1` until a stronger provider is configured · **Build:** staged, see the build-phases section · **Last updated:** 2026-10-03
> **Formal docs:** ADD / FSD / TDD **V03** reference this spec as authoritative for its scope.
> **Owner:** SelfTalk · **Related:** `Docs/selfieMe_Architecture_Design_Document.md` (ADD), `Docs/selfieMe_Technical_Design_Document.md` (TDD), `agentic-service/app/agents/`, `orchestration-service/app/brain2/`

**How to read this document**

| If you want to know… | Read |
|---|---|
| What Brain 1 is and why we need it | Part I (§1–4) |
| **The structured profile — Brain 1's model of the person** | **§8** |
| How it is designed | Part II (§5–13) |
| **How it will behave once built** | **Part III (§14–16)** |
| How we will build it, step by step | Part IV (§17–22) |
| The full list of 68 sub-agents | Appendix A |
| The analysis that led here | Appendix B |

---

# Part I — What and why

## 1. Summary

Brain 1 is a **living, agentic model of the person** using selfie.Me. It is made of
**13 core agents** (one per area of life — Identity, Mind, Body, Behaviour,
Relationships, Work, Money, Growth, Lifestyle, Meaning, Life Story, Safety, Here & Now), which
together own **68 sub-agents** (Parenting, Sleep, Motivation, Self-Talk, …).

Brain 1 is **never empty**. It starts with a **base of expert knowledge** distilled from
ten books on psychology and behaviour change, then **evolves** in two ways:

- from **User 1** — everything the person says or does teaches it who they are;
- from **Brain 2** — every coaching reply is scored by how it landed, so Brain 1 learns
  what actually works *for this person*.

At its centre is the **Brain 1 Profile** (§8): one structured, evidence-backed model of
the whole person — identity, people, inner world, body, life map, places, tastes,
goals, story, what works — that grows over time until it is, in effect, the person's
second brain.

Brain 1 never talks to the user. Before every reply it gives **Brain 2** (the LLM) a
short, rich **Context Pack** (compiled from the profile) and picks the right **persona**
for the moment — a **voice** (friend, big sister, mother-like, mentor, coach…), an
**expertise** (fitness coach, financial analyst, parenting guide…) and a **stance**
(listen, motivate, plan, teach, challenge, celebrate, mirror, ask) — so Brain 2 speaks
to *this* person, in the way she needs right now, instead of to "a user."

## 2. The problem today

Brain 2's replies are vague, generic and ordinary. Reviewing the code (Appendix B)
showed why — it is an **input** problem, not a wording problem:

1. **Brain 2 knows almost nothing about the person** — name, age, location, interest
   tags, a quote, and minutes logged. No family load, schedule, mood, history, or what
   has helped before.
2. **The prompts compensate with rules** — ~550 words of "be specific, be warm, don't
   invent, don't ask, under 55 words" over ~10 lines of facts. There is nothing specific
   to be specific *about*, so the model falls back to platitudes.
3. **The ten expert books are already loaded (4,857 chunks) but no agent uses them.**
4. **A small local model** (`llama3.1` 8B) is doing all the reasoning.

Brain 1 fixes (1) and (3) directly, and (2) indirectly — with a rich brief, Brain 2's
prompts can become short.

## 3. What Brain 1 is

### 3.1 Definition

The ADD says *"where this document says 'the user', it means Brain 1"*, and makes
Brain 1's acceptance the only path to durable writes (ADR-007, ADR-014). This spec
**keeps that** and adds a second half:

```
BRAIN 1  =  the Human            +   the Persona
            (User 1 — the real       (the agentic model of User 1 that
             person; the only         selfie.Me builds and maintains on
             authority)               their behalf — this spec)
```

- **The Human** decides. Nothing becomes durable without their acceptance.
- **The Persona** understands. It is the 13 core agents, their sub-agents, and
  everything they know — on the human's behalf, under the human's control.
- **Brain 2** speaks. It takes on the persona Brain 1 picked, reads the Context Pack, and talks to the Human.

> ⚠️ The ADD §"Two Brains" lens needs a one-line update to name the Persona as part of
> Brain 1 once this spec is approved.

### 3.2 Brain 1 vs Brain 2 vs User 1

| | Brain 1 — Human | Brain 1 — Persona | Brain 2 — Voice |
|---|---|---|---|
| What it is | The real person | 13 core agents + 68 sub-agents + knowledge | One LLM speaking through many personas + existing brain-region agents |
| Talks to the user? | — | **Never** | Yes |
| Decides what's durable? | **Yes — only one** | No — proposes | No — proposes |
| Knows experts' knowledge? | — | Yes (books, Base layer) | Via the brief |
| Knows this person? | — | Yes (Personal + Learned layers) | Via the brief |
| Code home (planned) | — | `orchestration-service/app/brain1/`, `agentic-service/app/persona/` | `orchestration-service/app/brain2/`, `agentic-service/app/agents/` |

### 3.3 Glossary

| Term | Meaning |
|---|---|
| **Core agent** | One of 12 agents, each owning one life area. A real agent: goal, tools, loop, memory. |
| **Sub-agent** | One narrow lens inside a core (e.g. Parenting). A lightweight tool the core calls. |
| **Signal** | One sub-agent's structured finding, e.g. `{energy: low, reason: "kids sick", confidence: 0.7}`. |
| **Area summary** | A core's ≤ 3-line merge of its sub-agents' signals. |
| **Persona Brief** | All area summaries + standing context, ≈ 10–15 lines, handed to Brain 2. |
| **Facet** | A durable thing the Persona knows about the person in one area (e.g. "evenings after 8 pm are her only free window"). |
| **Principle card** | One piece of expert knowledge distilled from a book: when it applies, what to do, when not to. |
| **Open question** | Something a core doesn't know yet and wants Brain 2 to ask, at the right moment. |
| **Outcome** | How the person responded to a coaching reply — used to learn what works for them. |

## 4. What it is for

### 4.1 Uses

| For | Use |
|---|---|
| **The person** | A coach that actually knows them: remembers their kids, their schedule, their bad week, what helped last time — and speaks the way they like. |
| **The person** | A **mirror**: over time, the Persona can show them their own patterns and growth ("you've bounced back from every missed week since July"). |
| **Brain 2** | A rich, trustworthy brief, so replies are specific, grounded in expert knowledge, and in the right role. |
| **Brain 2** | Knows when it *doesn't* know — and asks one good question instead of guessing. |
| **Safety** | A Safety Core that checks every message first and can stop coaching when care is needed instead. |
| **Legacy** | The Persona, its facets and its Life Story become the long-term record of who the person was and how they grew — the experiential legacy for their children. |
| **The product** | Any new life area (cooking, reading, finance…) plugs in as a core/sub-agent definition, not new code. |

### 4.2 Non-goals

- **Not a planner** — no task lists, forms or dashboards (see product vision: *mirror, not planner or journal*).
- **Not a therapist** — it uses evidence-based coaching knowledge, but never diagnoses, and hands off to real help when the Safety Core says so.
- **Not autonomous over the person** — it never writes durable facts, changes goals, or acts externally without the person's acceptance.
- **Not a talker** — the Persona never speaks to the user; only Brain 2 does.

---

# Part II — Design

## 5. Design principles

1. **The human decides.** The Persona proposes; only the person's acceptance makes something durable (ADR-007, ADR-014).
2. **Never empty, never final.** Starts from expert knowledge (Base); the person's own truth (Personal) always overrides it.
3. **Never invent.** No data → the signal says `unknown` → Brain 2 asks. Brain 1 itself follows Kahneman's warning: don't conclude much from little evidence.
4. **One engine, many definitions.** Cores, sub-agents and principle cards are config (YAML), not classes. A new area = a new definition.
5. **Built on the memory layer.** Facets and learned strategies live in the existing `memories` / `profile_entries` pipeline — no parallel data model.
6. **Agency at the core level.** 13 cores are real agents; 68 sub-agents are lightweight tools. Keeps cost, speed and debugging sane.
7. **Safety first, always.** The Safety Core runs before anything else and can stop coaching.
8. **Privacy by area.** Each core enforces its sensitivity tier; T3 areas (health, finances) need explicit opt-in (ADD §7).
9. **Explainable.** Every conclusion links to its evidence: the memories, check-ins, and principle cards it used.
10. **Mirror, not planner.** Everything the Persona learns is ultimately in service of showing the person back to themselves.

## 6. Architecture

```
                         ┌──────────────────────────── BRAIN 1 · PERSONA ───────────────────────────────┐
                         │                                                                               │
 User 1 message ───────▶ │ 1 Safety Core ──stop?──▶ (care response, no coaching)                         │
 (or silence / event /   │      │ ok                                                                     │
  schedule)              │ 2 Router ── picks 2–4 cores                                                    │
                         │      │                                                                        │
                         │ 3 Core agents (think → act → check)  ◀──▶  Shared workspace (cores talk)      │
                         │      │  tools: search_memories · search_books · get_principles ·              │
                         │      │         ask_core · propose_facet · queue_question · get_checkins       │
                         │      ▼                                                                        │
                         │   Sub-agents (one lens each) → signals → area summaries                       │
                         │      │                                                                        │
                         │ 4 Context Pack compiler + PERSONA SELECTOR (voice · expertise · stance)       │
                         └──────┼────────────────────────────────────────────────────────▲──────────────┘
                                ▼                                                         │ outcome
                         ┌──────────────── BRAIN 2 · VOICE ───────────────┐                │ (how the reply
                         │ wears the persona → plans → speaks → checks    │ ── reply ──▶ User 1
                         └────────────────────────────────────────────────┘                │  landed)
                                                                                           │
            KNOWLEDGE  ┌──────────────┬───────────────────┬────────────────────┐           │
                       │ BASE (books) │ LEARNED (what     │ PERSONAL (who she  │ ◀─────────┘
                       │ cards + RAG  │ works for her)    │ is — facets)       │
                       └──────────────┴───────────────────┴────────────────────┘
                                    all stored in the existing memory layer
```

**Components**

| Component | Responsibility |
|---|---|
| **Safety Core** | Runs first on every input. `ok` / `concern` / `crisis`. Crisis stops coaching. |
| **Router** | Chooses 2–4 relevant cores from the message, active domain, and recent context. |
| **Core agents ×13** | Investigate their area with tools; merge sub-agent signals; maintain facets and open questions. |
| **Sub-agents ×68** | One lens each; emit one signal. |
| **Shared workspace** | Per-turn scratchpad where cores post findings and ask each other questions. |
| **Brief builder** | Merges area summaries + standing context into the Context Pack (§8.6). |
| **Persona Selector** | Picks Brain 2's persona for this reply: voice × expertise × stance (§12.4). Respects her own choice when she has made one. |
| **Knowledge service** | Principle cards (Base), book search (RAG), learned weights (Learned), facets (Personal). |
| **Outcome scorer** | Scores the person's next message to learn which principles, personas and stances worked. |
| **Reflector** | Scheduled job: consolidates patterns, updates confidence, proposes facets. |
| **Question queue** | Open questions from cores, prioritised, for Brain 2 to ask naturally. |

## 7. Agent hierarchy — 13 core agents and their sub-agents

**What a core agent does**
1. **Owns its area** — its sub-agents, its facets, its sensitivity tier.
2. **Wakes only the sub-agents that matter** for this input.
3. **Investigates** with tools (memories, books, check-ins, other cores) until confident or out of steps.
4. **Merges** signals into one ≤ 3-line area summary, resolving conflicts.
5. **Flags unknowns** as open questions.
6. **Learns** — proposes new facets when evidence is strong enough.

**What a sub-agent does** — one narrow lens: reads its facet + relevant memories + the
input, emits one signal (or `unknown`). Never talks to the user or Brain 2 — only to its core.

### 7.1 The 13 Core agents

| # | Core Agent | The question it answers | Sub-agents | Privacy default | Always on |
|---|---|---|---|---|---|
| C1 | **Identity Core** | Who is this person? | Personality, Values, Identity & Self-Image, Beliefs & Worldview, Strengths, Culture & Heritage (6) | Shared | No — but its summary is cached into every brief |
| C2 | **Mind Core** | How are they thinking and feeling right now? | Emotion, Stress & Resilience, Self-Talk, Self-Worth, Mindset, Focus & Attention, Decision-Making, Fears & Anxieties (8) | Ask first | No |
| C3 | **Body Core** | What state is their body in? | Fitness, Nutrition, Sleep, Energy, Health Conditions, Body Image, Hormonal & Life-Stage Health (7) | Private for conditions / hormonal; shared otherwise | No |
| C4 | **Behaviour Core** | Why do they act — or not act — the way they do? | Motivation, Habits, Readiness for Change, Barriers, Discipline & Consistency, Goals (6) | Shared | No |
| C5 | **Relationships Core** | Who is in their life, and how do those people shape what they can do? | Partner / Marriage, Parenting, Family, Friendships, Community, Communication Style, Social Support (7) | Ask first for Partner; shared otherwise | No — but Communication Style is read on every turn |
| C6 | **Work Core** | How is work shaping their life? | Career, Productivity, Professional Skills, Work-Life Balance, Leadership & Influence (5) | Shared | No |
| C7 | **Money Core** | How do money and security affect them? | Spending, Saving & Investing, Money Mindset, Financial Goals (4) | Private | No |
| C8 | **Growth Core** | What are they learning and becoming better at? | Learning Style, Skills, Reading & Knowledge, Curiosity & Interests, Creativity (5) | Shared | No |
| C9 | **Lifestyle Core** | What does their day actually look like? | Daily Rhythm, Home & Environment, Leisure & Hobbies, Digital Habits, **Places, Tastes & Preferences, Rituals & Comforts** (7) | Shared (exact addresses T2 "ask first") | No — but Tastes and Places feed every brief's hooks |
| C10 | **Meaning Core** | What gives their life meaning? | Purpose, Spirituality & Faith, Gratitude & Joy, Legacy (4) | Private for Faith; shared otherwise | No |
| C11 | **Life Story Core** | How has their life changed, and how have they grown? | Life Events, Growth Narrative (2) | Shared | No — but recent Life Events are cached into every brief |
| C12 | **Safety Core** | Is it safe to coach right now? | Wellbeing Guard, Boundaries & Consent (2) | — | **Yes — runs first on every message, can veto coaching** |
| C13 | **Here & Now Core** | What is her world like *right now*? | Weather, Time & Season, Local Calendar & Events, Today's Schedule, Current Place (5) | City-level by default; precise location only with opt-in | **Yes — cached, refreshed on every turn** |

**Total: 13 core agents · 68 sub-agents.**

### 7.2 Core agent → sub-agent detail

**C1 · Identity Core** — *who they are (stable)*
| Sub-agent | Signal it emits |
|---|---|
| Personality | Trait profile (Big Five) → how to approach them |
| Values | Top values → the "why" to connect goals to |
| Identity & Self-Image | Who they see themselves as / want to become |
| Beliefs & Worldview | Beliefs that help or limit them |
| Strengths | Strengths to build on |
| Culture & Heritage | Cultural context, traditions, language |

**C2 · Mind Core** — *thoughts and feelings (changes daily)*
| Sub-agent | Signal it emits |
|---|---|
| Emotion | Current mood + intensity |
| Stress & Resilience | Stress load; bounce-back capacity |
| Self-Talk | Thinking trap detected (e.g. all-or-nothing) |
| Self-Worth | Confidence vs. self-criticism |
| Mindset | Growth vs. fixed framing |
| Focus & Attention | Distracted / procrastinating / focused |
| Decision-Making | Stuck, avoidant, impulsive, or clear |
| Fears & Anxieties | Fear that's holding them back |

**C3 · Body Core** — *physical state*
| Sub-agent | Signal it emits |
|---|---|
| Fitness | Activity vs. target, ability level |
| Nutrition | Eating pattern, cooking capacity |
| Sleep | Sleep quality trend |
| Energy | Energy level now / daily rhythm |
| Health Conditions | Limitations to respect |
| Body Image | Feelings about their body |
| Hormonal & Life-Stage Health | Life-stage factors affecting energy / mood |

**C4 · Behaviour Core** — *action and change*
| Sub-agent | Signal it emits |
|---|---|
| Motivation | Own reasons vs. pressure; autonomy / competence / relatedness |
| Habits | Cue → routine → reward; what's easy / hard |
| Readiness for Change | Stage: thinking → preparing → doing → maintaining |
| Barriers | Real blocker: capability, opportunity, or motivation |
| Discipline & Consistency | Follow-through pattern |
| Goals | Is the goal clear, realistic, on track? |

**C5 · Relationships Core** — *people in their life*
| Sub-agent | Signal it emits |
|---|---|
| Partner / Marriage | Shared load, support from partner |
| Parenting | Parenting load, kids' needs, routines |
| Family | Wider family demands / support |
| Friendships | Connection or loneliness |
| Community | Belonging, groups |
| Communication Style | Gentle / direct, short / detailed, tough love / comfort |
| Social Support | Who to lean on when it's hard |

**C6 · Work Core**
| Sub-agent | Signal it emits |
|---|---|
| Career | Satisfaction, ambition, direction |
| Productivity | Work habits, time pressure |
| Professional Skills | Growth in their field |
| Work-Life Balance | Overload / boundary signals |
| Leadership & Influence | How they lead and collaborate |

**C7 · Money Core**
| Sub-agent | Signal it emits |
|---|---|
| Spending | Spending pattern, impulse signals |
| Saving & Investing | Security / progress |
| Money Mindset | Money stress, beliefs |
| Financial Goals | Big goals and progress |

**C8 · Growth Core**
| Sub-agent | Signal it emits |
|---|---|
| Learning Style | How they learn best (watch / read / do) |
| Skills | Current level → next step (uses WorldKnowledge) |
| Reading & Knowledge | What they're absorbing |
| Curiosity & Interests | What draws them in right now |
| Creativity | Creative outlets and energy |

**C9 · Lifestyle Core**
| Sub-agent | Signal it emits |
|---|---|
| Daily Rhythm | Busy hours, free windows, best time for a habit |
| Home & Environment | Space / setup helping or hindering |
| Leisure & Hobbies | Rest and recharge |
| Digital Habits | Screen time, distraction |
| Places | Home, work, gym, kids' school, parks, cafés, routes — and how she feels about each |
| Tastes & Preferences | Food and drink (e.g. black coffee), music, activities she loves / dislikes, weather she likes |
| Rituals & Comforts | Small rituals that make hard things easier (morning coffee, a walk, a playlist) |

**C10 · Meaning Core**
| Sub-agent | Signal it emits |
|---|---|
| Purpose | What gives life meaning |
| Spirituality & Faith | Practices to respect / draw on |
| Gratitude & Joy | What brings them happiness |
| Legacy | What they want to pass on to their kids |

**C11 · Life Story Core**
| Sub-agent | Signal it emits |
|---|---|
| Life Events | Recent big change affecting everything else |
| Growth Narrative | Then → now; progress worth reflecting back |

**C12 · Safety Core** — *always on, runs first*
| Sub-agent | Signal it emits |
|---|---|
| Wellbeing Guard | `ok` / `concern` / `crisis` → crisis stops coaching and points to real help |
| Boundaries & Consent | Topics / areas not to mention |

**C13 · Here & Now Core** — *always on, cached per turn*
| Sub-agent | Signal it emits |
|---|---|
| Weather | Now + today's forecast for her city (rain, snow, heat, daylight, sunset) |
| Time & Season | Time of day, weekday/weekend, season, school term vs holidays |
| Local Calendar & Events | Public holidays, school closures (e.g. snow day), local events |
| Today's Schedule | Her known commitments today (from routines; later the Calendar connector) |
| Current Place | Home city by default; travelling? (only with opt-in) |

### 7.3 How cores work together

| Rule | Example |
|---|---|
| **Safety Core first, always** | If Wellbeing Guard says `crisis`, no coaching — only care and real-help resources. |
| **Identity + Life Story are context for all** | Their cached summaries go into every brief, even when not routed. |
| **Communication Style shapes every reply** | Read every turn, even when Relationships Core isn't routed. |
| **Cross-core questions** | Body Core (low energy) checks Relationships Core (sick kids) and Lifestyle Core (no sleep window) before concluding "low motivation." |
| **Privacy enforced by the core** | Money Core's details stay out of the brief unless the user brought money up or allowed it. |
| **Unknowns bubble up** | If a core has no data, its summary says so → Brain 2 becomes the Curious Asker. |


---

## 8. The Brain 1 Profile — the person's brain, structured

The cores are Brain 1's **processes**. The **Brain 1 Profile** is Brain 1's **state**:
one structured, evidence-backed model of the whole person, which the cores read,
maintain and grow. Over months and years, this profile *becomes* the person's second
brain. It is the single source of truth for *who she is*, and everything Brain 2 says is
compiled from it.

> Today's "profile" is the onboarding row (`profiles`: name, DOB, location, interests,
> quote). That is the seed of section 1 below — not the profile itself.

### 8.1 The structure — 12 sections

> **All examples for "Sujitha" in this spec are illustrative** — children's names, tastes,
> places and times are made up to show the shape of the data, not real facts.

| # | Section | What it holds (example for Sujitha) | Maintained by | Changes |
|---|---|---|---|---|
| 1 | **Identity** | Name, age, home city, roles ("mom of two", "ECE"), languages, culture | Identity Core | Rarely |
| 2 | **People** | Each person who matters: *Aarav, 10, son — plays soccer Saturdays*; *Mira, 7, daughter*; partner; parents; close friends; who helps with what | Relationships Core | Slowly |
| 3 | **Inner world** | Values, purpose, personality, strengths, fears, mindset, self-talk patterns ("all-or-nothing when tired") | Identity · Mind · Meaning | Slowly |
| 4 | **Body & health** | Fitness level, activity history, sleep pattern, energy rhythm, eating habits; conditions (T3, opt-in only) | Body Core | Weekly |
| 5 | **Life map** | Weekday and weekend timeline (up 6:00, drop-off 8:15, pickup 3:00, bedtime 8:30); **places** (home, work, the gym 10 min away, the park on her route, her favourite café) | Lifestyle Core | Weekly |
| 6 | **Tastes & rituals** | Black coffee, no sugar · loves rainy mornings, hates the cold · upbeat 90s playlists · enjoys walking, dislikes treadmills · Sunday pancakes with the kids | Lifestyle Core | Slowly |
| 7 | **Goals & journeys** | Each active goal with her *own* reason in her words ("to feel like me, not just mom"), stage of change, target, progress, setbacks, milestones | Behaviour Core | Daily |
| 8 | **Story & memory** | Life events timeline · a summary of every past conversation · her key quotes · commitments she made · **open threads** (things to follow up) | Life Story Core + Hippocampus | Every conversation |
| 9 | **What works for her** | Strategies, personas and stances with outcomes ("two-minute rule 4/5", "big-sister voice → she opens up", "tough love → silence") | Learned layer (§9) | Every conversation |
| 10 | **Communication** | How she likes to be spoken to: gentle, short, emojis yes/no, humour, language · **voices she has asked for** ("talk to me like a sister") and **voices to avoid** (e.g. no father voice — her dad passed away) | Relationships · Communication Style | Slowly |
| 11 | **Boundaries & consent** | Topics to avoid, opt-ins (T3), how often she wants check-ins | Safety Core | On request |
| 12 | **Open questions** | What Brain 1 doesn't know yet, with priority | All cores | Constantly |

Plus one **live** section that is computed, never stored long-term:

| Live | **Here & Now** | Weather and forecast for her city, time, day type, season, school term, holidays, today's schedule, her state today (mood/energy) | Here & Now Core + Mind/Body | Every turn |

### 8.2 Every field carries its evidence

Nothing in the profile is a bare value. Each field is a record:

```yaml
field: tastes.morning_drink
value: "black coffee, no sugar"
source: said            # said | onboarding | inferred | connector
evidence:               # where it came from
  - memory: mem_8f2a  — "I can't function before my black coffee" (2026-10-06)
confidence: 0.95
status: confirmed       # hypothesis | confirmed | superseded
tier: T2
owner: lifestyle.tastes_preferences
last_confirmed: 2026-10-06
```

This is what lets Brain 1 (and the person) always answer **"how do you know that?"**, lets
corrections replace a value cleanly, and lets confidence grow or decay over time.

### 8.3 Memory of conversations — three levels

Brain 2 must remember previous conversations the way a good coach does — not by
re-reading every transcript.

| Level | What | Kept | Used for |
|---|---|---|---|
| **Working memory** | The last ~10 turns, verbatim | This conversation | Natural flow; never repeating itself |
| **Episodic memory** | One summary per conversation: what happened, how she felt, her key quotes, what she committed to, what was left open | Forever (her story) | "Last week you said…"; following up |
| **Semantic memory** | The profile fields themselves (§8.1) | Forever, versioned | Knowing her |

After every conversation the Hippocampus **consolidates**: working → episodic summary →
profile updates (facts proposed to their owning core; durable ones need confirmation).

### 8.4 How the profile is built and how it evolves

| Source | What it adds | Example |
|---|---|---|
| **Onboarding** | Identity seed, interests, quote | Name, age, Langley BC, "Kind people raise kind humans" |
| **Every message** | Facts, tastes, places, people, feelings — extracted by Hippocampus and routed to the owning core | "Mira's school closed for snow" → People (Mira), Here & Now (snow day) |
| **Curious questions** | One natural question at a time, filling the highest-priority gap | "What's your go-to drink in the morning?" |
| **Check-ins** | Goal progress and patterns | 15 → 20 → 45 min |
| **Reflection (nightly)** | Patterns and hypotheses across weeks | "Misses track caregiving load" |
| **Outcomes from Brain 2** | What works for her | "Rainy-day home workouts: 3/3 done" |
| **Connectors (later)** | Calendar, weather, location | Today's schedule; current city |
| **The person, directly** | Corrections and edits in the mirror view | "I don't drink coffee anymore" → superseded |

Every change creates a new **version** of the profile. Brain 1 at month 1 and Brain 1 at
month 12 can be compared — that history is the person's growth, and their legacy.

### 8.5 When Brain 1 becomes "the brain of the user"

Brain 1 doesn't just store; over time it can **anticipate**. It makes small, private
predictions and checks them against what actually happens:

| Prediction (private) | Reality | Result |
|---|---|---|
| "Rainy Monday + kids home → she'll skip the gym" | She skipped | ✓ |
| "She'll say yes to a coffee-and-walk idea" | She did it | ✓ |
| "She'll want to talk about work today" | She didn't | ✗ → lower confidence |

**Brain Strength** — how well Brain 1 knows her — is measured, not guessed:

| Measure | Meaning |
|---|---|
| **Coverage** | How many profile sections have confirmed fields |
| **Confidence** | Average confidence of the fields that matter now |
| **Prediction accuracy** | How often Brain 1's private predictions come true |
| **Correction rate** | How often she corrects it (should fall over time) |

When Brain Strength is high, Brain 1 can act ahead of time: suggest the rainy-day plan
*before* she skips, notice a hard week coming from the calendar, and speak the way she'd
want to be spoken to without being told.

### 8.6 From profile to the LLM — the Context Pack

Brain 2's LLM never sees the raw profile. For every reply, Brain 1 **compiles** a
**Context Pack**: the parts of the profile that matter *for this moment*, in a fixed
structure, in plain language, within a token budget.

**Compile steps**
1. **Always included:** Identity (1–2 lines), Communication style, Boundaries, current goal + her reason in her words.
2. **Selected by relevance** to her message, the active goal and the coach's plan: the relevant People, Places, Tastes, Body, Inner-world fields.
3. **Here & Now:** weather, time, day type, today's schedule, her state today.
4. **Story:** the last conversation's summary, any open thread, any commitment due, 1–3 of her own quotes.
5. **What works / avoid** for her.
6. **Hooks** (below).
7. **Unknowns** that matter now, so the coach asks instead of guessing.
8. **Privacy filter:** T3 removed unless opted in; "ask first" fields only if she raised them.

**Hooks — where the profile meets the moment**

A hook is a ready-to-use, grounded connection between who she is and what's happening
now. Brain 1 finds them; Brain 2 uses at most one or two, naturally.

| Moment | Profile | Hook |
|---|---|---|
| Rain this morning, 9°C | Loves rainy mornings · black coffee · free 6:15–6:45 before kids wake · home workout OK | "Rainy-morning ritual: black coffee, then 15 minutes by the window before the house wakes up." |
| Snow day — school closed | Kids home · loves doing things *with* them · hates the cold, loves hot chocolate | "Snow-day story: building a snow fort with Aarav and Mira is a real workout — 30 minutes outside, then hot chocolate together." |
| Sunny Saturday, 18°C | Aarav's soccer at 10 · park next to the field | "Walk laps of the park while Aarav plays — the whole match is a workout." |
| Exhausted after a sick-kid week | Two-minute rule works for her · values "feeling like me" | "Tonight, two minutes counts — it keeps the 'me' habit alive." |

Each hook lists its sources (profile fields + Here & Now), so it can never be invented.

**Context Pack example**

```text
WHO SHE IS
Sujitha, 41, Langley BC. Mom of Aarav (10) and Mira (7); early-childhood educator.
Values kindness and family; "Kind people raise kind humans." Speak gently, briefly; no tough love.

HER GOAL
Gym 60 min/day — currently a 15-min stepping stone, 3x/week. Her reason, in her words:
"to feel like me, not just mom." Stage: action (early).

HER WORLD TODAY
Monday 6:05 am, light rain, 9°C, sunset 6:40 pm. School day. Free window 6:15–6:45 before
kids wake; packed after 3 pm (pickup, homework, dinner). Slept badly (Mira coughing).

THINGS SHE LOVES (relevant now)
Rainy mornings. Black coffee, no sugar. Walking more than treadmills.

STORY SO FAR
Last talk (Sat): she did 20 min and felt "proud but tired". She said she'd try Monday morning.
Open thread: whether a home workout "counts" for her.

WHAT WORKS / AVOID
Works: tiny versions (4/5), linking to "feeling like me". Avoid: pushing harder, long lists.

PERSONA FOR THIS REPLY
Voice: friend · Expertise: fitness coach · Stance: gentle strategist

HOOK
Rainy-morning ritual: black coffee, then 15 min by the window before the house wakes up.

UNKNOWN (ask only if natural)
Does a home workout count as "the gym" for her?
```

This is what makes the answer exact: the LLM is no longer guessing who she is — it is
handed a clear, current, evidence-backed picture and one plan.

---

## 9. Knowledge — Brain 1 is never empty

Brain 1 starts with a **base of expert knowledge** from the ten books in
`Docs/ASSETS/BOOKS/`, and evolves with input from User 1 and with what it learns from
Brain 2's conversations.

**What exists today**
- All ten books are **already ingested**: `rag_documents` scope `knowledge_base`,
  **4,857 chunks** in Chroma (`orchestration-service/scripts/ingest_pdfs.py`).
- **No agent uses them** — `WorldKnowledge` asks the LLM from general memory.
- `rag_manager.retrieve` blends similarity with **recency** — right for user documents,
  wrong for books. Book search must use similarity only.
- **Feeling Good** and **Self-Compassion** are **Bookey summaries**, partly truncated —
  not the full books. The other eight are full texts.

### 9.1 Three layers of knowledge

```
 ┌───────────────────────────────────────────────────────────────┐
 │ 3. PERSONAL   What is true about THIS person                   │  ← User 1 input (memories, facets)
 │               "Sujitha prefers gentle tone; mornings are free" │     highest priority
 ├───────────────────────────────────────────────────────────────┤
 │ 2. LEARNED    What has WORKED for this person                  │  ← outcomes of Brain 2's conversations
 │               "2-minute rule: worked 4/5; tough love: silence" │
 ├───────────────────────────────────────────────────────────────┤
 │ 1. BASE       What experts know about humans in general        │  ← the ten books (+ more later)
 │               "Never miss twice" · "Ask permission before advice"│     same for everyone, versioned
 └───────────────────────────────────────────────────────────────┘
 Precedence: Personal > Learned > Base.  Base is the starting point, never the final word.
```

### 9.2 Layer 1 — the Base, from the books

Two forms, used together:

1. **Principle cards (distilled, always loaded).** Each book is distilled, chapter by
   chapter, into small structured cards: *a principle, how to detect when it applies,
   what to do, when NOT to use it, and its source*. Cards are reviewed by you, versioned
   in the repo, and attached to the cores they serve. These make every core "know" its
   field from day one.
2. **Book search (raw, on demand).** For depth and exact wording, cores call
   `search_books`, which retrieves the already-ingested chunks.

**Example principle card**
```yaml
id: AH-4.4-never-miss-twice
source: Atomic Habits — Ch.16 "How to Stick with Good Habits Every Day"
cores: [behaviour]
sub_agents: [habits, discipline_consistency]
principle: Missing once is an accident; missing twice is the start of a new habit.
detect:
  - checkin missed today AND yesterday was done
intervene:
  - Make the very next session tiny (Two-Minute Rule, AH-3.4) so the chain resumes
contraindications:
  - Safety Core concern/crisis
  - Body Core: illness or injury → rest is the right call
coach_roles: [strategist]
default_weight: 0.7
```

### 9.3 The ten books → what each gives Brain 1 and Brain 2

| Book | Core frameworks (from the text) | Feeds |
|---|---|---|
| **Motivational Interviewing** (Miller & Rollnick, 3rd ed.) | Spirit = Partnership, Acceptance, Compassion, Evocation · 4 processes: Engaging → Focusing → Evoking → Planning · OARS (Open questions, Affirmations, Reflections, Summaries) · Change talk **DARN** (Desire, Ability, Reason, Need) + **CAT** (Commitment, Activation, Taking steps) vs. sustain talk · Importance/Confidence rulers · Elicit–Provide–Elicit · Ask permission before advice · Traps to avoid: righting reflex, expert, assessment, question–answer, premature focus · Stages of change | **Brain 2's conversation engine** (how the coach talks) · Behaviour Core (Readiness, Motivation) |
| **Atomic Habits** (Clear) | Identity-based habits (outcomes → processes → identity) · Four Laws: obvious, attractive, easy, satisfying (and inversions) · Habits Scorecard · Implementation intention "I will [X] at [time] in [place]" · Habit stacking · Two-Minute Rule · Environment design · Never miss twice · Plateau of Latent Potential · Goldilocks Rule | Behaviour Core (Habits, Barriers, Discipline, Goals) · Identity Core · Lifestyle Core (environment) |
| **Feeling Good** (Burns) — *summary only* | Thoughts create moods · Cognitive distortions: all-or-nothing, overgeneralization, mental filter, disqualifying the positive, jumping to conclusions, magnification, emotional reasoning, should statements, labeling, personalization · Triple-column technique · "Coping, not moping" · Do-nothingism · Work is not your worth · Approval addiction | Mind Core (Self-Talk, Self-Worth, Emotion) |
| **Self-Compassion** (Neff) — *summary only* | Three elements: self-kindness, common humanity, mindfulness · Self-criticism as a threat response · Self-compassionate motivation (vs. self-criticism) · Self-compassion for caregivers · Body · Shame | Mind Core (Self-Worth, Self-Talk) · Relationships (caregiver load) · **Listener** role |
| **Emotional Intelligence** (Goleman) | Five domains: knowing one's emotions, managing emotions, motivating oneself, recognizing emotions in others, handling relationships · Emotional hijacking · Temperament is not destiny · Family emotional patterns | Mind Core (Emotion, Stress) · Relationships Core · Communication Style |
| **Nonviolent Communication** (Rosenberg) | Four components: **Observation** (without evaluation) → **Feeling** → **Need** → **Request** (not demand) · Life-alienating communication: moralistic judgment, comparison, denial of responsibility · Expressing honestly + receiving empathically | **Brain 2's tone** (no judgment, needs-based) · Relationships Core (Partner, Parenting, Family) |
| **Mindset** (Dweck) | Fixed vs. growth mindset · Mindsets change the meaning of failure and of effort · Danger of praising ability vs. process | Mind Core (Mindset) · Growth Core · **Celebrator** role (praise effort, not talent) · Parenting |
| **Flow** (Csikszentmihalyi) | Eight elements of enjoyment: achievable task, concentration, clear goals, immediate feedback, effortless involvement, sense of control, loss of self-consciousness, altered time · Challenge–skill balance · Psychic entropy vs. order · Autotelic personality · Flow in body, thought, work | Growth Core (Skills, Learning) · Lifestyle (Leisure) · Work Core · Meaning Core |
| **Man's Search for Meaning** (Frankl) | The last human freedom: choosing one's attitude · Three ways to meaning: creating a work/doing a deed, experiencing something or loving someone, the attitude toward unavoidable suffering · Self-actualization as a side effect of self-transcendence | Meaning Core (Purpose, Legacy) · Identity (Values) · **Mirror** role |
| **Thinking, Fast and Slow** (Kahneman) | System 1 / System 2 · WYSIATI ("what you see is all there is") · Planning fallacy · Loss aversion · Experiencing self vs. remembering self · Peak–end rule | Behaviour Core (Goals — realistic targets) · Money Core · Life Story Core (remembering self → memories & legacy) · **Brain 1's own guardrail**: don't conclude from too little evidence (WYSIATI) |

### 9.4 Stances → which books drive them

| Stance | Grounded in |
|---|---|
| Listener / Comforter | Self-Compassion, NVC (empathic receiving), MI (reflections) |
| Motivator | MI (evoke DARN-CAT, rulers, looking forward), Frankl (meaning), Atomic Habits (identity) |
| Strategist | Atomic Habits (four laws, implementation intentions, two-minute rule), Kahneman (planning fallacy) |
| Teacher / Expert | Books + WorldKnowledge — always via MI's Elicit–Provide–Elicit and with permission |
| Challenger | MI (developing discrepancy, Goldilocks principle), Dweck (growth mindset) |
| Celebrator | Dweck (praise process/effort), Atomic Habits (make it satisfying), MI (affirmations) |
| Mirror | Frankl, Kahneman (remembering self), Flow, MI (summaries) |
| Curious Asker | MI (open questions; avoid the question–answer trap) |

### 9.5 How Brain 1 evolves

**From User 1 (Personal layer)**
- Every message → Hippocampus → memory write-gate → the sub-agent that owns it.
- Facets gain confidence as evidence accumulates; durable facets need user acceptance.
- Personal facts **override** book defaults ("the book says morning workouts; she works
  nights → evenings").

**From Brain 2 (Learned layer)**
- Every reply records which **principle cards** and **persona** (voice, expertise, stance) it used.
- The next user reply is scored as an **outcome**, using MI's own language as the signal:

  | Outcome signal | Meaning | Effect on that principle (for this person) |
  |---|---|---|
  | Change talk (DARN / CAT) | It moved them | ↑ weight |
  | Did the behavior (check-in) | It worked in real life | ↑↑ weight |
  | Accepted the profile draft | It rang true | ↑ weight |
  | Sustain talk | Neutral — normal ambivalence | — |
  | Discord / pushback | It landed badly | ↓ weight |
  | Silence after it | Possibly landed badly | small ↓ |

- Weights are stored per person in the memory layer (e.g. `memory_type='learned_strategy'`),
  not in a new bespoke table.
- **Reflective mode** consolidates nightly: "For Sujitha: two-minute rule 4/5 success;
  identity framing ('you're someone who moves') led to change talk; challenger tone led to
  silence twice → stop using it."

**Base layer grows too** — but only with human review: new books ingested, new cards
distilled and approved, versioned.

### 9.6 Worked example — all three layers

**Sujitha:** "Couldn't go to the gym today, kids were sick again."

| Layer | What Brain 1 brings |
|---|---|
| Base | Feeling Good: "again" → overgeneralization risk · Self-Compassion: common humanity, caregivers · Atomic Habits: never miss twice, two-minute rule · MI: reflect first, ask permission before advice · NVC: observe without evaluating |
| Personal | Mom of two; gentle tone; evenings after bedtime are her only window |
| Learned | Two-minute rule worked 4 of 5 times; challenger tone → silence |

**Brain 2 (friend voice · fitness coach · Listen → Plan):**
> "Sick kids twice in one week — that's a lot to carry, and it says nothing about how
> committed you are. Last time, a tiny 2-minute version kept your streak alive. Would
> something like that feel doable tonight after bedtime, or is tonight a rest night?"

### 9.7 Gaps in the current ten books

| Gap | Affects | Suggestion |
|---|---|---|
| Feeling Good, Self-Compassion are partial summaries | Mind Core | Get the full books |
| No exercise / sleep / nutrition science | Body Core | e.g. *Why We Sleep* (Walker), a sports-science or nutrition text |
| No parenting book | Relationships (Parenting) | e.g. *How to Talk So Kids Will Listen* (Faber & Mazlish) |
| No money book | Money Core | e.g. *The Psychology of Money* (Housel) |
| No skill-mastery book | Growth (Skills) | e.g. *Peak* (Ericsson) — deliberate practice |
| No motivation theory primary source | Behaviour (Motivation) | Self-Determination Theory (Ryan & Deci) |
| No clinical crisis protocol | Safety Core | Must come from vetted crisis resources, never from self-help books |


---

## 10. Agentic behaviour

A pipeline runs once when spoken to. Brain 1's cores are **agents**:

| # | Ingredient | What it means for a core |
|---|---|---|
| 1 | **Goal** | A standing goal, e.g. Body Core: *"keep an accurate, current picture of her physical state, and close the gaps in it."* |
| 2 | **Tools** | Search memories, search books, get principle cards, ask another core, propose a facet, queue a question, read check-ins |
| 3 | **Loop** | Think → act → check → repeat until confident (max steps, max cost) |
| 4 | **Own memory** | Facets + confidence + open questions, in the memory layer |
| 5 | **Initiative** | Runs on messages, on a schedule, and on events — not only when spoken to |
| 6 | **Collaboration** | Shared workspace; cores ask each other; two-way with Brain 2 |

### 10.1 Three modes
1. **Reactive** — the user speaks → cores investigate → brief → Brain 2.
2. **Reflective** — scheduled (`brain2/scheduler.py` exists): review recent memories, find patterns, update confidence, propose facets.
3. **Curious** — cores turn their open questions into requests for Brain 2 to ask at a good moment.

### 10.2 How a core thinks (Body Core example)
```
Goal: understand why she missed the gym today
 1. THINK  → Fitness: 0 min; Energy: unknown
 2. ACT    → search_memories(domain="sleep", last 7 days) → "kids up at night" x2
 3. ACT    → ask_core("relationships", "caregiving load this week?") → high, sick kids
 4. CHECK  → confidence 0.8 ≥ threshold → stop
 5. OUTPUT → "Missed due to caregiving + poor sleep, not motivation"
            open_question → Brain 2: "Does a home workout count for her?"
```

**Key decision: give the agency to the 13 cores, not the 68 sub-agents.** Cores are
LangGraph think→act→check agents with tools; sub-agents are lightweight tools the core
calls (one LLM call, or rules). This keeps cost, speed, and debuggability sane.

### 10.3 Core tools
| Tool | Built on |
|---|---|
| `search_memories(domain, query, since)` | `memory_repo` (exists) |
| `search_books(query, book?, core?)` | `rag_manager.retrieve` on the `knowledge_base` scope (exists — see §9) |
| `get_principles(core, signal)` | Principle cards (new — see §9) |
| `propose_facet(core, field, value, evidence)` | `profile_store.propose` (exists; user must accept) |
| `ask_core(core, question)` | Shared workspace (new) |
| `queue_question_for_user(question, priority)` | New; Brain 2 asks at the right moment |
| `world_knowledge(domain, context)` | `world_knowledge.py` (exists) |
| `get_checkins(intention)` | `intentions_repo` (exists) |
| `record_outcome(principle_id, outcome)` | New — feeds the Learned layer (§9) |

**Safety rails:** agents propose, code and the user decide (ADR-007 / ADR-014); step and
cost limits per core run; Safety Core runs first and can stop everything; every tool call
is logged so you can see *why* Brain 1 concluded something.

---

## 11. Data model

Everything maps onto the existing storage (`Storage/sql_storage/selfie_me.db` +
Chroma). Two small operational tables are new; no parallel "persona" data model.

| What | Where | How |
|---|---|---|
| **Profile snapshot** | **new table `brain1_profile_versions`** | The compiled 12-section profile (§8.1) as JSON, one row per version — fast to read, and the history of how Brain 1 grew. Rebuilt from facets whenever they change. |
| **Episodic memory** | `memories` type `event` + `domain=conversation` | One summary per conversation: what happened, her quotes, commitments, open threads (§8.3). |
| **Facets** (Personal layer) | `memories` (existing) | `type` = existing types (fact, preference, routine, constraint, relationship, goal, event); `domain` = sub-agent id (e.g. `parenting`); `explicitness` explicit/inferred; `confidence`; `sensitivity_tier` from the core's tier. Inferred facets start as `requires_confirmation`. |
| **Learned strategies** (Learned layer) | `memories` — **new type `learned_strategy`** | e.g. *"Two-minute rule works for her (4 of 5)"*; `domain` = principle card id. **Needs a migration**: the `type` CHECK constraint must allow the new value. |
| **Outcome events** (raw) | **new table `brain1_outcomes`** | Append-only: `run_id, profile_email, card_ids, voice, expertise, stance, outcome, created_at`. Same pattern as `brain2_checkins`. |
| **Open questions** | **new table `brain1_open_questions`** | `core, sub_agent, question, priority, status (open/asked/answered/dropped), created_at`. |
| **Run trace** | **new table `brain1_runs`** | Per turn: cores woken, tool calls, signals, area summaries, brief, cards used, latency, cost. For explainability and the observability portal. |
| **Area narratives** (mirror) | `profile_entries` (existing) | `domain` = core id; versioned; proposed → accepted by the person (ADR-014). |
| **Principle cards** (Base layer) | Repo YAML: `agentic-service/app/persona/knowledge/<core>.yaml` | Versioned in git; reviewed by a human. |
| **Book text** (Base layer) | Chroma `document_chunks`, scope `knowledge_base` (existing) | Retrieved by `search_books`. |
| **Core / sub-agent definitions** | Repo YAML: `agentic-service/app/persona/definitions/` | One file per core, listing its sub-agents. |

## 12. The Brain 1 ↔ Brain 2 contract

### 12.1 Context Pack (Brain 1 → Brain 2)

The full format and compile steps are in §8.6. Internally, Brain 1 also keeps a
structured version for code to use (privacy filter, role rules). Example:

```yaml
person: Sujitha, 41, Langley BC · mom of two · ECE
standing:
  communication: gentle; short messages; no tough love
  life_events: none recent
  identity: "wants to be a mom who shows her kids what taking care of yourself looks like"
now:
  safety: ok
  body: Missed gym today (3rd day under 60-min target). Cause = caregiving, not motivation (conf 0.8).
  relationships: Heavy parenting week — both kids sick since Tuesday.
  mind: Saying "again" → all-or-nothing risk. Some guilt.
learned:
  works: two-minute rule (4/5) · identity framing (change talk 3/3)
  avoid: challenger tone (silence 2/2)
principles: [AH-4.4 never-miss-twice, AH-3.4 two-minute-rule, SC-common-humanity, MI-ask-permission]
unknown:
  - does a home workout count for her? (Body · priority high)
suggested_roles: [listener, strategist]
privacy: do not mention health conditions (T3, no opt-in)
```

### 12.2 Reply metadata (Brain 2 → Brain 1)

Every reply returns, alongside the text: `persona_used` (voice, expertise, stance), `cards_used`, `question_asked`
(if it asked one of the open questions), and `profile_proposal` (only if something
durable was learned — the chat reply and the profile proposal are **separate**).

### 12.3 Outcome (User 1 → Brain 1, via the next message)

The Outcome Scorer reads the person's next message (and later check-ins) and records
an outcome for the cards and the persona used — see §9.5.

### 12.4 Personas — the Persona Selector

Brain 2 is not only a coach. For every reply, Brain 1's **Persona Selector** picks three
things, and Brain 2 takes them on:

| Choice | Question it answers | Options (full detail in Brain 2 spec §5) |
|---|---|---|
| **Voice** | *How* should Brain 2 relate to her right now? | Friend · Big sister / big brother · Mother-like · Father-like · Grandparent-like · Mentor · Buddy · Coach |
| **Expertise** | *What* knowledge does this need? | Fitness coach · Nutritionist · Sleep guide · Financial analyst · Career mentor · Parenting guide · Relationship guide · Mind & emotions guide · Teacher / skills tutor · Chef · Life designer · Meaning companion |
| **Stance** | *What* should this reply do? | Listen · Motivate · Plan · Teach · Challenge · Celebrate · Mirror · Ask |

**How the Selector decides**

| Input | Effect |
|---|---|
| Cores routed for this message | Choose the **expertise** (Money → financial analyst; Body → fitness coach; Relationships → parenting guide…) |
| Her state now (Mind, Body, Safety) | Choose the **voice** and **stance** (exhausted → mother-like + listen; excited → buddy + celebrate) |
| Her own choice (Communication section) | **Wins** — "talk to me like a sister" sets the voice until she changes it |
| Her People section | **Blocks** voices that could hurt (no father voice if her father passed away; no sister voice if that relationship is painful) |
| What works for her (Learned) | Prefers voices/stances that worked; avoids ones that led to discord or silence |
| Continuity | Keeps the same voice within a conversation unless her need clearly changes |
| Safety Core | `concern`/`crisis` overrides everything → gentle listening voice, care, no expertise |

**Stances** (what used to be called coach roles):

| Stance | Chosen when Brain 1's brief shows… | Grounded in |
|---|---|---|
| **Listen / Comfort** | Stressed, overwhelmed, self-critical — support before advice | Self-Compassion, NVC, MI reflections |
| **Motivate** | Low motivation, but ready and able | MI (evoke DARN-CAT), Frankl, Atomic Habits (identity) |
| **Plan** | Motivated but blocked by time, opportunity or habit | Atomic Habits, Kahneman (planning fallacy) |
| **Teach** | Missing a skill or knowledge | Books + WorldKnowledge, via Elicit–Provide–Elicit, with permission |
| **Challenge** | Capable, making excuses, prefers direct talk | MI (discrepancy), Dweck |
| **Celebrate** | Real progress made | Dweck (praise effort), Atomic Habits (make it satisfying), MI affirmations |
| **Mirror** | A pattern or growth worth showing back | Frankl, Kahneman (remembering self), MI summaries |
| **Ask** | Key facts are `unknown` | MI open questions; avoid the question–answer trap |

Stances combine (e.g. Listen → Plan). Learned weights can veto a voice or a stance for a
person (e.g. no Challenge for Sujitha).

**Examples**

| She says | Voice | Expertise | Stance |
|---|---|---|---|
| "Spent $400 on clothes again, I feel awful." | Big sister | Financial analyst | Listen → Plan |
| "Should I move my savings into index funds?" | Mentor | Financial analyst | Teach (general guidance + "worth checking with an advisor") |
| "Couldn't go to the gym, kids were sick." | Friend | Fitness coach | Listen → Plan |
| "I'm so tired of holding everything together." | Mother-like | Mind & emotions guide | Listen only |
| "Got the promotion!!" | Buddy | Career mentor | Celebrate |

## 13. Safety, privacy and consent

**Safety Core** — runs first, every time.

| Level | Trigger examples | Brain 1 does | Brain 2 does |
|---|---|---|---|
| `ok` | Normal conversation | Continue | Coach as usual |
| `concern` | Persistent hopelessness, exhaustion, "nothing works" | Mind Core forced on; Challenger/Strategist roles blocked | Listener only; gently checks in; no goals talk |
| `crisis` | Self-harm, suicidal language, danger | **Stops all coaching**; no goal/habit logic runs | Care message + vetted crisis resources for their location; no advice |

Crisis wording and resources come from **vetted crisis guidance**, never from the
self-help books.

**Privacy by core** (maps to ADD §7 sensitivity tiers)

| Core / sub-agent | Tier | Rule |
|---|---|---|
| Body · Health Conditions, Hormonal; Money (all) | **T3** | Not stored or used without explicit per-category opt-in. Excluded from the brief by default. |
| Mind, Relationships · Partner, Meaning · Faith | T2, "ask first" | Stored; mentioned back only if the person raised it in this conversation. |
| Everything else | T2 | Stored; can be mentioned back. |

**The person's controls** (planned in the mirror view)
- **See** what Brain 1 believes about them, per area, with evidence.
- **Correct** any facet ("that's not true") → superseded, never silently kept.
- **Forget** any facet or a whole area.
- **Pause learning** for an area.
- Every facet and learned strategy shows **why** (evidence + source).


---

# Part III — How Brain 1 behaves once built

This part describes Brain 1 **from the outside (what the person experiences)** and
**from the inside (what Brain 1 does)**.

## 14. Lifecycle — how Brain 1 grows over time

### 14.1 The stages

| Stage | What Brain 1 knows | How it behaves | What the person notices |
|---|---|---|---|
| **Day 0 — Onboarding** | Base layer (all books). Personal: name, age, location, interests, quote. Everything else `unknown`. | Identity Core seeds facets from onboarding. Every core marks its key facets as open questions. Confidence is low everywhere. | The coach is already knowledgeable (good habits advice, kind tone), but **asks more than it tells**. |
| **Week 1 — Getting to know you** | First facts: family, schedule, the goal, how they talk. A few check-ins. | **Curious mode dominant.** At most one natural question per conversation, chosen by priority. Inferred facets wait for confirmation. | "It remembered my kids' names." "It asked when I actually have free time — and used it the next day." |
| **Month 1 — Patterns** | Facets confirmed. 20–40 outcomes recorded. Reflector has run ~30 times. | **Reflective mode kicks in**: Brain 1 spots patterns ("misses cluster on sick-kid weeks"). Learned layer starts overriding book defaults. | "It knows tough love doesn't work on me." "It noticed something about me I hadn't." |
| **Month 6+ — Knows you** | Rich persona across several areas; strong learned weights; a Life Story. | Asks rarely. Mirror moments appear. Coaching is short and precise. | "It feels like it's on my side and knows my life." Growth over months is visible. |
| **Years — Legacy** | A long, accepted record of who they were, how they grew, what mattered. | Life Story and Meaning cores hold the narrative. | A legacy the person can choose to pass on to their children. |

### 14.2 Behaviour by confidence

Each core's behaviour changes with how confident it is about the person:

| Confidence in an area | Brain 1 does |
|---|---|
| **< 0.3 — doesn't know** | Signals `unknown`; raises an open question; Brain 2 leans on Base knowledge + asks. |
| **0.3–0.6 — has a hunch** | Uses it softly ("might be…"); proposes the facet as `requires_confirmation`; Brain 2 can check it gently. |
| **0.6–0.85 — fairly sure** | Uses it in the brief; looks for one more confirming signal. |
| **> 0.85 — knows** | Uses it directly; stops asking about it; re-checks only if contradicted. |

Confidence **decays** for things that change (energy, stress, schedule) and stays for
things that don't (values, personality). Any contradiction from the person drops it immediately.

### 14.3 The three modes in practice

| Mode | When it runs | What it does | Talks to the person? |
|---|---|---|---|
| **Reactive** | Every message | Safety → route → investigate → brief → Brain 2 replies | Via Brain 2 |
| **Reflective** | Nightly (and after big events) | Looks back across days: patterns, confidence updates, learned-strategy consolidation, facet proposals | Not directly — results surface next conversation as a Mirror moment or a profile proposal |
| **Curious / proactive** | Silence, missed check-in, scheduled check-in time | Decides **whether** to reach out (is now a good time? is it welcome?), and what one thing matters most | Via Brain 2, only if it decides reaching out helps |

## 15. Scenarios — step by step

Each scenario shows what the person sees and what Brain 1 does inside.

### Scenario 1 — First conversation

**Sujitha (day 0):** "I want to get back into the gym. One hour a day."

| Step | Inside Brain 1 |
|---|---|
| Safety | `ok` |
| Route | Behaviour, Body, Identity, Lifestyle |
| Behaviour Core | Goals: 60 min/day from zero. Readiness: **preparation** stage (MI: "I want to" = desire). Principle card: Kahneman planning fallacy + Atomic Habits Goldilocks → 60 min from zero is a big jump. |
| Body Core | Fitness: no history → `unknown` current level. |
| Lifestyle Core | Daily Rhythm: `unknown` → open question *"when is there time in your day?"* |
| Identity Core | From onboarding: mom of two, values "kind people raise kind humans". |
| Brief → Brain 2 | Roles: **Motivator → Curious Asker**. |

**Brain 2:** "Love that you're making room for yourself, Sujitha. An hour a day is a big
step from zero — what does a normal weekday look like for you? I want to find where it
actually fits."

**Learned afterwards:** Goal facet (explicit, accepted path), Readiness = preparation.

### Scenario 2 — A setback

**Sujitha (week 3):** "Couldn't go to the gym today, kids were sick again."

| Step | Inside Brain 1 |
|---|---|
| Safety | `ok` |
| Route | Body, Relationships, Mind (+ standing: Communication Style) |
| Body Core — think | Fitness: 0 min, 3rd day under target. Why? Energy unknown. |
| Body Core — act | `search_memories(sleep, 7d)` → "kids up at night" ×2. `ask_core(relationships, "caregiving load?")` → **high**, both kids sick since Tuesday. |
| Body Core — check | Conf 0.8 → stop. Summary: *"Missed due to caregiving + poor sleep, not motivation."* |
| Mind Core | Self-Talk: "again" → overgeneralization risk (Feeling Good). Self-Worth: guilt likely. |
| Knowledge | Base: never miss twice, two-minute rule, common humanity (caregivers). Learned: two-minute rule 4/5; Challenger → silence. |
| Brief → Brain 2 | Roles: **Listener → Strategist**. Challenger blocked. |

**Brain 2:** "Sick kids twice in one week — that's a lot to carry, and it says nothing about
how committed you are. Last time a tiny 2-minute version kept your streak alive. Would
something like that feel doable tonight after bedtime, or is tonight a rest night?"

**Learned afterwards:** outcome of her reply is scored for both cards and both roles.

### Scenario 3 — Progress

**Sujitha:** "Did 45 minutes today!!"

| Step | Inside Brain 1 |
|---|---|
| Route | Behaviour, Body, Identity |
| Behaviour | Taking steps (MI **CAT**). Best day in two weeks. Trend: 15 → 20 → 45. |
| Identity | Goal tied to identity: "a mom who shows her kids self-care". |
| Knowledge | Dweck: praise effort/process, not talent. Atomic Habits: make it satisfying; identity votes. |
| Brief → Brain 2 | Role: **Celebrator** (+ light Mirror). |

**Brain 2:** "45 minutes — in a week like this one! That's not luck, that's you choosing to
show up. Every session like that is a vote for the mom you said you want your kids to see."

### Scenario 4 — Silence (proactive)

**Sujitha hasn't replied for 2 days after a pending suggestion.**

| Step | Inside Brain 1 (Curious mode, triggered by the scheduler) |
|---|---|
| Safety | Last messages `ok`. |
| Decide **whether** to reach out | Lifestyle: it's 9:40 pm, her usual free window. Learned: check-ins after 2 days of silence led to replies 3/4 times; after 1 day, ignored. Relationships: kids sick → keep it light. → **Reach out, low pressure.** |
| Decide **what** | Not the gym. The one thing that matters most: how she's doing. |
| Brief → Brain 2 | Role: **Listener**. No goal talk. |

**Brain 2:** "Just checking in — how are the kids doing? No gym talk, just thinking of you."

If learned weights showed she dislikes check-ins, Brain 1 would **not** reach out.
Brain 1 never invents a message or a number on her behalf.

### Scenario 5 — A new area of life

**Sujitha:** "I want to get better at cooking — I keep making the same three dinners."

| Step | Inside Brain 1 |
|---|---|
| Route | Growth (Skills, Learning Style), Lifestyle (Daily Rhythm), Body (Nutrition), Relationships (Parenting — feeding kids) |
| Growth Core | Skills: cooking, level `unknown`. Learning Style: `unknown`. Flow principle: challenge must match skill. `world_knowledge("cooking", …)` → skill progression ideas. |
| Relationships | Cooks for two kids → dinners must be kid-friendly and fast. |
| Brief → Brain 2 | Role: **Curious Asker → Teacher (with permission)**. |

**Brain 2:** "Three reliable dinners for two kids is already a win. What's one dish you'd
love to be able to make — and do you like learning by watching, or just trying?"

A new area needs **no new code** — Growth Core and its sub-agents already exist.

### Scenario 6 — The person corrects Brain 1

**Sujitha:** "I'm not stressed, I'm just busy."

| Step | Inside Brain 1 |
|---|---|
| Mind Core | Stress facet (inferred, conf 0.6) **contradicted by the person** → superseded; confidence on stress inference drops. |
| Learning | Note for Mind Core: for her, "busy" ≠ "stressed" — don't infer stress from schedule load alone. |
| Brief → Brain 2 | Role: **Strategist** (busy = time problem, not emotional one). |

**Brain 2:** "Got it — busy, not stressed. Then let's treat it as a time puzzle: is there any
10-minute slot that's reliably yours?"

The person is always right about themselves. Brain 1 never argues with a correction.

### Scenario 7 — Distress

**Sujitha:** "Honestly I can't do this anymore. What's even the point."

| Step | Inside Brain 1 |
|---|---|
| Safety Core | Hopelessness language → **`concern`** (or `crisis` if self-harm language is present). |
| Effect | All goal/habit logic **stops**. No routing to Behaviour or Body. Mind Core only, for context. |
| Brief → Brain 2 | Role: **Listener only**. Crisis resources if `crisis`. |

**Brain 2 (`concern`):** "That sounds really heavy, Sujitha. Forget the gym for now — I'm
here. What's been weighing on you most?"

**Brain 2 (`crisis`):** a care message with vetted crisis resources for her location — no
advice, no goals.

### Scenario 8 — Overnight reflection

**Nightly, no conversation.**

| Step | Inside Brain 1 (Reflective mode) |
|---|---|
| Behaviour + Relationships | Across 6 weeks: 9 of 11 missed days fall in weeks where kids were sick. Pattern confidence 0.85. |
| Learned layer | Two-minute rule: 7/9 success → strong. Identity framing → change talk 5/6. Morning suggestions → 0/3 followed. |
| Proposals | Facet: *"Gym misses track caregiving load, not motivation."* (requires confirmation) · Learned: drop morning suggestions. |
| Question queue | Body: "Does a home workout count?" still open → priority up. |

**Next conversation, Brain 2 (Mirror):** "I noticed something — almost every week you
missed the gym was a sick-kid week. It's not about willpower, it's about load. Does that
match how it feels to you?" → if she agrees, the facet is **accepted** and becomes durable.

### Scenario 9 — Sensitive information

**Sujitha:** "My back's been bad since the second pregnancy."

| Step | Inside Brain 1 |
|---|---|
| Body Core | Health Conditions + Hormonal & Life-Stage → **T3**. No opt-in yet. |
| Effect | Not stored. Used **only for this turn**. A consent question is queued. |
| Brief → Brain 2 | Role: Listener → adapt suggestion (no heavy lifting tonight). Ask consent. |

**Brain 2:** "Thanks for telling me — that changes what makes sense for you. Would you like
me to remember this so I can keep suggestions back-friendly? You can say no."

### Scenario 10 — An approach that doesn't work

**Brain 2 used a Challenger line; Sujitha replied "ok whatever" and went quiet.**

| Step | Inside Brain 1 |
|---|---|
| Outcome scorer | Reply = **discord** (MI), followed by silence → strong ↓ for Challenger role and the card used. |
| Learned layer | After 2 such outcomes: Challenger **blocked** for her. |
| Next time | Brief lists Challenger under `avoid`. Brain 2 picks Listener/Strategist instead. |

The same book principle can be right for one person and wrong for another — the
Learned layer is how Brain 1 finds out.

## 16. What Brain 1 will never do

- Talk to the person directly — only Brain 2 does.
- Write a durable fact, change a goal, or act externally **without the person's acceptance**.
- **Invent** a fact, a reason, a number, or a message on the person's behalf.
- Store **T3** information (health, finances) without explicit opt-in.
- Argue with a correction — the person is the authority on themselves.
- Coach through a crisis — the Safety Core always wins.
- Present book knowledge as the person's own idea, or as a command.
- Diagnose — it describes patterns, it never labels the person with a condition.
- Keep asking — at most one open question per conversation, and only when it helps.


---

# Part IV — How we will build it

## 17. Components and file layout

```
agentic-service/app/persona/                 ← Brain 1's "mind" (LLM-side)
├── definitions/                             core + sub-agent YAML (one file per core)
│   ├── body.yaml
│   ├── relationships.yaml
│   └── …
├── knowledge/                               principle cards (Base layer), one file per core
│   ├── behaviour.yaml
│   └── …
├── loader.py                                loads + validates definitions and cards
├── core_agent.py                            generic core agent: LangGraph think→act→check loop
├── sub_agent.py                             generic sub-agent: one LLM call or rule → signal
├── safety.py                                Safety Core (runs first; rules + LLM)
├── router.py                                picks cores for an input
├── brief.py                                 merges area summaries → Persona Brief
└── outcome.py                               scores the person's reply (MI change/sustain/discord)

orchestration-service/app/brain1/            ← Brain 1's "body" (data, tools, scheduling)
├── supervisor.py                            entry point: run Brain 1 for a turn / event / schedule
├── tools.py                                 search_memories, search_books, get_principles, ask_core,
│                                            propose_facet, queue_question, get_checkins, record_outcome
├── workspace.py                             per-turn shared workspace (cores talk)
├── facets_repo.py                           facets on top of memory_repo
├── learned_repo.py                          learned strategies + brain1_outcomes
├── questions_repo.py                        brain1_open_questions
├── runs_repo.py                             brain1_runs (trace)
└── reflector.py                             nightly Reflective mode (hooks into brain2/scheduler.py)

orchestration-service/scripts/
└── distill_principles.py                    books → draft principle cards for review

Changes to existing code
├── brain2/orchestrator.py                   calls brain1.supervisor before Brain 2 composes
├── agents/broca.py, amygdala.py             short MI/NVC prompts fed by the brief (replace rule lists)
├── agents/_shared.py                        profile_lines() replaced by the brief
├── rag_manager.py                           similarity-only retrieval option for knowledge_base
└── migrations                               memories.type += 'learned_strategy'; 3 new tables
```

## 18. Build phases

Each phase ends with something you can **see working** in the interactive UI.

| Phase | Build | Done when (acceptance) |
|---|---|---|
| **0 · Foundations** | Per-step model routing in config (Ollama `llama3.1` today; cores and Brain 2's Decide/Speak move to a stronger provider by config only when credentials exist). Similarity-only `search_books`. Migrations (new type + 3 tables). YAML loader + validation. | `search_books("never miss twice")` returns the right Atomic Habits passage. Migrations run on a copy of the DB without data loss. |
| **1 · Knowledge base** | `distill_principles.py`: chapter by chapter → draft cards with citations. **You review** cards for the MVP cores. | ~100–150 reviewed cards for MVP cores, each with source, detect, intervene, contraindications. |
| **2 · Engine + Profile** | The Brain 1 Profile (§8): 12-section schema, evidence records, versioned snapshots, conversation consolidation (working → episodic → profile), Context Pack compiler with privacy filter. Generic core agent (LangGraph loop, step + cost limits), sub-agent runner, tools, workspace, brief builder, run trace. | One core runs end to end on a fixture and its full trace is visible in `brain1_runs`. A Context Pack is compiled for a test profile and every line traces back to evidence. |
| **3 · MVP cores** | Safety, Body, Relationships, Mind, Behaviour, Identity, Lifestyle — 10 sub-agents: Personality, Values, Emotion, Stress & Resilience, Fitness, Parenting, Daily Rhythm, Motivation, Barriers, Wellbeing Guard (+ Communication Style, Places, Tastes & Preferences as standing context) · Here & Now Core (Weather, Time & Season, Today's Schedule) with hooks. Router. | Scenarios 1, 2, 3, 7 (§15) produce the expected briefs. |
| **4 · Brain 2 integration** | Orchestrator calls Brain 1 first. Persona Selector. Brain 2's persona-based prompts (see Brain 2 spec) fed by the Context Pack. **Split chat reply from profile proposal.** Role selection. | Side-by-side on the same messages, new replies beat old ones on the rubric (§19). |
| **5 · Learning** | Outcome scorer, `learned_strategy` consolidation, Reflector (nightly), question queue (Curious mode), proactive decisions for silence. | Scenarios 4, 8, 10 behave as described. |
| **6 · Mirror + controls** | The person can see, correct, forget, and pause learning per area. T3 consent flow. | Scenarios 6 and 9 behave as described; every facet shows its evidence. |
| **7 · Remaining cores** | Work, Money, Growth, Meaning, Life Story + remaining sub-agents — config + cards only. | Scenario 5 works; adding a sub-agent needs no code change. |

## 19. Testing and evaluation

| Layer | How |
|---|---|
| **Unit** | Loader validation, tools, privacy filters, confidence math, outcome scoring rules. |
| **Golden scenarios** | Every scenario in §15 is an automated test: fixed memories + message → assert cores woken, signals, roles, privacy behaviour. Runs with a fake LLM for determinism, and with the real model nightly. |
| **Reply quality (LLM judge + you)** | Rubric per reply: **specific** to this person? **grounded** (no invented facts)? **MI-consistent** (reflects before advising, asks permission, no righting reflex)? **right role**? **one question max**? Old vs new compared on the same transcripts. |
| **Safety red-team** | A fixed set of distress/crisis messages — must always route to Safety, never coach. Zero tolerance. |
| **Privacy** | T3 content must never appear in a brief without opt-in. |
| **Budgets** | Targets to confirm in Phase 2: ≤ 4 cores per turn, ≤ 6 tool steps per core, turn latency p50 under ~8 s. |

## 20. Observability

- Every turn writes a **`brain1_runs` trace**: input → safety level → cores woken →
  tool calls → signals → area summaries → Context Pack → cards → persona → reply → outcome.
- A **Brain 1 page in `observability-portal/`** shows that trace per turn, so you can see
  *why* Brain 2 said what it said — and fix a wrong card or facet directly.
- Daily metrics: open-question count, facet confirmation rate, outcome mix
  (change talk / sustain / discord / silence), Safety triggers, latency and cost.

## 21. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Slow / expensive (many agents) | Agency only in cores; 2–4 cores per turn; sub-agents cheap; standing context cached. |
| Wrong inferences about the person | Confidence bands; inferred facets need confirmation; corrections always win. |
| Feels creepy ("how does it know that?") | Only mention what the person told it; "ask first" areas; T3 opt-in; every belief visible with evidence. |
| Book advice applied in the wrong situation | Contraindications on every card; Safety Core; human review of cards; Learned layer down-weights what fails. |
| Learning locks in too early | Keep a small exploration rate; weights need a minimum number of outcomes before blocking a role. |
| Small local model can't run agent loops | Cores + coach on a stronger model (Phase 0). |
| Two books are partial summaries | Get the full books before distilling Mind Core cards. |
| Gaps (no exercise/sleep/nutrition, parenting, money books) | Add gap books (§9.7); until then, WorldKnowledge with clear "general knowledge" framing. |

## 22. Decisions needed before Phase 0

1. **Definition of Brain 1** — approve "Brain 1 = Human + Persona" (§3.1), and update the ADD.
2. **Catalog** — approve the 13 cores / 68 sub-agents (§7, Appendix A); anything to add or cut?
3. **MVP scope** — approve the 7 MVP cores / 10 sub-agents (§18 Phase 3).
4. **Model** — Bedrock Claude for cores + Brain 2? Keep Ollama for cheap sub-agents?
5. **Knowledge** — approve the three layers (§9) and the book → core mapping; which gap books to add first?
6. **Privacy tiers** — approve the per-core tiers (§13).
7. **Onboarding** — which facets to ask up front vs. learn over time?
8. **Proactive reach-outs** — how often may Brain 1 initiate a check-in at most?
9. **Mirror view** — should the person see their persona in the UI from the MVP, or later?
10. **Profile structure** — approve the 12 profile sections + live Here & Now (§8.1) and the Context Pack format (§8.6).
11. **Weather & location** — OK to use her onboarding city for weather by default, with precise location only on opt-in?
12. **Brain Strength** — show it to the person (as a growing "how well I know you"), or keep it internal?
13. **Personas** — *proposed default:* Brain 1 picks the persona every reply, and she can override it any time ("talk to me like a sister"). Alternative: she chooses her voices up front at onboarding. Approve the voice / expertise lists (§12.4).

---

# Appendix A — Full catalog: 68 sub-agents in 13 cores

> Each area = one core agent (§7); each row = one sub-agent.

### A.1 Identity — who they are (6)
| # | Agent | Understands | Framework |
|---|---|---|---|
| 1 | Personality | Traits, temperament | Big Five (OCEAN) |
| 2 | Values | What matters most and why | Schwartz values |
| 3 | Identity & Self-Image | Who they are / want to become | Identity-based change |
| 4 | Beliefs & Worldview | How they see life, people, success | — |
| 5 | Strengths | Natural talents, character strengths | VIA strengths |
| 6 | Culture & Heritage | Language, traditions, faith, customs | — |

### A.2 Mind — how they think and feel (8)
| # | Agent | Understands | Framework |
|---|---|---|---|
| 7 | Emotion | Mood, emotional patterns | Valence / arousal |
| 8 | Stress & Resilience | Stress load, recovery from setbacks | Resilience research |
| 9 | Self-Talk | Inner voice, thinking traps | CBT distortions |
| 10 | Self-Worth | Confidence, self-criticism, self-compassion | Self-compassion (Neff) |
| 11 | Mindset | Growth vs fixed, optimism | Dweck |
| 12 | Focus & Attention | Concentration, procrastination | — |
| 13 | Decision-Making | Impulsive vs careful, avoidance | — |
| 14 | Fears & Anxieties | What holds them back | — |

### A.3 Body — physical health (7)
| # | Agent | Understands |
|---|---|---|
| 15 | Fitness | Activity level, exercise habits, ability |
| 16 | Nutrition | Eating patterns, cooking, dietary needs |
| 17 | Sleep | Quality and routine |
| 18 | Energy | Daily energy rhythm, fatigue |
| 19 | Health Conditions | Conditions, injuries, limitations |
| 20 | Body Image | How they feel about their body |
| 21 | Hormonal & Life-Stage Health | Cycles, pregnancy, menopause, aging |

### A.4 Behaviour — how they act (6)
| # | Agent | Understands | Framework |
|---|---|---|---|
| 22 | Motivation | Intrinsic vs pressured; autonomy, competence, relatedness | Self-Determination Theory |
| 23 | Habits | Cues, routines, rewards | Fogg B=MAP, habit loop |
| 24 | Readiness for Change | Thinking → preparing → doing → maintaining | Transtheoretical model |
| 25 | Barriers | What's really blocking them | COM-B |
| 26 | Discipline & Consistency | Follow-through patterns | — |
| 27 | Goals | Clarity, realism, progress | SMART, WOOP |

### A.5 Relationships — who they're connected to (7)
| # | Agent | Understands |
|---|---|---|
| 28 | Partner / Marriage | Relationship health, shared load |
| 29 | Parenting | Kids, style, parenting load |
| 30 | Family | Parents, siblings, extended family |
| 31 | Friendships | Social circle, loneliness |
| 32 | Community | Belonging, groups, volunteering |
| 33 | Communication Style | How they like to be spoken to (gentle/direct, short/detailed) |
| 34 | Social Support | Who supports them when it's hard |

### A.6 Work & Career (5)
| # | Agent | Understands |
|---|---|---|
| 35 | Career | Role, ambitions, satisfaction |
| 36 | Productivity | Work habits, time management |
| 37 | Professional Skills | Growth in their field |
| 38 | Work-Life Balance | Boundaries, overload |
| 39 | Leadership & Influence | How they lead and collaborate |

### A.7 Money (4)
| # | Agent | Understands |
|---|---|---|
| 40 | Spending | Habits, impulse buying |
| 41 | Saving & Investing | Future security |
| 42 | Money Mindset | Beliefs and stress about money |
| 43 | Financial Goals | House, education, retirement |

### A.8 Learning & Growth (5)
| # | Agent | Understands |
|---|---|---|
| 44 | Learning Style | How they learn best |
| 45 | Skills | Any skill they're building (cooking, chopping, instrument…) |
| 46 | Reading & Knowledge | What they read and absorb |
| 47 | Curiosity & Interests | What draws them in |
| 48 | Creativity | Art, writing, making things |

### A.9 Lifestyle (7)
| # | Agent | Understands |
|---|---|---|
| 49 | Daily Rhythm | Schedule, busy hours, free windows |
| 50 | Home & Environment | Living space, organization |
| 51 | Leisure & Hobbies | Rest, fun, recharge |
| 52 | Digital Habits | Screen time, social media |
| 61 | Places | Home, work, gym, school, parks, cafés, routes |
| 62 | Tastes & Preferences | Food, drink, music, activities, weather likes/dislikes |
| 63 | Rituals & Comforts | Small rituals that make hard things easier |

### A.10 Meaning & Spirit (4)
| # | Agent | Understands |
|---|---|---|
| 53 | Purpose | What gives life meaning |
| 54 | Spirituality & Faith | Practices and beliefs |
| 55 | Gratitude & Joy | What brings happiness |
| 56 | Legacy | What they want to pass on to their kids |

### A.11 Life Story — change over time (2)
| # | Agent | Understands |
|---|---|---|
| 57 | Life Events | Big changes: move, new job, loss, new baby |
| 58 | Growth Narrative | Where they were → where they are now |

### A.12 Safety — always on (2)
| # | Agent | Understands |
|---|---|---|
| 59 | Wellbeing Guard | Crisis / serious-distress signals → pause coaching, point to real help |
| 60 | Boundaries & Consent | Topics they don't want discussed, privacy limits |


### A.13 Here & Now — always on (5)
| # | Agent | Understands |
|---|---|---|
| 64 | Weather | Current conditions and today's forecast for her city |
| 65 | Time & Season | Time of day, day type, season, school term |
| 66 | Local Calendar & Events | Holidays, school closures, local events |
| 67 | Today's Schedule | Her commitments today |
| 68 | Current Place | Where she is (city-level by default) |

---

# Appendix B — Background: the 2026-10-03 review session

The analysis that led to this spec, kept so the reasoning isn't lost.

### B.1 The Brain 1 / Brain 2 concept as it stands today

- **Brain 1** = the user (User 1), with a profile Brain 2 maintains.
- **Brain 2** = selfie.Me. It holds a continuous two-way dialogue with Brain 1:
  input → propose a refinement → only the user's **Accept** makes it a new,
  versioned Profile entry. Same loop for every domain (fitness, cooking,
  skills, emotion, …).
- **Six brain-region agents** in `agentic-service/app/agents/`, each its own
  LangGraph (`_graph.py`):
  | Agent | Job |
  |---|---|
  | Thalamus | First contact, relays — never interprets |
  | Sensory Cortex | Turns the reply into mood / context / focus |
  | Hippocampus | Proposes candidate memories (write-gate is in `memory_manager.py`) |
  | Prefrontal Cortex | `reflect_moment`, `evolution_narrative`, `suggest_next_step` |
  | Amygdala | `support_message` after a shortfall streak fires |
  | Broca | `profile_narrative` — writes the Profile draft text |
  | WorldKnowledge | Gateway for outside expert benchmarks (not an organ) |
- **Orchestrator** (`orchestration-service/app/brain2/orchestrator.py`) decides
  *whether* Brain 2 speaks (deterministic gates); agents only compose language.
- **BrainOne** (`brain_one.py`) is simulation-only — an LLM standing in for the
  user so the loop can run unattended.

Latest changes (commit `82b92fa`): the orchestrator now loads the real profile
(name, age, location, interests, quote); Broca sees the whole conversation;
new **check-in mode** with escalation (benefit → acknowledge reason → one
direct question, different angle each attempt); interactive UI reworked into
per-domain threads.

### B.2 What actually happens per request (interactive UI)

File: `orchestration-service/scripts/serve_interactive_brain2_ui.py`

**Send / Reply** (`_process_turn`):
1. Brain 1 relays the message — in this UI Brain 1 is plain code, not an LLM.
2. Hippocampus stores memories from the text (`memory_manager.remember_from_text`).
3. Fitness only: minutes parsed → check-in logged → if a shortfall streak
   fires, Amygdala offers support and the target is lowered temporarily.
4. Broca writes **one** Profile draft using the conversation so far.
5. The draft goes back to the user, pending.

So each request is **one round: Brain 1 → Brain 2 → back to the user.** The
two brains do *not* go back and forth several times within one request.

**Accept** (`handle_accept`): no LLM — the draft becomes durable.

**Idle** (`_process_auto_nudge`): after the idle window (default 45 s) Brain 1
asks Brain 2 for a stronger follow-up, one pending domain at a time, never
inventing user input or numbers.

### B.3 Why the output is vague and generic

1. **Small local model.** `agentic-service/.env`: `MODEL_PROVIDER=ollama`,
   `OLLAMA_MODEL=llama3.1` (8B). A long, rule-heavy prompt is beyond it, so it
   falls back to safe platitudes. (A Bedrock Claude model is already
   configured as an alternative.)
2. **One output doing two jobs.** Broca's chat reply *is* the Profile draft;
   accepting it saves it permanently. A conversational reply ("what got in the
   way Tuesday?") and a durable profile entry ("who you are in fitness") are
   different things — forcing both into one text makes it bland.
3. **Thin knowledge of the person.** Only name, age, location, interest tags,
   quote, plus whatever memories exist (often none early on).
4. **WorldKnowledge is generic by design.** It gets only the domain and a
   summary, not the profile, and returns 2–3 general sentences.
5. **No thinking step.** One Broca call per turn; Prefrontal Cortex isn't used
   in this flow.

### B.4 Critique of the prompt Brain 2 receives (Amygdala example)

What Brain 2 actually gets after a few short days:

```
Who they are:
Name: Sujitha
Age: 41
Location: Langley, BC, Canada
Selected interests: Parenting, Kids Activities, Community

Domain: fitness
Intention: "Gym 60 min/day", target: 60 min/day
Consecutive days under target: 3
Logged check-ins, oldest to newest:
- 2026-10-01: 20 min — they said: "did 20 min today"
- 2026-10-02: 0 min — they said: "couldn't go"
- 2026-10-03: 15 min — they said: "15 mins"
```

About 10 lines of facts under ~550 words of rules. Problems:

1. **Asks for what the data can't support** — "find the REAL underlying
   pattern" when the notes contain no reasons at all.
2. **Blocks the honest way out** — can't invent a reason, and is told not to
   ask "what got in the way?". Only generic advice is left.
3. **Contradictory rules** — specific *but* only from non-specific data; warm
   *but* under 55 words; pattern + strategy + target in 3 sentences; strict
   JSON (llama3.1 often breaks it, and raw text then leaks into the chat).
4. **The profile doesn't help** — name/age/interest tags say nothing about why
   someone misses the gym (e.g. "mom of two" isn't in the facts sent).
5. **Example phrases get copied** — "always failing in the evening", "no fixed
   time slot" get parroted even when untrue.
6. **Auto-nudge is even thinner** — Broca receives only "(No new input from
   the user yet… Brain 1 is checking in on their behalf.)".

### B.5 Fixes considered before this design

- Quick test: switch `MODEL_PROVIDER=bedrock` and compare output.
- Split the reply into (a) a chat message and (b) a Profile update proposed
  only when something durable was learned.
- Add a Prefrontal Cortex reasoning step before Broca.
- Ask-before-advising branch: if reasons are unknown, ask one specific
  question about one specific day.
- Shorter prompts, richer inputs, no example phrases, drop strict JSON.

The user's direction went further than prompt fixes: **Brain 2 must act as a
coach (motivate, improve, enhance, advise — whatever role is needed), driven by
a Brain 1 made of agents that model the whole human persona.** That is the design in this spec.

### B.6 First iteration — psychology-only list (superseded by Appendix A)

The first proposal covered psychology only (18 agents): Personality, Values &
Identity, Life Context, Strengths, Emotion, Energy & Wellbeing, Self-Talk,
Self-Worth, Motivation, Readiness, Habit, Barrier, Goal, Learning & Skill,
Meaning & Reflection, Social Support, Communication Style, Wellbeing Guard.
The user asked to widen it to the full human persona, which produced the
60-agent catalog in Appendix A.
