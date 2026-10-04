# Security Architecture and Threat Model

*Version 0.3 | Company Document 25*

Identify major security risks and controls.

## Primary Threats

- Account takeover.
- Cross-user memory leakage.
- Prompt injection through stored content.
- Unauthorized agent actions.
- API key/secret exposure.
- Data exfiltration.
- Malicious trusted recipient.
- Model/inference leakage.
- An outside-knowledge lookup over-discloses personal context to an external provider.

## Controls

- MFA/passkeys where appropriate.
- Least privilege.
- Row-level/user-scoped authorization.
- Secrets management.
- Input/output validation.
- Agent permission boundaries.
- Audit logs.
- Rate limiting.
- Backups and incident response.
- Profile-comparison queries are scoped to the minimum fields needed, reviewed the same as any model prompt, and the provider must contractually agree to zero retention/no training on that content.

## Working Status

This is a working document. It should evolve through founder usage, user research, product experiments, technical validation, and legal/security review.

## Basis

Grounded in the selfie.Me Strategic Framework and Business Model Canvas, the founder's clarified direction, and the Brain 1 / Brain 2 design in `Docs/FEATURES/Building_Brain1.md` and `Building_Brain2.md`, formalized in the Architecture, Functional and Technical Design Documents (V03).
