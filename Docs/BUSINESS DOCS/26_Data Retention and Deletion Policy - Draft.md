# Data Retention and Deletion Policy — Draft

*Version 0.3 | Company Document 26*

Define lifecycle controls for user data.

## User Control

Users can delete individual captures/memories and request account-level deletion.

## Deletion Scope

Deletion must address original source, derived memory, embeddings, indexes, cached copies, agent state and future training eligibility — including Profile entries, their full version history, and any cached outside-knowledge comparison results tied to them.

## Retention

Default retention should be transparent and configurable where practical. A superseded Profile version is a retained history record, not a deletion — it is only removed when the user deletes the underlying Profile entry or the account itself.

## Backups

Backup deletion behavior and retention windows must be documented before production launch.

## Working Status

This is a working document. It should evolve through founder usage, user research, product experiments, technical validation, and legal/security review.

## Basis

Grounded in the selfie.Me Strategic Framework and Business Model Canvas, the founder's clarified direction, and the Brain 1 / Brain 2 design in `Docs/FEATURES/Building_Brain1.md` and `Building_Brain2.md`, formalized in the Architecture, Functional and Technical Design Documents (V03).
