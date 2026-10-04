# AI Product Specification

*Version 0.4 | Company Document 11*

Define what intelligence Brain 1 and Brain 2 are each responsible for.

## Brain 1 — the Persona (understands)

- Maintain a structured, evidence-backed model of the person: identity, people, inner world, body, life map and places, tastes and rituals, goals and their own reasons, story and conversation memory, what works for them, communication style, boundaries, and open questions.
- Start every person with a reviewed base of expert knowledge (principle cards distilled from the book library), so the first reply is already knowledgeable.
- Learn from every conversation; keep inferences as hypotheses until the person confirms them.
- Add live context — weather, time, season, schedule — for the person's city.
- Compile a Context Pack for each reply: only what matters now, privacy-filtered, with ready-made hooks (profile × moment) and unknowns.
- Pick Brain 2's persona — voice × expertise × stance — honouring the person's own choice.
- Learn what works for this person from how they respond; reflect nightly to find patterns and propose them for confirmation.
- Check safety first on every input.

## Brain 2 — the Voice (speaks)

- Understand the message (intent, feeling, readiness to change, question asked).
- Decide one plan in the chosen persona: stance, one or two moves, at most one hook and one question.
- Speak in the persona's voice: short, specific, warm, honest — never a list of tips, never flattery, never talking about the person in the third person.
- Check every reply before it is shown; rewrite or fall back if it fails.
- Remember: consolidate the turn into memory; propose a profile change only when something lasting was learned.

## Output Contract

Every important conclusion exposes conclusion, evidence, source dates, confidence, and whether it is observed / inferred / confirmed. Every reply records which persona and principles it used, so its outcome can be learned from.

## Failure Behavior

When evidence is weak, Brain 2 asks one good question instead of producing a generic answer. When a reply fails the Check, it is never shown.

## Learning Loop

Corrections, confirmations, accepted/rejected proposals, and the person's responses to each reply (change talk, action taken, pushback, silence) become labeled feedback for Brain 1's Learned layer.

## Working Status

This is a working document. It should evolve through founder usage, user research, product experiments, technical validation, and legal/security review.

## Basis

Grounded in the selfie.Me Strategic Framework and Business Model Canvas, the founder's clarified direction, and the Brain 1 / Brain 2 design in `Docs/FEATURES/Building_Brain1.md` and `Docs/FEATURES/Building_Brain2.md`, formalized in the Architecture, Functional and Technical Design Documents (V03).
