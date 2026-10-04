# Agentic AI Architecture

*Version 0.4 | Company Document 12*

Define how selfie.Me's intelligence is structured, and its boundaries.

## Two Brains

- **Brain 1 = the Human + the Persona.** The Human is the only authority. The Persona is an agentic model of the Human, built and maintained by selfie.Me on their behalf. It never talks to the Human and never writes anything durable without their yes.
- **Brain 2 = the Voice.** One LLM that talks to the Human through a persona chosen by Brain 1.

This supersedes the V0.3 "one orchestrator, many jobs" framing: understanding the person and speaking to the person are now separate, explicitly designed systems.

## Brain 1 — 13 core agents, 68 sub-agents

Each core agent owns one area of life and is a real agent (goal, tools, bounded think → act → check loop, its own facets and open questions). Sub-agents are lightweight lenses the core calls.

| Core | Example sub-agents |
| --- | --- |
| Identity | Personality, Values, Strengths, Culture |
| Mind | Emotion, Stress, Self-Talk, Self-Worth, Mindset |
| Body | Fitness, Nutrition, Sleep, Energy, Health Conditions |
| Behaviour | Motivation, Habits, Readiness, Barriers, Goals |
| Relationships | Partner, Parenting, Family, Friends, Communication Style |
| Work | Career, Productivity, Work-Life Balance |
| Money | Spending, Saving, Money Mindset, Financial Goals |
| Growth | Learning Style, Skills, Reading, Curiosity, Creativity |
| Lifestyle | Daily Rhythm, Places, Tastes & Preferences, Rituals |
| Meaning | Purpose, Faith, Gratitude, Legacy |
| Life Story | Life Events, Growth Narrative |
| Safety (always on) | Wellbeing Guard, Boundaries & Consent |
| Here & Now (always on) | Weather, Time & Season, Local Calendar, Today's Schedule |

Supporting parts: Router, shared workspace, Context Pack compiler, Persona Selector, Outcome scorer, Reflector, question queue, Knowledge service (principle cards + book library).

## Brain 2 — five steps per reply

Understand → Decide → Speak → Check → Remember, implemented by the existing brain-region agents (Sensory Cortex, Prefrontal Cortex, Broca, Hippocampus) plus a new Anterior Cingulate for the Check.

## Personas

voice (friend, big sister/brother, mother-like, father-like, grandparent-like, mentor, buddy, coach) × expertise (fitness, nutrition, sleep, money, career, parenting, relationships, mind & emotions, skills, meaning) × stance (listen, motivate, plan, teach, challenge, celebrate, mirror, ask).

## Boundaries

- Neither brain writes durable personal context except through the memory write gate; inferred facts and profile narratives need the Human's explicit confirmation.
- No reply reaches the Human without passing Check.
- Safety overrides every persona.
- Personas never impersonate the Human's real people and always disclose being an AI when asked; expert personas give general guidance only.
- High-impact external actions are outside V1.

## Working Status

This is a working document. It should evolve through founder usage, user research, product experiments, technical validation, and legal/security review.

## Basis

Grounded in the selfie.Me Strategic Framework and Business Model Canvas, the founder's clarified direction, and the Brain 1 / Brain 2 design in `Docs/FEATURES/Building_Brain1.md` and `Docs/FEATURES/Building_Brain2.md`, formalized in the Architecture, Functional and Technical Design Documents (V03).
