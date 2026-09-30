# MVP Scope

*Version 0.4 | Company Document 28*

Freeze the first build boundary.

## Reference Use Case: One-Hour Gym

The MVP is not built around an abstract domain list — it is built, end to end, around one complete, concrete story, and every other domain follows the same shape once this one works:

1. Brain 1 states an intention in their own words: "I want to gym for one hour a day." Explicit and self-authored, so it's trackable immediately — no reflection-check needed for a person's own stated goal.
2. Brain 1 checks in daily with what actually happened (0 min, 20 min, 60 min...).
3. Brain 2 deterministically detects a real shortfall — three or more consecutive days under target, never a single bad day — and only then does anything at all.
4. Brain 2 offers support: notices the pattern, asks what got in the way, and — only as a question, never a command — floats a smaller target. It never decides or acts for Brain 1.
5. Brain 1 responds in their own words. That response is what makes the moment eligible to become a memory at all.
6. Brain 2 drafts a Profile proposal — the "brain strength" story: the struggle, the support offered, what Brain 1 actually said — and presents it. This is a disclosure, not a write.
7. Brain 1 accepts it (or asks for a refinement, or rejects it). Only on accept does anything become durable.
8. If Brain 1 also adjusts the target, the old intention is superseded, never mutated — the original target and the fact it didn't work stay visible in history, alongside every version of the Profile entry, accepted or not.

This is built and running today: `orchestration-service/app/brain2/` (`profile_store.py`, `intentions_repo.py`, `orchestrator.py`), two new model modes in `agentic-service` (`brain2_support_message`, `brain2_profile_narrative`), nine endpoints under `/api/v1/brain2/*`, and a runnable proof at `orchestration-service/scripts/demo_brain2_gym_story.py`.

## Build Now

- Private account.
- Voice/text capture.
- Transcription.
- Memory extraction.
- Search.
- Belief/evolution timeline.
- Evidence-backed reflections.
- Advisor query using personal history.
- Feedback/correction.
- Export/delete.
- Basic agent activity log.
- The One-Hour Gym reference use case above, fully working end to end (done — see above), then the same mechanism extended to a second domain (an emotion, a relationship, a learning area) to prove it generalizes, with propose/accept/refine/reject and basic follow-through support throughout.
- A UI for the reference use case — deliberately not designed yet (two prior guesses at "what does mirror look like" were both wrong); do not build one without an explicit, checked-in decision on interaction shape first.

## Do Not Build Yet

- AI clone/avatar.
- Public sharing network.
- Fully autonomous external actions.
- Digital inheritance — any access to a user's Profile by a person other than the account owner, at any time, including after their death (`27_Consent and AI Identity Policy`).
- Custom foundation model.
- Complex microservice platform.
- Premature GPU infrastructure.

## Founder Pilot

Use daily for 60–90 days before broad launch and maintain a defect/insight journal.

## Working Status

This is a working document. It should evolve through founder usage, user research, product experiments, technical validation, and legal/security review.

## Basis

Grounded in the selfie.Me Strategic Framework and Business Model Canvas, the founder's clarified direction, and the Two Brains / Profile implementation plan formalized in the Architecture, Functional and Technical Design Documents (V02).
